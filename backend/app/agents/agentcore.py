"""Client adapter for the Strands team hosted by Amazon Bedrock AgentCore.

Only bounded reasoning runs remotely. Ticket state, policies, idempotent actions,
and the durable coordinator loop remain in the operations service.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.app.config import Settings
from backend.app.domain.models import CoordinatorDirective, SpecialistReport, Ticket


class AgentCoreRuntime:
    name = "strands-agentcore"
    provider = "amazon-bedrock-agentcore"
    real_model = True

    def __init__(self, settings: Settings, client=None):
        if not settings.agentcore_runtime_arn:
            raise ValueError("AGENTCORE_RUNTIME_ARN is required when AGENT_RUNTIME=agentcore")
        self.settings = settings
        self.model_id = settings.bedrock_model_id
        self.runtime_arn = settings.agentcore_runtime_arn
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("bedrock-agentcore", region_name=self.settings.aws_region)
        return self._client

    def _invoke(self, operation: str, ticket: Ticket, **arguments: Any) -> dict[str, Any]:
        payload = {
            "schema_version": "1",
            "operation": operation,
            "ticket": ticket.model_dump(mode="json"),
            **arguments,
        }
        # A stable ticket-scoped session isolates concurrent workflows while the
        # complete durable state is still supplied on every idempotent invocation.
        session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"buildingops:{ticket.ticket_id}"))
        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8"),
            qualifier=self.settings.agentcore_qualifier,
            contentType="application/json",
            accept="application/json",
        )
        body = response["response"]
        raw = body.read() if hasattr(body, "read") else b"".join(body)
        result = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if not isinstance(result, dict) or result.get("schema_version") != "1":
            raise RuntimeError("AgentCore returned an invalid response envelope")
        return result

    def run_specialist(self, role: str, ticket: Ticket, context: dict[str, Any]) -> SpecialistReport:
        result = self._invoke("run_specialist", ticket, role=role, context=context)
        return SpecialistReport.model_validate(result["report"])

    def coordinate(
        self,
        ticket: Ticket,
        context: dict[str, Any],
        reports: list[SpecialistReport],
        iteration: int,
    ) -> CoordinatorDirective:
        result = self._invoke(
            "coordinate",
            ticket,
            context=context,
            reports=[report.model_dump(mode="json") for report in reports],
            iteration=iteration,
        )
        return CoordinatorDirective.model_validate(result["directive"])
