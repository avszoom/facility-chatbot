import type { LiveOperations, Ticket } from "./types";
import { humanize } from "./format";

export function LiveWork({ live, tickets, onSelect }: { live: LiveOperations; tickets: Ticket[]; onSelect: (id: string) => void }) {
  const stages = [
    { label: "Queued", states: ["new"], color: "#71879c" },
    { label: "Investigating", states: ["triaging"], color: "#73b9ff" },
    { label: "Acting / field work", states: ["working", "waiting_technician"], color: "#bb9afa" },
    { label: "Verifying", states: ["waiting_verification"], color: "#65cfdf" },
    { label: "Resolved", states: ["resolved"], color: "#54dbaa" },
    { label: "Needs attention", states: ["needs_approval", "escalated"], color: "#efb574" },
  ].map(s => ({ ...s, count: tickets.filter(t => s.states.includes(t.status)).length }));
  const work = (live.agent.deliveries || []).filter(d => d.status === "processing");
  const unique = [...new Map(work.map(d => [d.ticket_id, d])).values()];
  const recent = live.recent_events.filter(e => tickets.some(t => t.ticket_id === e.ticket_id)).slice(0, 5);
  return <section className="mc-live-overview" aria-label="Live work overview"><div className="mc-stage-overview"><header><h3>Work moving through the building</h3><strong>{tickets.filter(t => t.status === "resolved").length}<small> / {tickets.length} requests resolved</small></strong></header>
    <div className="mc-stage-bars" role="img" aria-label={stages.map(s => `${s.count} ${s.label}`).join(", ")}>{stages.filter(s => s.count).map(s => <span key={s.label} style={{width:`${s.count / tickets.length * 100}%`,background:s.color}} title={`${s.count} ${s.label}`} />)}</div>
    <div className="mc-stage-legend">{stages.map(s => <span key={s.label}><i style={{background:s.color}} /><b key={s.count} className="metric-updated">{s.count}</b> {s.label}</span>)}</div>
    <h4>Executing now <span>Worker leases · not queued requests</span></h4>
    <div className="mc-now-cards">{unique.map(d => { const t = tickets.find(t => t.ticket_id === d.ticket_id); return <button key={d.ticket_id} onClick={() => onSelect(d.ticket_id)}><span className="mc-running-dot" /><b>{d.role || humanize(d.step || "Coordinator")}</b><small>{t?.subject || d.ticket_id}</small><em>{String(live.agent.workflow_states[d.ticket_id]?.checkpoint.objective || "Advancing the next saved workflow step")}</em></button>; })}{!unique.length && <p>{tickets.some(t => t.status === "new") ? "Waiting for a worker to pick up the queued requests." : "No worker is executing right now. Waiting requests remain visible below."}</p>}</div>
    </div><aside className="mc-live-feed"><h3>Latest agent activity</h3><div>{recent.map(e => <button key={e.event_id} onClick={() => onSelect(e.ticket_id)}><time>{new Date(e.created_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"})}</time><b>{e.actor}</b><p>{e.summary}</p><small>{e.ticket_id}</small></button>)}{!recent.length && <p>Activity will appear as requests are picked up.</p>}</div></aside></section>;
}
