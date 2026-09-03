from datetime import UTC, datetime, timedelta

from backend.app.config import Settings
from backend.app.domain.models import ApprovalRequest, TicketStatus
from backend.app.system import build_system


def future():
    return datetime.now(UTC) + timedelta(hours=1)


def test_service_request_closes_only_after_verification(system):
    system.tickets.seed_demo()
    system.workflow.process_due(limit=10)
    before = system.tickets.detail("TKT-1002")
    assert before.ticket.status == TicketStatus.WAITING_VERIFICATION
    assert before.actions[0].before_state["setpoint_f"] == 72
    assert before.actions[0].after_state["setpoint_f"] == 70
    system.workflow.process_due(now=future(), limit=10)
    assert system.tickets.detail("TKT-1002").ticket.status == TicketStatus.RESOLVED


def test_failed_service_verification_escalates(system):
    system.tickets.seed_demo()
    system.building.set_verification_failure("TKT-1002", True)
    system.workflow.process_due(limit=10)
    system.workflow.process_due(now=future(), limit=10)
    assert system.tickets.detail("TKT-1002").ticket.status == TicketStatus.ESCALATED


def test_incident_survives_composition_root_restart(system):
    system.tickets.seed_demo()
    system.workflow.process_due(limit=10)
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
