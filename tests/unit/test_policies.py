from backend.app.domain.models import RiskTier
from backend.app.domain.policies import ActionPolicy


def test_localized_qualified_dispatch_is_autonomous():
    decision = ActionPolicy().evaluate(
        "dispatch_electrical_technician",
        {
            "qualified_personnel": True,
            "scope": "localized",
            "service_disruption": False,
        },
    )

    assert decision.tier == RiskTier.AUTONOMOUS
    assert decision.rule == "OPS-DISPATCH-003"


def test_shared_infrastructure_dispatch_still_requires_approval():
    decision = ActionPolicy().evaluate(
        "dispatch_electrical_technician",
        {
            "qualified_personnel": True,
            "scope": "shared_infrastructure",
            "service_disruption": True,
        },
    )

    assert decision.tier == RiskTier.APPROVAL_REQUIRED
    assert decision.rule == "OPS-APPROVAL-010"
