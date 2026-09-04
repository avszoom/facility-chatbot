from __future__ import annotations

from backend.app.domain.models import TicketStatus


ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.NEW: {TicketStatus.TRIAGING},
    TicketStatus.TRIAGING: {TicketStatus.WORKING, TicketStatus.ESCALATED},
    TicketStatus.WORKING: {
        TicketStatus.NEEDS_APPROVAL,
        TicketStatus.WAITING_TECHNICIAN,
        TicketStatus.WAITING_VERIFICATION,
        TicketStatus.RESOLVED,
        TicketStatus.ESCALATED,
    },
    TicketStatus.NEEDS_APPROVAL: {TicketStatus.WORKING, TicketStatus.ESCALATED},
    TicketStatus.WAITING_TECHNICIAN: {
        TicketStatus.WAITING_VERIFICATION,
        TicketStatus.ESCALATED,
    },
    TicketStatus.WAITING_VERIFICATION: {
        TicketStatus.RESOLVED,
        TicketStatus.WORKING,
        TicketStatus.ESCALATED,
    },
    TicketStatus.RESOLVED: set(),
    TicketStatus.ESCALATED: {TicketStatus.RESOLVED},
}


def assert_transition(current: TicketStatus | str, target: TicketStatus | str) -> None:
    source = TicketStatus(current)
    destination = TicketStatus(target)
    if destination not in ALLOWED_TRANSITIONS[source]:
        raise ValueError(f"Illegal ticket transition: {source.value} -> {destination.value}")
