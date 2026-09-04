from __future__ import annotations

from datetime import UTC, datetime

from backend.app.domain.models import TicketCreate
from backend.app.messaging.ports import MessageBusPort
from backend.app.services.tickets import TicketService
from backend.app.services.workflow import WorkflowService


class OperationsMessageService:
    """Consumes cross-service events, then advances durable ticket workflows."""

    def __init__(
        self,
        message_bus: MessageBusPort,
        tickets: TicketService,
        workflow: WorkflowService,
    ):
        self.message_bus = message_bus
        self.tickets = tickets
        self.workflow = workflow

    def process_due(self, *, now: datetime | None = None, limit: int = 10) -> int:
        current = now or datetime.now(UTC)
        processed = self._consume_intake(current, limit)
        remaining = max(0, limit - processed)
        if remaining:
            processed += self.workflow.process_due(now=current, limit=remaining)
        return processed

    def _consume_intake(self, current: datetime, limit: int) -> int:
        deliveries = self.message_bus.pull(
            "operations.intake", now=current, limit=limit
        )
        processed = 0
        for delivery in deliveries:
            try:
                if delivery.message.message_type != "building.request.detected":
                    raise ValueError(
                        f"Unsupported building event {delivery.message.message_type}"
                    )
                payload = delivery.message.payload
                self.tickets.create(
                    TicketCreate.model_validate(payload["request"]),
                    ticket_id=str(payload["ticket_id"]),
                    intake_metadata=dict(payload.get("scenario") or {}),
                )
                self.message_bus.acknowledge(delivery)
                processed += 1
            except Exception as exc:
                self.message_bus.reject(delivery, exc, now=current)
        return processed
