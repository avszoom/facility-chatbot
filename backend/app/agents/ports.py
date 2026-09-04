from __future__ import annotations

from typing import Any, Protocol

from backend.app.domain.models import AgentDecision, Ticket


class AgentRuntime(Protocol):
    """Agent execution port. AgentCoreRuntime will implement the same interface."""

    name: str
    provider: str
    model_id: str
    real_model: bool

    def decide(self, ticket: Ticket, context: dict[str, Any]) -> AgentDecision: ...
