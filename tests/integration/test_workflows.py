from datetime import UTC, datetime, timedelta

from backend.app.config import Settings
from backend.app.domain.models import ApprovalRequest, TicketCreate, TicketStatus
from backend.app.system import build_system


def future():
    return datetime.now(UTC) + timedelta(hours=1)


def run_agent_steps(system):
    for _ in range(3):
        system.workflow.process_due(now=future(), limit=10)


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
    assert system.tickets.detail(ticket.ticket_id).ticket.status == TicketStatus.WORKING

    system.workflow.process_due(now=future(), limit=1)
    assert system.tickets.detail(ticket.ticket_id).ticket.status == TicketStatus.WAITING_VERIFICATION

    system.workflow.process_due(now=future(), limit=1)
    detail = system.tickets.detail(ticket.ticket_id)
    assert detail.ticket.status == TicketStatus.RESOLVED
    assert [event.event_type for event in detail.events] == [
        "ticket.created",
        "agent.started",
        "evidence.correlated",
        "specialist.completed",
        "specialist.completed",
        "specialist.completed",
        "specialist.completed",
        "agent.decision",
        "agent.tools_completed",
        "message.sent",
        "evidence.collected",
        "action.completed",
        "message.sent",
        "verification.passed",
        "message.sent",
        "ticket.resolved",
    ]
    assert detail.workflow
    assert detail.workflow.workflow_id == f"WF-{ticket.ticket_id}"
    assert detail.workflow.status == "completed"
    assert detail.workflow.current_step == "resolved"


def test_general_floor_report_uses_the_relevant_sensor_without_a_scripted_condition(system):
    ticket = system.tickets.create(
        TicketCreate(
            subject="Something smells wrong in the pantry",
            description="There is a strong burning smell near the pantry on floor 5.",
            requester="Avery Chen",
            location_id="BLDG-A-F05-PANTRY",
        )
    )

    run_agent_steps(system)
    detail = system.tickets.detail(ticket.ticket_id)
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


def test_service_request_closes_only_after_verification(system):
    system.tickets.seed_demo()
    run_agent_steps(system)
    before = system.tickets.detail("TKT-1002")
    assert before.ticket.status == TicketStatus.WAITING_VERIFICATION
    assert before.actions[0].before_state["setpoint_f"] == 72
    assert before.actions[0].after_state["setpoint_f"] == 70
    system.workflow.process_due(now=future(), limit=10)
    assert system.tickets.detail("TKT-1002").ticket.status == TicketStatus.RESOLVED


def test_failed_service_verification_escalates(system):
    system.tickets.seed_demo()
    system.building.set_verification_failure("TKT-1002", True)
    run_agent_steps(system)
    system.workflow.process_due(now=future(), limit=10)
    assert system.tickets.detail("TKT-1002").ticket.status == TicketStatus.ESCALATED


def test_incident_survives_composition_root_restart(system):
    system.tickets.seed_demo()
    run_agent_steps(system)
    system.tickets.decide_approval("TKT-1003", ApprovalRequest(approved=True))
    system.workflow.process_due(limit=10)
    assert system.tickets.detail("TKT-1003").ticket.status == TicketStatus.WAITING_TECHNICIAN

    restarted = build_system(
        Settings(database_path=system.settings.database_path, technician_delay_seconds=0, verification_delay_seconds=0)
    )
    restarted.workflow.process_due(now=future(), limit=10)
    restarted.workflow.process_due(now=future(), limit=10)
    detail = restarted.tickets.detail("TKT-1003")
    assert detail.ticket.status == TicketStatus.RESOLVED
    assert detail.work_order and detail.work_order.status == "completed"
    assert len([event for event in detail.events if event.event_type == "work_order.created"]) == 1
