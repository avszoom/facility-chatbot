from datetime import UTC, datetime, timedelta

from backend.app.agents.runtime import DeterministicAgentRuntime
from backend.app.domain.models import TicketCreate, TicketStatus


class FailingAgent(DeterministicAgentRuntime):
    name = "failing-test-double"

    def decide(self, ticket, context):
        raise TimeoutError("model unavailable")


def test_model_failure_retries_then_escalates_to_recoverable_state(system):
    system.agent = FailingAgent()
    system.workflow.agent = system.agent
    ticket = system.tickets.create(TicketCreate(subject="Unclear request", description="Please review this"))
    for index in range(4):
        system.workflow.process_due(now=datetime.now(UTC) + timedelta(hours=index + 1))
    saved = system.repository.get_ticket(ticket.ticket_id)
    assert saved.status == TicketStatus.ESCALATED
    assert any(event.event_type == "workflow.dead_lettered" for event in system.repository.list_events(ticket.ticket_id))
    assert system.message_bus.stats()["dead_letters"] == 1
    assert system.repository.get_workflow_state(ticket.ticket_id).status == "failed"
