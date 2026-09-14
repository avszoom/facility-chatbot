#!/usr/bin/env python3
"""Invoke the deployed AgentCore boundary with one typed specialist request."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3

from backend.app.agents.agentcore import AgentCoreRuntime
from backend.app.config import Settings
from backend.app.domain.models import Ticket


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="buildingops")
    args = parser.parse_args()
    receipt = json.loads((Path(__file__).resolve().parents[1] / ".deployment" / "agentcore.json").read_text())
    session = boto3.Session(profile_name=args.profile, region_name=receipt["region"])
    now = datetime.now(UTC)
    ticket = Ticket(
        ticket_id=f"TKT-VERIFY-{int(now.timestamp())}", subject="What time does the fitness center close?",
        description="Please confirm today's fitness center hours.", requester="Deployment verifier",
        location_id="BLDG-A-F01-FITNESS", sla_due_at=now + timedelta(hours=4),
        created_at=now, updated_at=now,
    )
    runtime = AgentCoreRuntime(
        Settings(agent_runtime="agentcore", aws_region=receipt["region"], agentcore_runtime_arn=receipt["runtime_arn"]),
        session.client("bedrock-agentcore"),
    )
    report = runtime.run_specialist(
        "Resident Knowledge Agent", ticket,
        {"objective": "Find authoritative fitness center hours", "knowledge_result": {
            "answer": "The fitness center is open from 5:00 AM to 11:00 PM daily.",
            "source": "Northstar Resident Handbook v1.4",
        }},
    )
    assert report.role == "Resident Knowledge Agent"
    if report.model_provider != "amazon-bedrock":
        raise AssertionError(
            f"Expected live Bedrock inference, got provider={report.model_provider!r}: {report.summary}"
        )
    print(json.dumps({"status": "PASS", "runtime": runtime.name, "role": report.role, "provider": report.model_provider}))


if __name__ == "__main__":
    main()
