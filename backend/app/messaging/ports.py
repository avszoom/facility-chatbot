from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from backend.app.domain.models import MessageDelivery, PubSubMessage


class MessageBusPort(Protocol):
    """At-least-once pub/sub contract; EventBridge plus SQS implements this on AWS."""

    name: str

    def publish(
        self,
        *,
        topic: str,
        message_type: str,
        payload: dict[str, Any],
        correlation_id: str,
        idempotency_key: str,
        message_id: str | None = None,
        available_at: datetime | None = None,
    ) -> PubSubMessage: ...

    def pull(
        self, subscription: str, *, now: datetime | None = None, limit: int = 1
    ) -> list[MessageDelivery]: ...

    def acknowledge(self, delivery: MessageDelivery) -> None: ...
    def reject(self, delivery: MessageDelivery, error: Exception, *, now: datetime | None = None) -> bool: ...
    def stats(self) -> dict[str, int]: ...
