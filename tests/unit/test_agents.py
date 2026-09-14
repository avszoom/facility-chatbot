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


def test_enquiry_agent_eligibility_does_not_depend_on_prefetched_search_results():
    from backend.app.agents.specialists import roles_for
    from backend.app.domain.models import TicketCreate

    ticket = TicketCreate(
        subject="Where can I park my car?",
        description="Please tell me where resident parking is located.",
        requester="Resident",
        location_id="BLDG-A-LOBBY",
        kind="enquiry",
    )
    # The durable Ticket has additional generated fields; the router only needs
    # the common request attributes and deliberately receives no search result.
    assert roles_for(ticket, {"knowledge_result": None}) == ["Resident Knowledge Agent"]


def test_typed_investigation_decision_is_routed_through_execution():
    from backend.app.agents.runtime import enforce_phase_action
    from backend.app.domain.models import AgentDecision, CoordinatorDirective

    decision = AgentDecision(
        kind="enquiry",
        priority="low",
        objective="Answer the resident question.",
        selected_action="answer_enquiry",
        confidence=0.95,
        rationale="An authoritative answer is available.",
        user_update="I found the parking guidance.",
    )
    proposal = CoordinatorDirective(
        iteration=2,
        action="complete",
        objective="Answer the request.",
        rationale="The knowledge report answers the request.",
        state_summary="Ready to answer.",
        decision=decision,
    )

    guarded = enforce_phase_action(proposal, "investigation")

    assert guarded.action == "execute"
    assert guarded.decision == decision
    assert guarded.model_provider == "workflow-guardrail"


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


def test_missing_evidence_repairs_routing_without_fabricating_a_decision():
    from backend.app.agents.runtime import enforce_evidence_handoff
    from backend.app.domain.models import CoordinatorDirective
    proposal = CoordinatorDirective(iteration=2, action="execute", objective="Answer",
                                    rationale="Enough evidence", state_summary="Ready")
    repaired = enforce_evidence_handoff(proposal, ["Intake & Safety Agent", "Building Context Agent"])
    assert repaired.action == "delegate"
    assert repaired.specialist_role == "Intake & Safety Agent"
    assert repaired.decision is None
    assert repaired.model_provider == "workflow-guardrail"
    assert "guardrail" in repaired.rationale
    assert enforce_evidence_handoff(proposal, []) is proposal


def test_evidence_guard_preserves_safe_escalation_and_valid_model_choice():
    from backend.app.agents.runtime import enforce_evidence_handoff
    from backend.app.domain.models import CoordinatorDirective
    for action, role in [("escalate", None), ("delegate", "Building Context Agent")]:
        proposal = CoordinatorDirective(iteration=2, action=action, specialist_role=role,
                                        objective="Check", rationale="Next step", state_summary="Pending")
        assert enforce_evidence_handoff(proposal, ["Building Context Agent"]) is proposal
