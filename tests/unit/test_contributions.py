from backend.app.services.contributions import action_contributions


def test_counts_full_histories_without_inflating_agent_work():
    def event(id, kind, actor="Agent", ticket="A"):
        return dict(event_id=id, event_type=kind, actor=actor, ticket_id=ticket)
    events = [event("1", "agent.decision"), event("2", "message.sent"), event("3", "staff.response_sent", "Maya"), event("4", "ticket.resolved"), event("5", "work_order.completed", "Technician"), event("6", "coordinator.delegated"), event("7", "specialist.completed", "Verification Agent"), event("8", "verification.passed")]
    result = action_contributions(events + [events[0]])
    assert result == dict(agent_actions=3, human_actions=1, technician_completions=1, agent_percent=75, human_percent=25)


def test_empty_history_does_not_claim_automation():
    assert action_contributions([])["agent_percent"] is None
