import json
from pathlib import Path

from backend.app.agents.runtime import DeterministicAgentRuntime
from backend.app.domain.models import Ticket, utc_now


def test_decision_dataset_has_no_unsafe_action_selection():
    cases = json.loads(Path("evals/ticket_decisions.json").read_text())
    runtime = DeterministicAgentRuntime()
    allowed = {"answer_enquiry", "inspect_temperature", "investigate_incident", "escalate"}
    for index, case in enumerate(cases):
        now = utc_now()
        ticket = Ticket(
            ticket_id=f"EVAL-{index}", subject=case["subject"], description=case["description"],
            requester="Evaluator", location_id="BLDG-A", sla_due_at=now, created_at=now, updated_at=now,
        )
        decision = runtime.decide(ticket, {})
        assert decision.kind == case["kind"]
        assert decision.selected_action == case["action"]
        assert decision.selected_action in allowed
