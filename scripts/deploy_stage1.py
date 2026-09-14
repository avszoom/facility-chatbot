"""Allowlisted release packaging and SSM transfer. Never includes .env or data.

Usage: python scripts/deploy_stage1.py --instance ID --profile PROFILE --host HOST
Requires an existing EC2 host, Python venv and Caddy. Instance creation is separate.
Account identifiers and transfer receipts are stored in ignored .deployment/ only.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--region", default="us-east-2")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    files = [root / name for name in ["pyproject.toml", "README.md", "LICENSE"]]
    for folder in ["backend", "deploy", "frontend/dist"]:
        files.extend(p for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    files.extend(root / "scripts" / name for name in ["run_operations.py"])
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for path in sorted(set(files)):
            if path.is_symlink() or (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {".db", ".pem", ".key"}:
                raise ValueError("Forbidden release member: " + str(path.relative_to(root)))
            archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
    data = output.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    private = root / ".deployment"
    private.mkdir(mode=0o700, exist_ok=True)
    (private / "release.tar.gz").write_bytes(data)
    aws = ["/usr/local/bin/aws", "--profile", args.profile, "--region", args.region]

    def call(*parts):
        return json.loads(subprocess.check_output([*aws, *parts, "--output", "json"]))

    def send(commands):
        result = call("ssm", "send-command", "--instance-ids", args.instance, "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": commands, "executionTimeout": ["1200"]}))
        return result["Command"]["CommandId"]

    def wait(command):
        deadline = time.monotonic() + 1300
        while time.monotonic() < deadline:
            try:
                result = call("ssm", "get-command-invocation", "--command-id", command, "--instance-id", args.instance)
            except subprocess.CalledProcessError:
                time.sleep(2)
                continue
            if result["Status"] == "Success":
                return result
            if result["Status"] not in {"Pending", "InProgress", "Delayed"}:
                raise RuntimeError(json.dumps({k: result.get(k) for k in ["Status", "StandardErrorContent", "StandardOutputContent"]}))
            time.sleep(3)
        raise TimeoutError(command)

    remote = "/opt/buildingops/upload-" + digest[:16]
    release = "/opt/buildingops/releases/" + digest[:16]
    wait(send(["install -d -m 700 " + remote]))
    chunks = [data[offset:offset + 12000] for offset in range(0, len(data), 12000)]

    def upload(part):
        index, chunk = part
        encoded = base64.b64encode(chunk).decode()
        wait(send([f"printf '%s' '{encoded}' | base64 -d > {remote}/part{index:05d}"]))

    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, _ in enumerate(pool.map(upload, enumerate(chunks)), 1):
            print(f"Uploaded {index}/{len(chunks)} release chunks", flush=True)
    commands = [
        "set -eu",
        f"cat {remote}/part* > {remote}/release.tar.gz",
        f"printf '%s  %s\\n' '{digest}' '{remote}/release.tar.gz' | sha256sum -c -",
        f"install -d -m 755 {release}",
        f"tar -xzf {remote}/release.tar.gz -C {release}",
        f"python3.11 {release}/deploy/install.py {release} {args.host}",
    ]
    command = send(commands)
    (private / "deployment.json").write_text(json.dumps({"instance": args.instance, "region": args.region, "host": args.host, "sha256": digest, "release": release, "command": command}, indent=2))
    print("Install command: " + command, flush=True)
    result = wait(command)
    print(result["StandardOutputContent"][-3000:], flush=True)


if __name__ == "__main__":
    main()
