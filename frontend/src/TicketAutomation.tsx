import type { TicketDetail } from "./types";
import { ticketContributions } from "./automation";
import "./ticket-automation.css";

export function TicketAutomation({ detail }: { detail: TicketDetail }) {
  const work = ticketContributions(detail.events);
  const pending = ["needs_approval", "escalated"].includes(detail.ticket.status);
  return <section className="ticket-automation" aria-label="Who did the work">
    <header><div><small>WHO DID THE WORK</small><h3>{work.percentage === null ? "Work has not been recorded yet" : `${work.percentage}% of recorded coordination actions automated`}</h3></div><span>{detail.ticket.status === "resolved" ? "Closed request" : "So far"}</span></header>
    {work.percentage !== null && <div className="automation-bar" role="meter" aria-label="Automated share of recorded coordination actions" aria-valuenow={work.percentage} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${work.percentage}%` }} /></div>}
    <div className="automation-counts"><div><b>{work.agent.length}</b><span>Agent actions</span></div><div><b>{work.human.length}</b><span>Staff interventions</span></div><div><b>{work.technician.length}</b><span>Technician completions · simulated</span></div></div>
    <p>{pending ? "Your input is needed now; completed agent work is retained below." : work.human.length ? `Staff contributed ${work.human.length} recorded intervention${work.human.length === 1 ? "" : "s"}; the agent performed ${work.agent.length} coordination actions.` : "No staff intervention has been recorded."}</p>
    <div className="contribution-columns">{([["Agent handled", work.agent], ["Staff handled", work.human], ["Technician handled", work.technician]] as const).map(([title, items]) => <details key={title} open={title === "Staff handled" && items.length > 0}><summary>{title} <b>{items.length}</b></summary>{items.length ? <ul>{items.map(item => <li key={item.id}><b>{item.label}</b><p>{item.summary}</p><small>{item.actor} · {new Date(item.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</small></li>)}</ul> : <p>No completed actions recorded.</p>}</details>)}</div>
    <small className="automation-method">Calculation: agent actions ÷ (agent actions + staff interventions). Counts completed recorded steps, not time saved or percentage of the physical repair. Technician work, pending decisions, routing events and closure markers are excluded. A staff reply and its closure count once.</small>
  </section>;
}
