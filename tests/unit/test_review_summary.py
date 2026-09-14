from types import SimpleNamespace
from backend.app.domain.models import TicketEvent
from backend.app.services.review_summary import review_summary


def test_system_failure_is_not_a_missing_knowledge_answer():
    ticket = SimpleNamespace(kind="service_request", status="escalated", waiting_reason=None)
    event = TicketEvent(event_id="E1", ticket_id="T1", actor="Coordinator",
        event_type="workflow.dead_lettered", summary="Unknown asset AIR-04-01", correlation_id="C1", created_at="2026-09-14T00:00:00Z")
    result = review_summary(ticket, [event])
    assert "equipment ID" in result["reason"]
    assert result["can_resolve"] is False
    assert "No successful" in result["changed"]


def test_completed_work_order_does_not_imply_verified_resolution():
    ticket = SimpleNamespace(kind="incident", status="escalated", waiting_reason=None)
    order = SimpleNamespace(work_order_id="WO1", technician="Jordan", status="completed")
    event = TicketEvent(event_id="E2", ticket_id="T1", actor="Coordinator",
        event_type="workflow.dead_lettered", summary="Failed verification handoff", correlation_id="C1", created_at="2026-09-14T00:00:00Z")
    result = review_summary(ticket, [event], order)
    assert "has not passed" in result["changed"]
    assert "not resolved" in result["reason"]
    assert not result["can_resolve"]
