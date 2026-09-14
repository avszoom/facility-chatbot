"""Resident-facing explanations based only on persisted workflow evidence."""


def review_summary(ticket, events, work_order=None):
    records = [e.model_dump(mode="json") for e in events]
    def latest(kind):
        return next((e["summary"] for e in reversed(records) if e["event_type"] == kind), "")

    done = []
    roles = {e["actor"] for e in records if e["event_type"] == "specialist.completed"}
    for role, label in [
        ("Building Context Agent", "Checked the building and location."),
        ("Sensor Intelligence Agent", "Checked sensor readings for the reported issue."),
        ("Maintenance Intelligence Agent", "Reviewed maintenance information."),
        ("Resident Knowledge Agent", "Searched the resident handbook."),
    ]:
        if role in roles:
            done.append(label)
    finding = latest("agent.decision")
    if work_order:
        done.append(f"Created work order {work_order.work_order_id}, assigned to {work_order.technician}.")
    changed = latest("action.completed") or "No successful equipment change or repair is recorded."
    if work_order:
        changed = ("Technician completion is recorded in the simulation. " +
                   ("The final check passed." if latest("verification.passed") else "The final check has not passed.")) if work_order.status == "completed" else "A work order exists, but no completed repair is recorded."
    failure = latest("workflow.dead_lettered")
    reason = latest("ticket.escalated") or ticket.waiting_reason or "The agent needs staff review before it can continue."
    next_step = "Review the findings and arrange the next step with facilities. Keep this request open until the outcome is checked."
    can_resolve = ticket.kind == "enquiry" and not work_order and not failure
    if failure:
        reason = "The automatic process failed after retries. This is a system problem, not a missing resident answer."
        if "Unknown asset" in failure:
            reason = "The agent could not find the equipment ID used in its work order, so the repair process stopped."
            next_step = "Ask facilities to confirm the correct equipment and technician assignment. The equipment mapping must be fixed before the workflow can be retried. You can send the resident an update below."
            if work_order and work_order.trade == "indoor_air_quality" and any(word in finding.lower() for word in ["hvac", "fan-coil", "thermostat"]):
                reason += " Its findings call for heating/cooling inspection, but the work order was assigned to air-quality services."
        elif "verification" in failure.lower():
            reason = "A check was recorded, but the system could not complete the final verification step. The request is not resolved."
            next_step = "Ask facilities to review the recorded work and confirm the outcome. The verification handoff needs fixing before the workflow can finish. Check that the resident’s original question was answered too."
    elif ticket.status == "needs_approval":
        reason = latest("approval.requested") or "The proposed action requires your approval."
        next_step = "Review the findings and approve technician dispatch, or decline and explain why. Approval starts the next step; it does not close the request."
    elif can_resolve:
        next_step = "Check the question and the agent’s findings. If you know the answer, send it below to answer the resident and close this request."
    return {"done": done, "finding": finding, "changed": changed, "reason": reason,
            "next_step": next_step, "can_resolve": can_resolve, "technical_detail": failure}
