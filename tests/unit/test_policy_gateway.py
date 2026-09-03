import pytest

from backend.app.domain.models import TicketCreate
from backend.app.services.action_gateway import ActionBlocked, ActionGateway


def test_forbidden_write_is_blocked_before_operation(system):
    ticket = system.tickets.create(TicketCreate(subject="Unsafe request", description="Disable the alarm"))
    called = False

    def operation():
        nonlocal called
        called = True
        return {"after": {"enabled": False}}

    with pytest.raises(ActionBlocked):
        ActionGateway(system.repository).execute(
            ticket,
            action_type="disable_life_safety",
            parameters={"enabled": False},
            before_state={"enabled": True},
            rationale="test",
            idempotency_key="FORBIDDEN",
            operation=operation,
        )
    assert called is False
    assert system.repository.get_action(f"ACT-{ticket.ticket_id}-FORBIDDEN").status == "blocked"


def test_autonomous_write_is_idempotent_and_redacted(system):
    ticket = system.tickets.create(TicketCreate(subject="Warm room", description="It is hot"))
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        return {"after": {"setpoint": 70, "token": "do-not-log"}}

    gateway = ActionGateway(system.repository)
    for _ in range(2):
        action = gateway.execute(
            ticket,
            action_type="set_temperature_setpoint",
            parameters={"value": 70, "api_key": "do-not-log"},
            before_state={"setpoint": 72},
            rationale="Within policy",
            idempotency_key="SAFE",
            operation=operation,
        )
    assert calls == 1
    assert action.requested["api_key"] == "[REDACTED]"
    assert action.after_state["token"] == "[REDACTED]"
