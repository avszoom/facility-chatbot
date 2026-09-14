import type { LiveOperations, Ticket } from "./types";

export function progressStage(ticket: Ticket, events: string[] = []) {
  const stage = ({ new: 0, triaging: 1, working: 2, needs_approval: 2, waiting_technician: 2, waiting_verification: 3, resolved: 4, escalated: 1 })[ticket.status];
  if (ticket.status !== "escalated") return stage;
  if (events.some(e => e.startsWith("verification."))) return 3;
  if (events.some(e => ["action.completed", "work_order.created", "agent.decision"].includes(e))) return 2;
  return stage;
}

export function sortByProgress(tickets: Ticket[], live: LiveOperations): Ticket[] {
  const reports = (t: Ticket) => {
    const roles = live.agent.workflow_states[t.ticket_id]?.checkpoint.completed_specialists;
    return Array.isArray(roles) ? new Set(roles).size : 0;
  };
  const stage = (t: Ticket) => progressStage(t, live.agent.ticket_progress?.[t.ticket_id]?.event_types);
  const actions = (t: Ticket) => live.agent.ticket_progress?.[t.ticket_id]?.contributions.agent_actions || 0;
  return [...tickets].sort((a, b) => stage(b) - stage(a) || reports(b) - reports(a) || actions(b) - actions(a) || b.updated_at.localeCompare(a.updated_at) || a.ticket_id.localeCompare(b.ticket_id));
}
