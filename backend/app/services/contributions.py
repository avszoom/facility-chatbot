from collections import defaultdict


def action_contributions(events: list[dict]) -> dict:
    """Count meaningful recorded coordination actions across complete ticket histories."""
    groups = defaultdict(dict)
    for event in events:
        groups[event["ticket_id"]][event["event_id"]] = event
    agent = human = technician = 0
    action_types = {"specialist.completed", "agent.decision", "action.completed", "work_order.created", "message.sent", "approval.requested", "verification.passed", "verification.failed"}
    for records in groups.values():
        items = list(records.values())
        sensor_report = any(e["event_type"] == "specialist.completed" and e["actor"] == "Sensor Intelligence Agent" for e in items)
        verified = any(e["event_type"] in {"verification.passed", "verification.failed"} for e in items)
        legacy_evidence = False
        for event in items:
            kind = event["event_type"]
            if kind in {"approval.decided", "staff.response_sent"}:
                human += 1
            elif kind == "work_order.completed":
                technician += 1
            elif not sensor_report and not legacy_evidence and kind in {"evidence.correlated", "evidence.collected"}:
                agent += 1
                legacy_evidence = True
            elif kind in action_types:
                if not (verified and event["actor"] == "Verification Agent"):
                    agent += 1
    total = agent + human
    percent = int(agent / total * 100 + 0.5) if total else None
    return {"agent_actions": agent, "human_actions": human, "technician_completions": technician, "agent_percent": percent, "human_percent": 100 - percent if percent is not None else None}
