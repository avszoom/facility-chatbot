import type { LiveOperations, Metrics, Ticket } from "./types";
import { humanize } from "./format";

type Props = {
  tickets: Ticket[];
  metrics: Metrics;
  live: LiveOperations;
  onReview: (ticket: Ticket) => void;
};

const locationName = (id: string) => ({
  "BLDG-A-F01-FITNESS": "Fitness Center · Floor 1",
  "BLDG-A-F04-CONF-4B": "Conference Room 4B · Floor 4",
  "BLDG-A-F07-EAST": "East Office Zone · Floor 7",
  "BLDG-A-LOBBY": "Main Lobby · Ground",
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
  const autonomyRate = live.impact.autonomy_rate;
  const primaryDecision = needsYou[0];
  const active = tickets.filter((ticket) => !["resolved", "escalated"].includes(ticket.status)).slice(0, 7);
  const otherOpen = Math.max(0, metrics.active - needsYou.length);

  return <section className="overview-view">
    <section className="overview-kpis">
      <article><span className="overview-icon blue">▣</span><small>Requests received</small><strong>{metrics.received}</strong><em>Current workspace</em></article>
      <article><span className="overview-icon green">✓</span><small>Handled automatically</small><strong>{metrics.autonomous_resolutions}</strong><em>{autonomyRate}% of resolved work</em></article>
      <article><span className="overview-icon violet">⌁</span><small>Agent working</small><strong>{agentWorking.length}</strong><em>Parallel workflows</em></article>
      <article><span className="overview-icon amber">◷</span><small>Waiting externally</small><strong>{waitingExternal.length}</strong><em>Technician or resident</em></article>
      <article><span className="overview-icon red">!</span><small>Needs your attention</small><strong>{needsYou.length}</strong><em>Approval or staff reply</em></article>
      <article><span className="overview-icon green">↻</span><small>Human touches avoided</small><strong>{metrics.human_touches_saved}</strong><em>Updates and coordination</em></article>
    </section>

    <div className="overview-grid">
      <section className="overview-panel decision-list">
        <div className="overview-panel-head"><div><h2>Only {needsYou.length} thing{needsYou.length === 1 ? "" : "s"} need you</h2><p>Autopilot is handling the other {otherOpen} open requests.</p></div><span className="decision-count">{needsYou.length}</span></div>
        {needsYou.length ? needsYou.slice(0, 2).map((ticket) => <button className="decision-row" onClick={() => onReview(ticket)} key={ticket.ticket_id}>
          <span className={`decision-severity ${ticket.priority}`}>{ticket.priority.toUpperCase()}</span>
          <div><b>{ticket.subject}</b><small>{ticket.ticket_id} · {locationName(ticket.location_id)}</small><p>{ticket.status === "needs_approval" ? "Autopilot completed the investigation and needs approval for the consequential next step." : "Autopilot could not complete this safely and routed the exception to you."}</p><em>{nextAction(ticket)} →</em></div>
        </button>) : <div className="overview-clear"><span>✓</span><div><b>Nothing needs your attention</b><small>Autopilot owns every open request.</small></div></div>}
      </section>

      <section className="overview-panel autonomy-panel">
        <div className="overview-panel-head"><div><h2>Autopilot at a glance</h2><p>What the operations service is handling for you</p></div></div>
        <div className="autonomy-chart"><div className="autonomy-ring" style={{ background: `conic-gradient(#38c986 ${autonomyRate * 3.6}deg, #e9eef4 0deg)` }}><span><b>{autonomyRate}%</b><small>autonomy rate</small></span></div><dl><div><dt><i className="green" />Handled automatically</dt><dd>{metrics.autonomous_resolutions}</dd></div><div><dt><i className="violet" />Agent working</dt><dd>{agentWorking.length}</dd></div><div><dt><i className="amber" />Waiting externally</dt><dd>{waitingExternal.length}</dd></div><div><dt><i className="red" />Needs your attention</dt><dd>{needsYou.length}</dd></div></dl></div>
        <div className="autonomy-callout"><b>{autonomyRate}% handled without concierge intervention</b><span>Autopilot keeps routine work moving in the background.</span></div>
      </section>

      <aside className={`overview-panel decision-detail ${primaryDecision ? "has-decision" : ""}`}>
        {primaryDecision ? <><div className="decision-detail-head"><span>{primaryDecision.ticket_id}</span><b className={`priority-chip ${primaryDecision.priority}`}>{primaryDecision.priority}</b></div><h2>{primaryDecision.subject}</h2><p>{primaryDecision.requester} · {locationName(primaryDecision.location_id)}</p><div className="mini-progress"><i className="done" /><i className="done" /><i className="done" /><i className="current" /><i /></div><h3>Agent summary</h3><ul><li>Loaded occupant and location context</li><li>Reviewed linked building telemetry</li><li>Applied the autonomy policy</li><li>Prepared the recommended next action</li></ul><div className="recommended-action"><b>Recommended action</b><span>{primaryDecision.status === "needs_approval" ? "Approve qualified technician dispatch and continue automated verification." : "Provide the missing facility answer and reply to the requester."}</span></div><button onClick={() => onReview(primaryDecision)}>{primaryDecision.status === "needs_approval" ? "Review approval" : "Respond to request"}</button></> : <div className="decision-detail-clear"><span>✓</span><h2>Autopilot has this covered</h2><p>No consequential decisions are waiting for Maya.</p></div>}
      </aside>
    </div>

    <section className="overview-panel active-work">
      <div className="overview-panel-head"><div><h2>Everything else is being handled</h2><p>Live ownership and next action across active tickets</p></div><span>{active.length} visible</span></div>
      <div className="overview-table"><table><thead><tr><th>Ticket</th><th>Requester</th><th>Category</th><th>Status</th><th>Priority</th><th>Next action</th><th>Updated</th></tr></thead><tbody>{active.map((ticket) => <tr key={ticket.ticket_id} onClick={() => onReview(ticket)}><td><b>{ticket.ticket_id}</b><span>{ticket.subject}</span></td><td>{ticket.requester}<small>{locationName(ticket.location_id)}</small></td><td>{humanize(ticket.kind)}</td><td><em className={`status ${ticket.status}`}>{humanize(ticket.status)}</em></td><td><i className={`priority-dot ${ticket.priority}`} />{humanize(ticket.priority)}</td><td><strong>{nextAction(ticket)}</strong></td><td>{time(ticket.updated_at)}</td></tr>)}</tbody></table>{active.length === 0 && <div className="overview-clear"><span>✓</span><div><b>All requests are complete</b><small>New work will appear after a request is submitted from the console.</small></div></div>}</div>
    </section>

    <footer className="overview-impact"><span>Autopilot continuously monitors and resolves requests.</span><b>Agent actions <i>{live.impact.actions_performed}</i></b><b>Verified resolutions <i>{live.impact.verified_resolutions}</i></b><b>Worker capacity <i>{live.agent.worker_count}</i></b><b>Active workflows <i>{live.agent.active_tickets.length}</i></b></footer>
  </section>;
}
