from __future__ import annotations

from typing import Any

from backend.app.domain.models import Ticket


class LocalNotificationProvider:
    """Local conversation adapter. Replace with SES/SNS/Connect without workflow changes."""

    def send(self, ticket: Ticket, message: str, audience: str, idempotency_key: str) -> dict[str, Any]:
        return {
            "delivered": True,
            "channel": "ticket_conversation",
            "audience": audience,
            "message": message,
            "idempotency_key": idempotency_key,
        }
