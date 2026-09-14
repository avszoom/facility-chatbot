#!/usr/bin/env python3
"""Build and deploy the BuildingOps Strands boundary to AgentCore Runtime."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-2"
RUNTIME_NAME = "buildingops_autopilot"
RUNTIME_ROLE = "BuildingOpsAgentCoreRuntime"
EC2_ROLE = "BuildingOpsEc2Runtime"


def template(name: str, account_id: str) -> dict:
    text = (ROOT / "deploy" / name).read_text().replace("ACCOUNT_ID", account_id)
    return json.loads(text)


def build_zip(target: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="buildingops-agentcore-") as temp_name:
        temp = Path(temp_name)
        package = temp / "package"
        subprocess.run(
            [
                str(ROOT / ".venv" / "bin" / "python"), "-m", "pip", "install",
                "--platform", "manylinux2014_aarch64", "--python-version", "3.11",
                "--implementation", "cp", "--only-binary=:all:", "--target", str(package),
                "-r", str(ROOT / "agentcore" / "requirements.txt"),
            ],
            check=True,
        )
        shutil.copytree(ROOT / "backend", package / "backend")
        shutil.copy2(ROOT / "agentcore" / "main.py", package / "main.py")
        for path in list(package.rglob("__pycache__")):
            shutil.rmtree(path)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(package))


def ensure_bucket(s3, bucket: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
            raise
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION})


def wait_runtime(control, runtime_id: str) -> dict:
    for _ in range(90):
        state = control.get_agent_runtime(agentRuntimeId=runtime_id)
        if state["status"] == "READY":
            return state
        if state["status"] in {"CREATE_FAILED", "UPDATE_FAILED", "DELETING"}:
            raise RuntimeError(f"AgentCore deployment failed: {state['status']} {state.get('failureReason', '')}")
        time.sleep(10)
    raise TimeoutError("AgentCore runtime did not become ready in 15 minutes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="buildingops")
    parser.add_argument("--instance", required=True)
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    account_id = session.client("sts").get_caller_identity()["Account"]
    iam = session.client("iam")
    s3 = session.client("s3")
    control = session.client("bedrock-agentcore-control")
    bucket = f"buildingops-agentcore-{account_id}-{REGION}"

    trust = template("agentcore-trust-policy.template.json", account_id)
    try:
        role = iam.get_role(RoleName=RUNTIME_ROLE)["Role"]
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(
            RoleName=RUNTIME_ROLE,
            Description="Runs the BuildingOps Strands coordinator boundary in AgentCore",
            AssumeRolePolicyDocument=json.dumps(trust),
        )["Role"]
    iam.put_role_policy(
        RoleName=RUNTIME_ROLE,
        PolicyName="BuildingOpsAgentCoreExecution",
        PolicyDocument=json.dumps(template("agentcore-execution-policy.template.json", account_id)),
    )
    iam.get_waiter("role_exists").wait(RoleName=RUNTIME_ROLE)
    time.sleep(8)

    ensure_bucket(s3, bucket)
    with tempfile.TemporaryDirectory(prefix="buildingops-agentcore-artifact-") as temp_name:
        artifact = Path(temp_name) / "buildingops-agentcore.zip"
        build_zip(artifact)
        key = "releases/buildingops-agentcore.zip"
        s3.upload_file(str(artifact), bucket, key)

    artifact_config = {
        "codeConfiguration": {
            "code": {"s3": {"bucket": bucket, "prefix": key}},
            "runtime": "PYTHON_3_11",
            "entryPoint": ["main.py"],
        }
    }
    runtime_environment = {
        "APP_ENV": "aws_ec2",
        "AWS_REGION": REGION,
        "AGENT_RUNTIME": "strands",
        "BEDROCK_MODEL_ID": "us.amazon.nova-pro-v1:0",
    }
    existing = control.list_agent_runtimes(maxResults=100).get("agentRuntimes", [])
    match = next((item for item in existing if item.get("agentRuntimeName") == RUNTIME_NAME), None)
    if match:
        result = control.update_agent_runtime(
            agentRuntimeId=match["agentRuntimeId"], agentRuntimeArtifact=artifact_config,
            roleArn=role["Arn"], networkConfiguration={"networkMode": "PUBLIC"},
            environmentVariables=runtime_environment,
        )
    else:
        result = control.create_agent_runtime(
            agentRuntimeName=RUNTIME_NAME,
            description="BuildingOps durable coordinator and bounded specialist reasoning",
            agentRuntimeArtifact=artifact_config, roleArn=role["Arn"],
            networkConfiguration={"networkMode": "PUBLIC"},
            lifecycleConfiguration={"idleRuntimeSessionTimeout": 300, "maxLifetime": 1800},
            environmentVariables=runtime_environment,
        )
    state = wait_runtime(control, result["agentRuntimeId"])
    runtime_arn = state["agentRuntimeArn"]

    ec2_policy = template("bedrock-policy.template.json", account_id)
    ec2_policy["Statement"].append({
        "Sid": "InvokeBuildingOpsAgentCore",
        "Effect": "Allow",
        "Action": "bedrock-agentcore:InvokeAgentRuntime",
        # InvokeAgentRuntime is authorized against the runtime endpoint ARN,
        # not only the parent runtime returned by the control-plane API.
        "Resource": [runtime_arn, f"{runtime_arn}/runtime-endpoint/*"],
    })
    iam.put_role_policy(
        RoleName=EC2_ROLE,
        PolicyName="BuildingOpsBedrockInference",
        PolicyDocument=json.dumps(ec2_policy),
    )
    ssm = session.client("ssm")
    activate = ssm.send_command(
        InstanceIds=[args.instance],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [
            "set -eu",
            "sed -i 's/^AGENT_RUNTIME=.*/AGENT_RUNTIME=agentcore/' /etc/buildingops/application.env",
            "grep -q '^BEDROCK_MODEL_ID=' /etc/buildingops/application.env && sed -i 's|^BEDROCK_MODEL_ID=.*|BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0|' /etc/buildingops/application.env || printf '%s\\n' 'BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0' >> /etc/buildingops/application.env",
            "grep -q '^AGENTCORE_RUNTIME_ARN=' /etc/buildingops/application.env && sed -i 's|^AGENTCORE_RUNTIME_ARN=.*|AGENTCORE_RUNTIME_ARN=" + runtime_arn + "|' /etc/buildingops/application.env || printf '%s\\n' 'AGENTCORE_RUNTIME_ARN=" + runtime_arn + "' >> /etc/buildingops/application.env",
            "systemctl restart buildingops@scripts.run_operations",
        ]},
    )["Command"]["CommandId"]
    for _ in range(90):
        try:
            command = ssm.get_command_invocation(CommandId=activate, InstanceId=args.instance)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(2)
            continue
        if command["Status"] == "Success":
            break
        if command["Status"] not in {"Pending", "InProgress", "Delayed"}:
            raise RuntimeError(f"Could not activate AgentCore on EC2: {command['Status']}")
        time.sleep(2)
    else:
        raise TimeoutError("EC2 AgentCore activation did not finish")
    receipt = ROOT / ".deployment" / "agentcore.json"
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text(json.dumps({"region": REGION, "runtime_arn": runtime_arn}, indent=2) + "\n")
    print(json.dumps({"status": "READY", "runtime_arn": runtime_arn, "ec2_activation": "Success", "receipt": str(receipt)}))


if __name__ == "__main__":
    main()
