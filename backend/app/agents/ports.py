from __future__ import annotations

from typing import Any, Protocol

from backend.app.domain.models import AgentDecision, CoordinatorDirective, SpecialistReport, Ticket


class AgentRuntime(Protocol):
    """Agent execution port. AgentCoreRuntime will implement the same interface."""

    name: str
    provider: str
    model_id: str
    real_model: bool
    coordinator_role: str
    specialist_roles: tuple[str, ...]

    def coordinate(
        self,
        ticket: Ticket,
        context: dict[str, Any],
        reports: list[SpecialistReport],
        iteration: int,
    ) -> CoordinatorDirective: ...
    def run_specialist(
        self, role: str, ticket: Ticket, context: dict[str, Any]
    ) -> SpecialistReport: ...
    def decide(self, ticket: Ticket, context: dict[str, Any]) -> AgentDecision: ...
