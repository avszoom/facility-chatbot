from __future__ import annotations

from datetime import UTC, datetime

from backend.app.domain.models import Ticket, WorkOrder
from backend.app.repositories.ports import OperationsRepository


class LocalWorkOrderProvider:
    """CMMS simulator. Replace with an AgentCore Gateway or direct CMMS adapter later."""

    def __init__(self, repository: OperationsRepository):
        self.repository = repository

    def create(
        self,
        ticket: Ticket,
        *,
        asset_id: str,
        trade: str,
        procedure: str,
        due_at: datetime,
        idempotency_key: str,
    ) -> WorkOrder:
        existing = self.repository.get_work_order_for_ticket(ticket.ticket_id)
        if existing:
            return existing
        order = WorkOrder(
            work_order_id=f"WO-{ticket.ticket_id.removeprefix('TKT-')}",
            ticket_id=ticket.ticket_id,
            asset_id=asset_id,
            location_id=ticket.location_id,
            trade=trade,
            priority=ticket.priority,
            procedure=procedure,
            technician="Maya Chen · Electrical",
            status="in_progress",
            requested_at=datetime.now(UTC),
            due_at=due_at,
        )
        return self.repository.save_work_order(order)
    def complete(self, ticket_id: str, notes: str) -> WorkOrder:
        order = self.repository.get_work_order_for_ticket(ticket_id)
        if not order:
            raise KeyError(f"No work order for ticket {ticket_id}")
        if order.status == "completed":
            return order
        order.status = "completed"
        order.completed_at = datetime.now(UTC)
        order.completion_notes = notes
        return self.repository.save_work_order(order)
