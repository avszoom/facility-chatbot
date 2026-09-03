import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, apiBase } from "./api";
import { humanize } from "./format";
import type { Metrics, Ticket, TicketDetail, TicketEvent, TicketStatus } from "./types";

const emptyMetrics: Metrics = {
  received: 0, active: 0, resolved: 0, autonomous_resolutions: 0,
  needs_approval: 0, escalated: 0, human_touches_saved: 0, verified_closures: 0,
};

const activeStatuses = new Set<TicketStatus>(["new", "triaging", "working", "waiting_technician", "waiting_verification"]);
const stageIndex: Record<TicketStatus, number> = {
  new: 0, triaging: 1, working: 2, needs_approval: 3,
  waiting_technician: 3, waiting_verification: 4, resolved: 5, escalated: 5,
};
const activityCopy: Record<TicketStatus, { title: string; detail: string }> = {
  new: { title: "Request received", detail: "A durable triage job is queued for the operations agent." },
  triaging: { title: "Agent is analyzing the request", detail: "Reviewing intent, location context, safety language, and eligible actions." },
  working: { title: "Agent is executing the plan", detail: "The selected action is being checked against policy before execution." },
  needs_approval: { title: "A human decision is required", detail: "The agent prepared the action and paused at a policy checkpoint." },
  waiting_technician: { title: "Technician work is in progress", detail: "State is saved. The agent will resume automatically when work completes." },
  waiting_verification: { title: "Agent is verifying the outcome", detail: "Fresh operational evidence is being checked before closure." },
  resolved: { title: "Outcome completed", detail: "The request reached a verified or grounded resolution." },
  escalated: { title: "Transferred for operator review", detail: "Automation stopped safely and preserved the full working record." },
};
const eventTone = (event: TicketEvent) => event.event_type.includes("failed") || event.event_type.includes("escalated")
  ? "danger" : event.event_type.includes("approval") ? "approval"
    : event.event_type.includes("verified") || event.event_type.includes("resolved") ? "success" : "neutral";

