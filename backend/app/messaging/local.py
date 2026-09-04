from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.app.domain.models import MessageDelivery, PubSubMessage
from backend.app.repositories.ports import OperationsRepository


TOPIC_SUBSCRIPTIONS: dict[str, tuple[str, ...]] = {
    "building.events": ("operations.intake",),
    "workflow.commands": ("operations.workflow",),
}


class SQLiteDurablePubSub:
    """SQLite-backed at-least-once pub/sub with leases, backoff, and a DLQ state."""

    name = "SQLite durable pub/sub"

    def __init__(
        self,
        repository: OperationsRepository,
        *,
        max_attempts: int = 3,
        base_retry_seconds: float = 1,
        lease_seconds: float = 30,
    ):
        self.repository = repository
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        self.lease_seconds = lease_seconds

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
    ) -> PubSubMessage:
        if topic not in TOPIC_SUBSCRIPTIONS:
            raise ValueError(f"No subscriptions configured for topic {topic}")
        now = datetime.now(UTC)
        message = PubSubMessage(
            message_id=message_id or f"MSG-{uuid4().hex.upper()}",
            topic=topic,
            message_type=message_type,
            payload=payload,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            published_at=now,
            available_at=available_at or now,
        )
        self.repository.publish_message(message, list(TOPIC_SUBSCRIPTIONS[topic]))
        return message

    def pull(
        self,
        subscription: str,
        *,
        now: datetime | None = None,
        limit: int = 1,
    ) -> list[MessageDelivery]:
        return self.repository.claim_deliveries(
            subscription,
            now or datetime.now(UTC),
            limit,
            self.lease_seconds,
        )

    def acknowledge(self, delivery: MessageDelivery) -> None:
        self.repository.complete_delivery(
            delivery.subscription, delivery.message.message_id
        )

    def reject(
        self,
        delivery: MessageDelivery,
        error: Exception,
        *,
        now: datetime | None = None,
    ) -> bool:
        current = now or datetime.now(UTC)
        dead_letter = delivery.attempts >= self.max_attempts
        delay = min(30.0, self.base_retry_seconds * (2 ** (delivery.attempts - 1)))
        self.repository.retry_delivery(
            delivery.subscription,
            delivery.message.message_id,
            str(error),
            current + timedelta(seconds=delay),
            dead_letter=dead_letter,
        )
        return dead_letter

    def stats(self) -> dict[str, int]:
        return self.repository.message_stats()
