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
        ("Apartment warm", "The living room in my apartment is hot", TicketKind.SERVICE_REQUEST, "inspect_temperature"),
        ("Burning smell", "Lights flicker and smell hot", TicketKind.INCIDENT, "investigate_incident"),
    ]
    for subject, description, kind, action in cases:
        decision = runtime.decide(ticket(subject, description), {})
        assert decision.kind == kind
        assert decision.selected_action == action
        assert decision.specialist_reports
        assert decision.tool_calls[-1] == "operations_coordinator.synthesize"


def test_operational_ticket_delegates_to_sensor_and_maintenance_specialists():
    runtime = DeterministicAgentRuntime()
    decision = runtime.decide(
        ticket("Odor in the pantry", "There is a burning smell on floor 5"),
        {
            "building_facts": {
                "floor": 5,
                "primary_sensor": {
                    "id": "VOC-05-01",
                    "type": "VOC",
                    "state": "Critical",
                    "value": "410 ppb",
                },
                "nearby_sensors": [
                    {
                        "id": "VOC-05-01",
                        "type": "VOC",
                        "state": "Critical",
                        "value": "410 ppb",
                    }
                ],
                "sensor_histories": {"VOC-05-01": []},
                "maintenance_history": [],
            }
        },
    )

    roles = [report.role for report in decision.specialist_reports]
    assert roles == [
        "Intake & Safety Agent",
        "Building Context Agent",
        "Sensor Intelligence Agent",
        "Maintenance Intelligence Agent",
    ]
    assert decision.evidence_sensor_ids == ["VOC-05-01"]


def test_coordinator_delegates_one_unfinished_specialist_per_iteration():
    runtime = DeterministicAgentRuntime()
    request = ticket("Apartment warm", "The living room in my apartment is hot")
    context = {
        "phase": "investigation",
        "building_facts": {"nearby_sensors": []},
    }

    first = runtime.coordinate(request, context, [], 1)
    assert first.action == "delegate"
    assert first.specialist_role == "Intake & Safety Agent"

    first_report = runtime.run_specialist(first.specialist_role, request, context)
    second = runtime.coordinate(request, context, [first_report], 2)
    assert second.action == "delegate"
    assert second.specialist_role == "Building Context Agent"
    assert second.specialist_role != first.specialist_role


def test_coordinator_requires_an_independent_verification_report():
    runtime = DeterministicAgentRuntime()
    request = ticket("Apartment warm", "The living room in my apartment is hot")
    context = {
        "phase": "verification",
        "building_facts": {"nearby_sensors": []},
        "verification_result": {
            "passed": True,
            "summary": "TMP-04-01 returned to the normal band.",
            "readings": {"id": "TMP-04-01", "state": "Normal"},
        },
    }

    directive = runtime.coordinate(request, context, [], 6)
    assert directive.action == "delegate"
    assert directive.specialist_role == "Verification Agent"

    report = runtime.run_specialist("Verification Agent", request, context)
    assert report.evidence_sensor_ids == ["TMP-04-01"]
    verified = runtime.coordinate(request, context, [report], 7)
    assert verified.action == "verify"


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
