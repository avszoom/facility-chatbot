import type { TicketEvent } from "./types";

export type Contribution = { id: string; label: string; actor: string; summary: string; at: string };
const agentActions: Record<string, string> = {
  "specialist.completed": "Specialist investigation",
  "agent.decision": "Selected the next action",
  "action.completed": "Applied a permitted change",
  "work_order.created": "Created and assigned technician work",
  "message.sent": "Sent a resident update",
  "approval.requested": "Prepared an approval request",
  "verification.passed": "Verified the outcome",
  "verification.failed": "Checked outcome; verification failed",
};

export function ticketContributions(events: TicketEvent[]) {
  const agent: Contribution[] = [], human: Contribution[] = [], technician: Contribution[] = [];
  const seen = new Set<string>();
  const hasSensorReport = events.some(event => event.event_type === "specialist.completed" && event.actor === "Sensor Intelligence Agent");
  let legacyEvidenceCounted = false;
  for (const event of events) {
    if (seen.has(event.event_id)) continue;
    seen.add(event.event_id);
    const contribution = { id: event.event_id, label: "", actor: event.actor, summary: event.summary, at: event.created_at };
    if (event.event_type === "approval.decided" || ["staff.response_sent", "staff.note_added"].includes(event.event_type)) {
      human.push({ ...contribution, label: event.event_type === "approval.decided" ? "Made an approval decision" : "Replied and closed the request" });
    } else if (event.event_type === "work_order.completed") {
      technician.push({ ...contribution, label: "Completed field work (simulated)" });
    } else if (!hasSensorReport && !legacyEvidenceCounted && ["evidence.correlated", "evidence.collected"].includes(event.event_type)) {
      agent.push({ ...contribution, label: "Investigated building evidence" });
      legacyEvidenceCounted = true;
    } else if (agentActions[event.event_type]) {
      agent.push({ ...contribution, label: event.event_type === "specialist.completed" ? event.actor : agentActions[event.event_type] });
    }
  }
  // Routing, duplicate summaries, intake and closure markers are not extra work.
  // Verification specialist and domain verifier describe one outcome check.
  const verified = agent.some(item => events.some(event => event.event_id === item.id && event.event_type.startsWith("verification.")));
  const countedAgent = verified ? agent.filter(item => item.actor !== "Verification Agent") : agent;
  const total = countedAgent.length + human.length;
  return { agent: countedAgent, human, technician, total, percentage: total ? Math.round(countedAgent.length / total * 100) : null };
}
