from datetime import UTC, datetime, timedelta

from backend.app.config import Settings
from backend.app.domain.models import ApprovalRequest, TicketCreate, TicketStatus
from backend.app.system import build_system


def future():
    return datetime.now(UTC) + timedelta(hours=1)


def run_until(system, ticket_id, *statuses):
    for _ in range(40):
        system.workflow.process_due(now=future(), limit=10)
        if system.tickets.detail(ticket_id).ticket.status in statuses:
            return system.tickets.detail(ticket_id)
    raise AssertionError(f"{ticket_id} did not reach {statuses}")


def run_seeded_investigation(system):
    for _ in range(40):
        system.workflow.process_due(now=future(), limit=10)
        states = {ticket.ticket_id: ticket.status for ticket in system.tickets.list()}
        if (
            states.get("TKT-1001") == TicketStatus.RESOLVED
            and states.get("TKT-1002") == TicketStatus.WAITING_VERIFICATION
            and states.get("TKT-1003") == TicketStatus.NEEDS_APPROVAL
        ):
            return
    raise AssertionError("Seeded investigations did not reach their durable waits")


def test_new_request_exposes_each_live_agent_phase(system):
    ticket = system.tickets.create(
        TicketCreate(
            subject="Apartment 4B is too warm",
            description="The living room in Apartment 4B feels hot.",
            requester="Building Resident",
            location_id="BLDG-A-F04-APT-4B",
        )
    )
    assert ticket.status == TicketStatus.NEW

    system.workflow.process_due(now=future(), limit=1)
    assert system.tickets.detail(ticket.ticket_id).ticket.status == TicketStatus.TRIAGING

    system.workflow.process_due(now=future(), limit=1)
    detail = system.tickets.detail(ticket.ticket_id)
    assert detail.ticket.status == TicketStatus.TRIAGING
    assert detail.workflow.current_step == "specialist:Intake & Safety Agent"

    detail = run_until(system, ticket.ticket_id, TicketStatus.WAITING_VERIFICATION)
    assert detail.workflow.checkpoint["phase"] == "verification"

    detail = run_until(system, ticket.ticket_id, TicketStatus.RESOLVED)
    assert detail.ticket.status == TicketStatus.RESOLVED
    event_types = [event.event_type for event in detail.events]
    assert event_types[0:3] == ["ticket.created", "coordinator.started", "evidence.correlated"]
    assert event_types.count("coordinator.delegated") == 5
    assert event_types.count("specialist.completed") == 5
    assert [event.actor for event in detail.events if event.event_type == "specialist.completed"][-1] == "Verification Agent"
    assert event_types[-3:] == ["verification.passed", "message.sent", "ticket.resolved"]
    assert detail.workflow
    assert detail.workflow.workflow_id == f"WF-{ticket.ticket_id}"
    assert detail.workflow.status == "completed"
    assert detail.workflow.current_step == "resolved"


def test_multiple_tickets_advance_as_independent_coordinator_loops(system):
    tickets = [
        system.tickets.create(
            TicketCreate(
                subject=f"Request {index}",
                description="When does the fitness center close?",
                requester=f"Resident {index}",
                location_id="BLDG-A-F02-FITNESS",
            )
        )
        for index in range(3)
    ]

    assert system.workflow.process_due(now=future(), limit=10) == 3
    assert all(
        system.tickets.detail(ticket.ticket_id).ticket.status == TicketStatus.TRIAGING
        for ticket in tickets
    )

    assert system.workflow.process_due(now=future(), limit=10) == 3
    details = [system.tickets.detail(ticket.ticket_id) for ticket in tickets]
    assert all(detail.workflow.current_step == "specialist:Intake & Safety Agent" for detail in details)
    assert {detail.workflow.workflow_id for detail in details} == {
        f"WF-{ticket.ticket_id}" for ticket in tickets
    }


