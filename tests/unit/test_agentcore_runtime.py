import io
import json
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.agents.agentcore import AgentCoreRuntime
from backend.app.config import Settings
from backend.app.domain.models import SpecialistReport, Ticket


def ticket():
    now = datetime.now(UTC)
    return Ticket(
        ticket_id="TKT-ACORE1", subject="Gym hours", description="When does the gym close?",
        requester="Resident", location_id="BLDG-A-F01-FITNESS",
        sla_due_at=now + timedelta(hours=4), created_at=now, updated_at=now,
    )


class Client:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        return {"response": io.BytesIO(json.dumps(self.result).encode())}


def test_agentcore_requires_runtime_arn():
    with pytest.raises(ValueError, match="AGENTCORE_RUNTIME_ARN"):
        AgentCoreRuntime(Settings(agent_runtime="agentcore"))


def test_agentcore_specialist_uses_typed_envelope_and_stable_session():
    result = {"schema_version": "1", "report": {
        "role": "Resident Knowledge Agent", "objective": "Find hours", "summary": "Open until 10 PM",
        "findings": ["Handbook says 10 PM"], "confidence": 0.9,
    }}
    client = Client(result)
    runtime = AgentCoreRuntime(Settings(agent_runtime="agentcore", agentcore_runtime_arn="arn:test"), client)
    report = runtime.run_specialist("Resident Knowledge Agent", ticket(), {"objective": "Find hours"})
    assert report.summary == "Open until 10 PM"
    request = json.loads(client.calls[0]["payload"])
    assert request["operation"] == "run_specialist"
    assert len(client.calls[0]["runtimeSessionId"]) >= 33
    assert client.calls[0]["qualifier"] == "DEFAULT"