function LiveWork({ ticket, events }: { ticket: Ticket; events: TicketEvent[] }) {
  const current = activityCopy[ticket.status];
  const active = activeStatuses.has(ticket.status);
  const labels = ["Received", "Analyze", "Act", "Coordinate", "Verify", "Complete"];
  return <section className={`live-work ${active ? "is-live" : ""}`}>
    <div className="live-summary">
      <span className="agent-orb"><i /></span>
      <div><p>{active ? "AGENT WORKING" : "WORKFLOW STATUS"}</p><h3>{current.title}</h3><span>{ticket.waiting_reason || current.detail}</span></div>
      <small>{events.length} recorded events</small>
    </div>
    <div className="workflow-rail">
      {labels.map((label, index) => <div className={index < stageIndex[ticket.status] ? "done" : index === stageIndex[ticket.status] ? "current" : ""} key={label}><i>{index < stageIndex[ticket.status] ? "✓" : index + 1}</i><span>{label}</span></div>)}
    </div>
  </section>;
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [metrics, setMetrics] = useState(emptyMetrics);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [runtime, setRuntime] = useState("connecting");
  const [connection, setConnection] = useState<"live" | "reconnecting">("reconnecting");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [nextTickets, nextMetrics, system] = await Promise.all([api.tickets(), api.metrics(), api.system()]);
      setTickets(nextTickets); setMetrics(nextMetrics); setRuntime(system.providers.agent_runtime); setError("");
      setSelectedId((current) => current || nextTickets[0]?.ticket_id || "");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to reach the operations API"); }
  }, []);

  useEffect(() => {
    void refresh();
    const polling = window.setInterval(() => void refresh(), 600);
    return () => window.clearInterval(polling);
  }, [refresh]);
  useEffect(() => { if (selectedId) void api.ticket(selectedId).then(setDetail).catch(() => setDetail(null)); }, [selectedId, tickets]);
  useEffect(() => {
    const stream = new EventSource(`${apiBase}/api/events`);
    stream.onopen = () => setConnection("live"); stream.onerror = () => setConnection("reconnecting");
    stream.onmessage = () => void refresh();
    return () => stream.close();
  }, [refresh]);

  const operate = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try { await action(); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The operation could not be completed"); }
    finally { setBusy(false); }
  };
  const loadSamples = () => operate(async () => {
    const loaded = await api.loadSampleRequests();
    setSelectedId(loaded[0]?.ticket_id || "");
  });
  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await operate(async () => {
      const ticket = await api.create({
        subject: String(form.get("subject")), description: String(form.get("description")),
        requester: String(form.get("requester")), location_id: String(form.get("location_id")),
      });
      setTickets((current) => [ticket, ...current.filter((item) => item.ticket_id !== ticket.ticket_id)]);
      setSelectedId(ticket.ticket_id); setDetail(await api.ticket(ticket.ticket_id)); setCreating(false);
    });
  };
  const sortedEvents = useMemo(() => [...(detail?.events || [])].reverse(), [detail]);

  return <main>
    <nav>
      <div className="brand"><span>BO</span><div>BuildingOps<small>Autopilot</small></div></div>
      <div className="nav-actions">
        <div className={`runtime ${connection}`}><i /> {connection === "live" ? "Connected" : "Reconnecting"}<small>{runtime}</small></div>
        <button onClick={() => setCreating(true)}>+ Create request</button>
      </div>
    </nav>

    <header>
      <div><p className="eyebrow">OPERATIONS CONTROL CENTER</p><h1>Facility work,<br /><em>continuously handled.</em></h1><p className="lede">Every request is triaged, worked within policy, coordinated across people and systems, and verified before closure.</p></div>
      <div className="workspace-controls"><button disabled={busy} onClick={() => setCreating(true)}>Create facility request</button><button className="ghost" disabled={busy} onClick={loadSamples}>Load sample requests</button><button className="text-button" disabled={busy} onClick={() => operate(() => api.processScheduled())}>Process scheduled work →</button></div>
    </header>

    <section className="metrics">
      {[["Requests received", metrics.received], ["In progress", metrics.active], ["Resolved outcomes", metrics.resolved], ["Human touches saved", metrics.human_touches_saved], ["Verified closures", metrics.verified_closures]].map(([label, value]) => <article key={label}><strong>{value}</strong><span>{label}</span></article>)}
    </section>
    {error && <p className="error">{error}</p>}

    <section className="operations">
      <aside className="inbox">
        <div className="section-title"><div><p className="eyebrow">PRIORITIZED WORK</p><h2>Request queue</h2></div><span>{tickets.length}</span></div>
        <div className="filters"><b>All requests</b><span>Needs approval {metrics.needs_approval}</span><span>Resolved {metrics.resolved}</span></div>
        <div className="ticket-list">{tickets.length === 0 ? <div className="empty-queue"><h3>No open requests</h3><p>Create a request to watch the agent work it in real time.</p><button onClick={() => setCreating(true)}>Create first request</button></div> : tickets.map((ticket) => <button className={`ticket-row ${selectedId === ticket.ticket_id ? "selected" : ""}`} key={ticket.ticket_id} onClick={() => setSelectedId(ticket.ticket_id)}>
          <span className={`priority-dot ${ticket.priority} ${activeStatuses.has(ticket.status) ? "active" : ""}`} />
          <span className="ticket-copy"><small>{ticket.ticket_id} · {ticket.location_id}</small><strong>{ticket.subject}</strong><span>{ticket.waiting_reason || ticket.description}</span></span>
          <span className={`status ${ticket.status}`}>{humanize(ticket.status)}</span>
        </button>)}</div>
      </aside>

      <section className="detail">
        {!detail ? <div className="empty"><span className="empty-icon">↗</span><b>Select a request</b><span>The live working record will appear here.</span></div> : <>
          <div className="detail-head"><div><p className="eyebrow">{detail.ticket.ticket_id} · {humanize(detail.ticket.kind)}</p><h2>{detail.ticket.subject}</h2><p>{detail.ticket.description}</p></div><div className={`outcome ${detail.ticket.status}`}>{humanize(detail.ticket.status)}<small>{detail.ticket.confidence ? `${Math.round(detail.ticket.confidence * 100)}% decision confidence` : "Awaiting analysis"}</small></div></div>
          <div className="context-strip"><span><small>Requester</small>{detail.ticket.requester}</span><span><small>Location</small>{detail.ticket.location_id}</span><span><small>Owner</small>{detail.ticket.assigned_owner}</span>{detail.ticket.safety_flags.length > 0 && <span className="safety"><small>Safety signals</small>{detail.ticket.safety_flags.length} detected</span>}</div>
          <LiveWork ticket={detail.ticket} events={detail.events} />

          {detail.ticket.status === "needs_approval" && <div className="approval-card"><div><p className="eyebrow">OPERATOR DECISION</p><h3>Qualified technician dispatch</h3><p>Investigation is complete. Policy OPS-APPROVAL-010 reserves this consequential action for an authorized operator.</p></div><div><button disabled={busy} onClick={() => operate(() => api.approve(detail.ticket.ticket_id, true))}>Approve dispatch</button><button className="ghost" disabled={busy} onClick={() => operate(() => api.approve(detail.ticket.ticket_id, false))}>Decline</button></div></div>}

          <div className="proof-grid">
            <div className="proof-column"><div className="column-title"><p className="eyebrow">CONTROL & EVIDENCE</p><h3>Actions taken</h3></div>
              {detail.actions.map((action) => <article className="action-card" key={action.action_id}><div><span className={`risk ${action.risk_tier}`}>{humanize(action.risk_tier)}</span><small>{action.policy_rule}</small></div><h4>{humanize(action.action_type)}</h4><p>{action.rationale}</p><div className="change"><span><small>Before</small>{JSON.stringify(action.before_state)}</span><b>→</b><span><small>After</small>{Object.keys(action.after_state).length ? JSON.stringify(action.after_state) : "Awaiting authorization"}</span></div></article>)}
              {detail.work_order && <article className="work-order"><div><span>WORK ORDER</span><b>{detail.work_order.work_order_id}</b></div><h4>{detail.work_order.technician}</h4><p>{detail.work_order.procedure}</p><strong>{humanize(detail.work_order.status)}</strong>{detail.work_order.completion_notes && <small>{detail.work_order.completion_notes}</small>}</article>}
              {!detail.actions.length && <p className="muted">Actions and operational evidence will appear here as the agent works.</p>}
            </div>
            <div className="proof-column timeline"><div className="column-title"><p className="eyebrow">LIVE WORKING RECORD</p><h3>Activity stream <span className="streaming-dot" /></h3></div>{sortedEvents.map((event) => <article key={event.event_id}><i className={eventTone(event)} /><div><span>{humanize(event.event_type)}<small>{event.actor}</small></span><p>{event.summary}</p>{event.event_type === "verification.passed" && <b className="verified">✓ Outcome independently verified</b>}</div></article>)}</div>
          </div>
        </>}
      </section>
    </section>

    {creating && <div className="modal" onMouseDown={() => setCreating(false)}><form onSubmit={create} onMouseDown={(event) => event.stopPropagation()}><div><p className="eyebrow">FACILITY SUPPORT</p><h2>Create a request</h2><p>The operations agent will begin working as soon as you submit.</p><button type="button" className="close" onClick={() => setCreating(false)}>×</button></div><label>Subject<input name="subject" required minLength={3} autoFocus placeholder="What needs attention?" /></label><label>Description<textarea name="description" required minLength={3} placeholder="Describe the question, condition, or issue…" /></label><div className="form-row"><label>Requester<input name="requester" required defaultValue="Building Occupant" /></label><label>Location<select name="location_id" defaultValue="BLDG-A-F04-CONF-4B"><option value="BLDG-A-F01-FITNESS">Fitness center</option><option value="BLDG-A-F04-CONF-4B">Conference Room 4B</option><option value="BLDG-A-F07-EAST">Floor 7 East</option><option value="BLDG-A-LOBBY">Main lobby</option></select></label></div><button disabled={busy}>Submit request</button></form></div>}
  </main>;
}
