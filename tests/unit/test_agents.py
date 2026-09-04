from backend.app.agents.runtime import (
    DeterministicAgentRuntime,
    OpenAIStrandsRuntime,
    StrandsAgentRuntime,
    runtime_from_settings,
)
from backend.app.config import Settings
from backend.app.domain.models import Ticket, TicketKind, TicketStatus, utc_now


def ticket(subject: str, description: str) -> Ticket:
    now = utc_now()
    return Ticket(
        ticket_id="TKT-TEST",
        subject=subject,
        description=description,
        requester="Tester",
        location_id="BLDG-A",
        sla_due_at=now,
        created_at=now,
        updated_at=now,
    )


def test_deterministic_runtime_classifies_supported_paths():
    runtime = DeterministicAgentRuntime()
    cases = [
        ("Gym hours", "When does the fitness center close?", TicketKind.ENQUIRY, "answer_enquiry"),
        ("Catering delivery", "Where should the delivery use the loading dock?", TicketKind.ENQUIRY, "answer_enquiry"),
        ("Visitor arrival", "What is the visitor check-in process?", TicketKind.ENQUIRY, "answer_enquiry"),
        ("Room warm", "The conference room is hot", TicketKind.SERVICE_REQUEST, "inspect_temperature"),
        ("Burning smell", "Lights flicker and smell hot", TicketKind.INCIDENT, "investigate_incident"),
    ]
    for subject, description, kind, action in cases:
        decision = runtime.decide(ticket(subject, description), {})
        assert decision.kind == kind
        assert decision.selected_action == action


def test_strands_runtime_is_a_real_selectable_boundary():
    runtime = StrandsAgentRuntime(Settings(agent_runtime="strands"))
    assert runtime.name == "strands-bedrock"
    assert runtime.real_model is True


def test_openai_runtime_is_a_strands_boundary_without_exposing_key():
    runtime = runtime_from_settings(
        Settings(
            agent_runtime="openai",
            openai_model_id="gpt-5.2",
            **{"openai_api_key": "test-only"},
        )
    )

    assert isinstance(runtime, OpenAIStrandsRuntime)
    assert runtime.name == "strands-openai"
    assert runtime.provider == "openai-responses"
    assert runtime.model_id == "gpt-5.2"
    assert "test-only" not in repr(runtime)
