import type { LiveOperations, Metrics, Ticket } from "./types";
import { humanize, ticketStatusLabel } from "./format";

type Props = {
  tickets: Ticket[];
  metrics: Metrics;
  live: LiveOperations;
  onReview: (ticket: Ticket) => void;
};

const locationName = (id: string) => ({
  "BLDG-A-F02-FITNESS": "Fitness Center · Floor 2",
  "BLDG-A-F04-APT-4B": "Apartment 4B · Floor 4",
  "BLDG-A-F04-CONF-4B": "Apartment 4B · Floor 4",
  "BLDG-A-F07-EAST": "East Residential Wing · Floor 7",
  "BLDG-A-LOBBY": "Main Lobby & Concierge · Floor 1",
}[id] || id);

const time = (value: string) => new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
}).format(new Date(value));

const nextAction = (ticket: Ticket) => {
  if (ticket.status === "needs_approval") return "Review approval";
  if (ticket.status === "escalated") return "Send staff response";
  if (ticket.status === "waiting_technician") return "Await completion";
  if (ticket.status === "waiting_verification") return "Verify outcome";
  if (ticket.status === "resolved") return "Completed";
  return "Autopilot handling";
};

export function OverviewView({ tickets, metrics, live, onReview }: Props) {
  const needsYou = tickets.filter((ticket) => ticket.status === "needs_approval" || ticket.status === "escalated");
  const waitingExternal = tickets.filter((ticket) => ticket.status === "waiting_technician");
  const agentWorking = tickets.filter((ticket) => ["new", "triaging", "working", "waiting_verification"].includes(ticket.status));
  const autonomyRate = live.impact.contributions?.agent_percent ?? 0;
  const primaryDecision = needsYou[0];
  const active = [...tickets].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).slice(0, 10);
  const otherOpen = Math.max(0, metrics.active - needsYou.length);

  return <section className="overview-view">

    <div className="overview-grid">
      <section className="overview-panel decision-list">
        <div className="overview-panel-head"><div><h2>{needsYou.length ? `${needsYou.length} request${needsYou.length === 1 ? "" : "s"} need your attention` : "No requests need your attention"}</h2><p>Autopilot is handling the other {otherOpen} open requests.</p></div><span className="decision-count">{needsYou.length}</span></div>
        {needsYou.length ? needsYou.slice(0, 2).map((ticket) => <button className="decision-row" onClick={() => onReview(ticket)} key={ticket.ticket_id}>
          <span className={`decision-severity ${ticket.priority}`}>{ticket.priority.toUpperCase()}</span>
          <div><b>{ticket.subject}</b><small>{ticket.ticket_id} · {locationName(ticket.location_id)}</small><p>{ticket.status === "needs_approval" ? "Autopilot completed the investigation and needs approval for the consequential next step." : "Autopilot could not complete this safely and routed the exception to you."}</p><em>{nextAction(ticket)} →</em></div>
        </button>) : <div className="overview-clear"><span>✓</span><div><b>Nothing needs your attention</b><small>Autopilot owns every open request.</small></div></div>}
      </section>

      <section className="overview-panel autonomy-panel">
        <div className="overview-panel-head"><div><h2>Who handled the coordination</h2><p>Completed actions across all requests, including staff-assisted closures</p></div></div>
        <div className="autonomy-chart"><div className="autonomy-ring" style={{ background: `conic-gradient(#38c986 ${autonomyRate * 3.6}deg, #e9eef4 0deg)` }}><span><b>{live.impact.contributions?.agent_percent == null ? "—" : `${autonomyRate}%`}</b><small>actions by agents</small></span></div><dl><div><dt><i className="green" />Agent actions</dt><dd>{live.impact.contributions?.agent_actions ?? "—"}</dd></div><div><dt><i className="blue" />Staff actions</dt><dd>{live.impact.contributions?.human_actions ?? "—"}</dd></div><div><dt><i className="violet" />Agent working</dt><dd>{agentWorking.length}</dd></div><div><dt><i className="amber" />Waiting externally</dt><dd>{waitingExternal.length}</dd></div><div><dt><i className="red" />Needs your attention</dt><dd>{needsYou.length}</dd></div></dl></div>
        <div className="autonomy-callout"><b>{live.impact.contributions?.agent_percent == null ? "No coordination actions recorded yet" : `${autonomyRate}% agent actions · ${live.impact.contributions.human_percent}% staff actions`}</b><span>A staff-assisted closure may still include extensive agent work. Open a request to see its action-by-action automation percentage.</span></div>
      </section>

      <aside className={`overview-panel decision-detail ${primaryDecision ? "has-decision" : ""}`}>
        {primaryDecision ? <><div className="decision-detail-head"><span>{primaryDecision.ticket_id}</span><b className={`priority-chip ${primaryDecision.priority}`}>{primaryDecision.priority}</b></div><h2>{primaryDecision.subject}</h2><p>{primaryDecision.requester} · {locationName(primaryDecision.location_id)}</p><div className="mini-progress"><i className="done" /><i className="done" /><i className="done" /><i className="current" /><i /></div><h3>Agent summary</h3><ul><li>Loaded resident and apartment context</li><li>Reviewed linked building telemetry</li><li>Applied the autonomy policy</li><li>Prepared the recommended next action</li></ul><div className="recommended-action"><b>Recommended action</b><span>{primaryDecision.status === "needs_approval" ? "Approve qualified technician dispatch and continue automated verification." : "Provide the missing facility answer and reply to the requester."}</span></div><button onClick={() => onReview(primaryDecision)}>{primaryDecision.status === "needs_approval" ? "Review approval" : "Respond to request"}</button></> : <div className="decision-detail-clear"><span>✓</span><h2>No decisions pending</h2><p>No consequential decisions are waiting for Maya.</p></div>}
      </aside>
    </div>

    <section className="overview-panel active-work">
      <div className="overview-panel-head"><div><h2>Recent requests and outcomes</h2><p>Open and resolved requests remain visible here. Select a request to see who handled it.</p></div><span>{active.length} visible</span></div>
      <div className="overview-table"><table><thead><tr><th>Ticket</th><th>Requester</th><th>Category</th><th>Status</th><th>Priority</th><th>Next action</th><th>Updated</th></tr></thead><tbody>{active.map((ticket) => <tr key={ticket.ticket_id} onClick={() => onReview(ticket)}><td><b>{ticket.ticket_id}</b><span>{ticket.subject}</span></td><td>{ticket.requester}<small>{locationName(ticket.location_id)}</small></td><td>{humanize(ticket.kind)}</td><td><em className={`status ${ticket.status}`}>{ticketStatusLabel(ticket.status)}</em></td><td><i className={`priority-dot ${ticket.priority}`} />{humanize(ticket.priority)}</td><td><strong>{nextAction(ticket)}</strong></td><td>{time(ticket.updated_at)}</td></tr>)}</tbody></table>{active.length === 0 && <div className="overview-clear"><span>✓</span><div><b>No requests yet</b><small>New work will appear after a request is submitted from the console.</small></div></div>}</div>
    </section>

    <footer className="overview-impact"><span>Autopilot continuously monitors and resolves requests.</span><b>Agent actions <i>{live.impact.actions_performed}</i></b><b>Verified resolutions <i>{live.impact.verified_resolutions}</i></b><b>Worker capacity <i>{live.agent.worker_count}</i></b><b>Active workflows <i>{live.agent.active_tickets.length}</i></b></footer>
  </section>;
}
