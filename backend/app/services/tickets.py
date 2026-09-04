from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.domain.models import (
    ApprovalRequest,
    Ticket,
    TicketCreate,
    TicketDetail,
    TicketEvent,
    TicketStatus,
    WorkflowJob,
    WorkflowState,
)
from backend.app.domain.state_machine import assert_transition
from backend.app.repositories.ports import OperationsRepository
from backend.app.services.events import LocalEventBus
from backend.app.tools.building import LocalBuildingProvider


class TicketService:
    def __init__(
        self,
        repository: OperationsRepository,
        events: LocalEventBus,
        *,
        intake_delay_seconds: float = 0.8,
    ):
        self.repository = repository
        self.events = events
        self.intake_delay_seconds = intake_delay_seconds

    def _append(self, event: TicketEvent) -> None:
        if self.repository.append_event(event):
            self.events.publish({"type": "ticket.updated", "ticket_id": event.ticket_id})

    def create(self, request: TicketCreate, *, ticket_id: str | None = None) -> Ticket:
        if ticket_id:
            existing = self.repository.get_ticket(ticket_id)
            if existing:
                return existing
        now = datetime.now(UTC)
        ticket = Ticket(
            ticket_id=ticket_id or f"TKT-{uuid4().hex[:6].upper()}",
            subject=request.subject,
            description=request.description,
            requester=request.requester,
            location_id=request.location_id,
            kind=request.kind or "unknown",
            priority="normal",
            status="new",
            sla_due_at=now + timedelta(hours=4),
            created_at=now,
            updated_at=now,
        )
        self.repository.create_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-TRIAGE",
                ticket_id=ticket.ticket_id,
                job_type="advance",
                available_at=now + timedelta(seconds=self.intake_delay_seconds),
            ),
        )
        self.repository.save_workflow_state(
            WorkflowState(
                workflow_id=f"WF-{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                current_step=str(ticket.status),
                status="running",
                checkpoint={"ticket_status": str(ticket.status), "next": "triage"},
                version=ticket.version,
                updated_at=now,
            )
        )
        self._append(
            TicketEvent(
                event_id=f"EVT-{ticket.ticket_id}-CREATED",
                ticket_id=ticket.ticket_id,
                actor=request.requester,
                event_type="ticket.created",
                summary=request.description,
                payload={"subject": request.subject, "location_id": request.location_id},
                correlation_id=f"CORR-{ticket.ticket_id}",
                created_at=now,
            )
        )
        return ticket

    def list(self) -> list[Ticket]:
        return self.repository.list_tickets()

    def detail(self, ticket_id: str) -> TicketDetail:
        ticket = self.repository.get_ticket(ticket_id)
        if not ticket:
            raise KeyError(ticket_id)
        return TicketDetail(
            ticket=ticket,
            events=self.repository.list_events(ticket_id),
            actions=self.repository.list_actions(ticket_id),
            work_order=self.repository.get_work_order_for_ticket(ticket_id),
            workflow=self.repository.get_workflow_state(ticket_id),
        )

    def seed_demo(self) -> list[Ticket]:
        self.repository.reset()
        building = LocalBuildingProvider(self.repository)
        building.reset()
        building.inject_simulated_condition("comfort_drift", "BLDG-A-F04-CONF-4B", "TKT-1002")
        building.inject_simulated_condition("electrical_overheat", "BLDG-A-F07-EAST", "TKT-1003")
        tickets = [
            self.create(
                TicketCreate(
                    subject="What time does the gym close?",
                    description="I want to use the fitness center after work. What are today’s hours?",
                    requester="Priya Shah",
                    location_id="BLDG-A-F01-FITNESS",
                ),
                ticket_id="TKT-1001",
            ),
            self.create(
                TicketCreate(
                    subject="Conference room is too warm",
                    description="Conference Room 4B feels hot during our client meeting. Can facilities help?",
                    requester="Marcus Lee",
                    location_id="BLDG-A-F04-CONF-4B",
                ),
                ticket_id="TKT-1002",
            ),
            self.create(
                TicketCreate(
                    subject="Flickering lights and burning smell",
                    description="Lights are flickering near the Floor 7 east offices and we smell hot plastic.",
                    requester="Elena Garcia",
                    location_id="BLDG-A-F07-EAST",
                ),
                ticket_id="TKT-1003",
            ),
        ]
        self.events.publish({"type": "demo.seeded", "ticket_ids": [ticket.ticket_id for ticket in tickets]})
        return tickets

    def enqueue_now(self, ticket_id: str, suffix: str = "MANUAL") -> Ticket:
        ticket = self.repository.get_ticket(ticket_id)
        if not ticket:
            raise KeyError(ticket_id)
        self.repository.enqueue_job(
            WorkflowJob(
                job_id=f"JOB-{ticket_id}-{suffix}-{ticket.version}",
                ticket_id=ticket_id,
                job_type="advance",
                available_at=datetime.now(UTC),
            )
        )
        return ticket

    def decide_approval(self, ticket_id: str, request: ApprovalRequest) -> Ticket:
        ticket = self.repository.get_ticket(ticket_id)
        if not ticket:
            raise KeyError(ticket_id)
        if ticket.status != TicketStatus.NEEDS_APPROVAL:
            raise ValueError("Ticket has no pending approval")
        action = next(
            (item for item in reversed(self.repository.list_actions(ticket_id)) if item.status == "proposed"),
            None,
        )
        if not action:
            raise ValueError("Approval action not found")
        trade_label = str(action.requested.get("trade", "facilities")).replace("_", " ")
        now = datetime.now(UTC)
        action.status = "approved" if request.approved else "denied"
        action.completed_at = now if not request.approved else None
        self.repository.save_action(action)
        target = TicketStatus.WORKING if request.approved else TicketStatus.ESCALATED
        assert_transition(ticket.status, target)
        ticket.status = target
        ticket.waiting_reason = None
        ticket.updated_at = now
        ticket.version += 1
        if not request.approved:
            self.repository.save_ticket(ticket)
        self._append(
            TicketEvent(
                event_id=f"EVT-{ticket_id}-APPROVAL-{action.status.upper()}",
                ticket_id=ticket_id,
                actor="Facility Manager",
                event_type="approval.decided",
                summary=(
                    f"Approved qualified {trade_label} technician dispatch and controlled inspection."
                    if request.approved else
                    f"Denied the proposed action. {request.reason or 'Manual review required.'}"
                ),
                payload={"action_id": action.action_id, "approved": request.approved, "reason": request.reason},
                correlation_id=f"CORR-{ticket_id}",
                created_at=now,
            )
        )
        if request.approved:
            self.repository.save_ticket_and_job(
                ticket,
                WorkflowJob(
                    job_id=f"JOB-{ticket_id}-DISPATCH",
                    ticket_id=ticket_id,
                    job_type="dispatch_incident",
                    available_at=now,
                )
            )
        self.repository.save_workflow_state(
            WorkflowState(
                workflow_id=f"WF-{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                current_step=str(ticket.status),
                status="running" if request.approved else "failed",
                checkpoint={
                    "ticket_status": str(ticket.status),
                    "approved": request.approved,
                    "next": "dispatch_incident" if request.approved else None,
                },
                version=ticket.version,
                updated_at=now,
            )
        )
        return ticket