def test_general_floor_report_uses_the_relevant_sensor_without_a_scripted_condition(system):
    ticket = system.tickets.create(
        TicketCreate(
            subject="Something smells wrong in the pantry",
            description="There is a strong burning smell near the pantry on floor 5.",
            requester="Avery Chen",
            location_id="BLDG-A-F05-PANTRY",
        )
    )

    detail = run_until(system, ticket.ticket_id, TicketStatus.WAITING_TECHNICIAN)
    decision = next(event for event in detail.events if event.event_type == "agent.decision")
    tools = next(event for event in detail.events if event.event_type == "agent.tools_completed")

    assert detail.ticket.status == TicketStatus.WAITING_TECHNICIAN
    assert decision.payload["evidence_sensor_ids"] == ["VOC-05-01"]
    assert [report["role"] for report in decision.payload["specialist_reports"]] == [
        "Intake & Safety Agent",
        "Building Context Agent",
        "Sensor Intelligence Agent",
        "Maintenance Intelligence Agent",
    ]
    assert [event.actor for event in detail.events if event.event_type == "specialist.completed"] == [
        "Intake & Safety Agent",
        "Building Context Agent",
        "Sensor Intelligence Agent",
        "Maintenance Intelligence Agent",
    ]
    assert tools.payload["evidence_sensor_ids"] == ["VOC-05-01"]
    assert detail.actions[0].requested["asset_id"] == "VOC-05-01"
    assert detail.actions[0].requested["trade"] == "indoor_air_quality"
    assert detail.work_order and detail.work_order.status == "in_progress"
    coordinator_events = [event for event in detail.events if event.event_type == "coordinator.delegated"]
    assert len(coordinator_events) == 4
    assert [event.payload["iteration"] for event in coordinator_events] == [1, 2, 3, 4]


def test_service_request_closes_only_after_verification(system):
    system.tickets.seed_demo()
    run_seeded_investigation(system)
    before = system.tickets.detail("TKT-1002")
    assert before.ticket.status == TicketStatus.WAITING_VERIFICATION
    assert before.actions[0].before_state["setpoint_f"] == 72
    assert before.actions[0].after_state["setpoint_f"] == 70
    assert run_until(system, "TKT-1002", TicketStatus.RESOLVED).ticket.status == TicketStatus.RESOLVED


def test_failed_service_verification_escalates(system):
    system.tickets.seed_demo()
    system.building.set_verification_failure("TKT-1002", True)
    run_seeded_investigation(system)
    assert run_until(system, "TKT-1002", TicketStatus.ESCALATED).ticket.status == TicketStatus.ESCALATED


def test_incident_survives_composition_root_restart(system):
    system.tickets.seed_demo()
    run_seeded_investigation(system)
    system.tickets.decide_approval("TKT-1003", ApprovalRequest(approved=True))
    system.workflow.process_due(limit=10)
    assert system.tickets.detail("TKT-1003").ticket.status == TicketStatus.WAITING_TECHNICIAN

    restarted = build_system(
        Settings(database_path=system.settings.database_path, technician_delay_seconds=0, verification_delay_seconds=0)
    )
    detail = run_until(restarted, "TKT-1003", TicketStatus.RESOLVED)
    assert detail.ticket.status == TicketStatus.RESOLVED
    assert detail.work_order and detail.work_order.status == "completed"
    assert len([event for event in detail.events if event.event_type == "work_order.created"]) == 1


def test_coordinator_loop_resumes_after_restart_between_handoffs(system):
    ticket = system.tickets.create(
        TicketCreate(
            subject="Gym access hours",
            description="When does the resident gym close?",
            requester="Priya Shah",
            location_id="BLDG-A-F02-FITNESS",
        )
    )
    system.workflow.process_due(now=future(), limit=1)
    system.workflow.process_due(now=future(), limit=1)
    system.workflow.process_due(now=future(), limit=1)
    before = system.tickets.detail(ticket.ticket_id)
    assert before.workflow.current_step == "coordinator:review"
    assert before.workflow.checkpoint["completed_specialists"] == ["Intake & Safety Agent"]

    restarted = build_system(
        Settings(
            database_path=system.settings.database_path,
            intake_delay_seconds=0,
            agent_analysis_seconds=0,
            action_delay_seconds=0,
            verification_delay_seconds=0,
        )
    )
    detail = run_until(restarted, ticket.ticket_id, TicketStatus.RESOLVED)
    assert detail.ticket.status == TicketStatus.RESOLVED
    assert len([
        event for event in detail.events
        if event.event_type == "specialist.completed" and event.actor == "Intake & Safety Agent"
    ]) == 1
