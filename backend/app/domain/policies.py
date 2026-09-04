from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.domain.models import RiskTier


@dataclass(frozen=True)
class PolicyDecision:
    tier: RiskTier
    rule: str
    reason: str


class ActionPolicy:
    """Deterministic safety boundary shared by local and AWS tool adapters."""

    def evaluate(self, action: str, parameters: dict[str, Any]) -> PolicyDecision:
        if action in {"search_knowledge", "read_telemetry", "send_update"}:
            return PolicyDecision(RiskTier.AUTONOMOUS, "OPS-READ-001", "Read and communication action")
        if action == "set_temperature_setpoint":
            value = float(parameters.get("value", 0))
            if 68 <= value <= 75:
                return PolicyDecision(
                    RiskTier.AUTONOMOUS,
                    "HVAC-SP-002",
                    "Occupied-zone setpoint is inside the approved 68–75°F range",
                )
            return PolicyDecision(RiskTier.FORBIDDEN, "HVAC-SP-900", "Setpoint is outside the equipment policy")
        if action in {"dispatch_electrical_technician", "dispatch_safety_technician", "reset_critical_equipment"}:
            return PolicyDecision(
                RiskTier.APPROVAL_REQUIRED,
                "OPS-APPROVAL-010",
                "Potentially disruptive or safety-related work requires an operator decision",
            )
        if action in {"disable_life_safety", "isolate_electrical_feed", "override_access_control"}:
            return PolicyDecision(RiskTier.FORBIDDEN, "OPS-DENY-999", "Action is never delegated to the agent")
        return PolicyDecision(RiskTier.APPROVAL_REQUIRED, "OPS-DEFAULT-100", "Unknown writes require review")
