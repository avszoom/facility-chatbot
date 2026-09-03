from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from backend.app.domain.models import ActionRecord, RiskTier, Ticket
from backend.app.domain.policies import ActionPolicy
from backend.app.repositories.ports import OperationsRepository


SENSITIVE_KEYS = {"password", "secret", "token", "authorization", "api_key"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class ActionBlocked(RuntimeError):
    pass


class ApprovalRequired(RuntimeError):
    pass


class ActionGateway:
    """Deterministic pre-tool policy and post-tool audit boundary for writes."""

    def __init__(self, repository: OperationsRepository, policy: ActionPolicy | None = None):
        self.repository = repository
        self.policy = policy or ActionPolicy()

    def execute(
        self,
        ticket: Ticket,
        *,
        action_type: str,
        parameters: dict[str, Any],
        before_state: dict[str, Any],
        rationale: str,
        idempotency_key: str,
        operation: Callable[[], dict[str, Any]],
    ) -> ActionRecord:
        action_id = f"ACT-{ticket.ticket_id}-{idempotency_key}"
        existing = self.repository.get_action(action_id)
        if existing and existing.status == "completed":
            return existing

        decision = self.policy.evaluate(action_type, parameters)
        action = ActionRecord(
            action_id=action_id,
            ticket_id=ticket.ticket_id,
            action_type=action_type,
            risk_tier=decision.tier,
            policy_rule=decision.rule,
            status="proposed",
            before_state=redact(before_state),
            requested=redact(parameters),
            rationale=rationale or decision.reason,
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )
        if decision.tier == RiskTier.FORBIDDEN:
            action.status = "blocked"
            action.completed_at = datetime.now(UTC)
            self.repository.save_action(action)
            raise ActionBlocked(decision.reason)
        if decision.tier == RiskTier.APPROVAL_REQUIRED:
            self.repository.save_action(action)
            raise ApprovalRequired(decision.reason)

        self.repository.save_action(action)
        try:
            outcome = operation()
        except Exception as exc:
            action.status = "failed"
            action.after_state = {"error": type(exc).__name__}
            action.completed_at = datetime.now(UTC)
            self.repository.save_action(action)
            raise
        action.status = "completed"
        action.after_state = redact(outcome.get("after", outcome))
        action.completed_at = datetime.now(UTC)
        return self.repository.save_action(action)
