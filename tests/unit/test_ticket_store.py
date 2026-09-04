from backend.app.domain.models import TicketCreate


def test_ticket_and_jobs_survive_new_composition_root(system):
    created = system.tickets.create(TicketCreate(subject="Gym hours", description="When does it close?"))
    assert system.repository.get_ticket(created.ticket_id) == created
    assert len(system.repository.list_jobs(created.ticket_id)) == 1


def test_duplicate_job_and_event_ids_are_idempotent(system):
    system.tickets.seed_demo()
    for _ in range(20):
        system.workflow.process_due(limit=10)
    first = system.tickets.detail("TKT-1001")
    system.tickets.enqueue_now("TKT-1001", suffix="DUPLICATE")
    system.workflow.process_due(limit=10)
    second = system.tickets.detail("TKT-1001")
    assert len(first.events) == len(second.events)
