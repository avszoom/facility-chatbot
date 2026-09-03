import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, apiBase } from "./api";
import { humanize } from "./format";
import type { Metrics, Ticket, TicketDetail, TicketEvent } from "./types";

const emptyMetrics: Metrics = { received: 0, active: 0, resolved: 0, autonomous_resolutions: 0, needs_approval: 0, escalated: 0, human_touches_saved: 0, verified_closures: 0 };
const eventTone = (event: TicketEvent) => event.event_type.includes("failed") || event.event_type.includes("escalated") ? "danger" : event.event_type.includes("approval") ? "approval" : event.event_type.includes("verified") || event.event_type.includes("resolved") ? "success" : "neutral";

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
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to reach the local API"); }
  }, []);

  useEffect(() => {
    void refresh();
    const polling = window.setInterval(() => void refresh(), 1500);
    return () => window.clearInterval(polling);
  }, [refresh]);
  useEffect(() => { if (selectedId) void api.ticket(selectedId).then(setDetail).catch(() => setDetail(null)); }, [selectedId, tickets]);
  useEffect(() => {
    const events = new EventSource(`${apiBase}/api/events`);
    events.onopen = () => setConnection("live");
    events.onerror = () => setConnection("reconnecting");
    events.onmessage = () => void refresh();
    return () => events.close();
  }, [refresh]);

  const operate = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try { await action(); await refresh(); if (selectedId) setDetail(await api.ticket(selectedId)); }
    finally { setBusy(false); }
  };

  const seed = () => operate(async () => {
    const seeded = await api.seed();
    setSelectedId(seeded.find((ticket) => ticket.ticket_id === "TKT-1003")?.ticket_id || seeded[0]?.ticket_id || "");
  });
  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await operate(async () => {
      const ticket = await api.create({ subject: String(form.get("subject")), description: String(form.get("description")), requester: String(form.get("requester")), location_id: String(form.get("location_id")) });
      setSelectedId(ticket.ticket_id); setCreating(false);
    });
  };
  const sortedEvents = useMemo(() => [...(detail?.events || [])].reverse(), [detail]);

  return <main>
    <nav>
      <div className="brand"><span>BO</span> BuildingOps <small>Autopilot</small></div>
      <div className="nav-actions"><div className={`runtime ${connection}`}><i /> {connection} · {runtime}</div><button className="ghost" onClick={() => setCreating(true)}>+ New ticket</button></div>
    </nav>
    <header>
      <div><p className="eyebrow">AUTONOMOUS FACILITY OPERATIONS</p><h1>Every request,<br /><em>worked to an outcome.</em></h1><p className="lede">Triage, investigation, safe action, long-running work and verified closure—without losing human control.</p></div>
      <div className="demo-controls"><span>Hero scenario</span><button disabled={busy} onClick={seed}>Reset 3-ticket demo</button><button className="ghost" disabled={busy} onClick={() => operate(() => api.advance())}>Advance waiting work →</button></div>
    </header>
    <section className="metrics">
      {[["Requests received", metrics.received], ["Actively worked", metrics.active], ["Outcomes resolved", metrics.resolved], ["Human touches saved", metrics.human_touches_saved], ["Verified closures", metrics.verified_closures]].map(([label, value]) => <article key={label}><strong>{value}</strong><span>{label}</span></article>)}
    </section>
    {error && <p className="error">Start the API on port 8000. {error}</p>}
    <section className="operations">
      <aside className="inbox">
        <div className="section-title"><div><p className="eyebrow">PRIORITIZED INBOX</p><h2>Agent queue</h2></div><span>{tickets.length}</span></div>
        <div className="filters"><b>All</b><span>Needs approval {metrics.needs_approval}</span><span>Resolved {metrics.resolved}</span></div>
        <div className="ticket-list">{tickets.map((ticket) => <button className={`ticket-row ${selectedId === ticket.ticket_id ? "selected" : ""}`} key={ticket.ticket_id} onClick={() => setSelectedId(ticket.ticket_id)}>
          <span className={`priority-dot ${ticket.priority}`} /><span className="ticket-copy"><small>{ticket.ticket_id} · {ticket.location_id}</small><strong>{ticket.subject}</strong><span>{ticket.waiting_reason || ticket.description}</span></span><span className={`status ${ticket.status}`}>{humanize(ticket.status)}</span>
        </button>)}</div>
      </aside>
      <section className="detail">
        {!detail ? <div className="empty"><b>Select a ticket</b><span>Its evidence, decisions, and outcomes appear here.</span></div> : <>
          <div className="detail-head"><div><p className="eyebrow">{detail.ticket.ticket_id} · {humanize(detail.ticket.kind)}</p><h2>{detail.ticket.subject}</h2><p>{detail.ticket.description}</p></div><div className={`outcome ${detail.ticket.status}`}>{humanize(detail.ticket.status)}<small>{Math.round(detail.ticket.confidence * 100)}% confidence</small></div></div>
          <div className="context-strip"><span><small>Requester</small>{detail.ticket.requester}</span><span><small>Location</small>{detail.ticket.location_id}</span><span><small>Owner</small>{detail.ticket.assigned_owner}</span></div>
          {detail.ticket.waiting_reason && <div className="waiting"><span className="pulse" /><div><b>Workflow paused durably</b><p>{detail.ticket.waiting_reason}</p></div><small>No request is held open. The worker will resume from the saved job.</small></div>}
          {detail.ticket.status === "needs_approval" && <div className="approval-card"><div><p className="eyebrow">HUMAN CHECKPOINT</p><h3>Qualified technician dispatch</h3><p>The agent investigated and prepared the action, but policy OPS-APPROVAL-010 reserves this consequential decision for you.</p></div><div><button disabled={busy} onClick={() => operate(() => api.approve(detail.ticket.ticket_id, true))}>Approve dispatch</button><button className="ghost" disabled={busy} onClick={() => operate(() => api.approve(detail.ticket.ticket_id, false))}>Decline</button></div></div>}
          <div className="proof-grid">
            <div className="proof-column"><div className="column-title"><p className="eyebrow">AGENT ACTIVITY</p><h3>Decision & audit trail</h3></div>
              {detail.actions.map((action) => <article className="action-card" key={action.action_id}><div><span className={`risk ${action.risk_tier}`}>{humanize(action.risk_tier)}</span><small>{action.policy_rule}</small></div><h4>{humanize(action.action_type)}</h4><p>{action.rationale}</p><div className="change"><span><small>Before</small>{JSON.stringify(action.before_state)}</span><b>→</b><span><small>After</small>{Object.keys(action.after_state).length ? JSON.stringify(action.after_state) : "Awaiting approval"}</span></div></article>)}
              {detail.work_order && <article className="work-order"><div><span>WORK ORDER</span><b>{detail.work_order.work_order_id}</b></div><h4>{detail.work_order.technician}</h4><p>{detail.work_order.procedure}</p><strong>{humanize(detail.work_order.status)}</strong>{detail.work_order.completion_notes && <small>{detail.work_order.completion_notes}</small>}</article>}
              {!detail.actions.length && <p className="muted">No physical or system change was needed for this request.</p>}
            </div>
            <div className="proof-column timeline"><div className="column-title"><p className="eyebrow">LIVE TIMELINE</p><h3>What happened</h3></div>{sortedEvents.map((event) => <article key={event.event_id}><i className={eventTone(event)} /><div><span>{humanize(event.event_type)}<small>{event.actor}</small></span><p>{event.summary}</p>{event.event_type === "verification.passed" && <b className="verified">✓ Outcome independently verified</b>}</div></article>)}</div>
          </div>
        </>}
      </section>
    </section>
    {creating && <div className="modal" onMouseDown={() => setCreating(false)}><form onSubmit={create} onMouseDown={(event) => event.stopPropagation()}><div><p className="eyebrow">NEW BUILDING REQUEST</p><h2>Create a ticket</h2><button type="button" className="close" onClick={() => setCreating(false)}>×</button></div><label>Subject<input name="subject" required minLength={3} placeholder="Conference room is too warm" /></label><label>Description<textarea name="description" required minLength={3} placeholder="Tell the agent what is happening…" /></label><div className="form-row"><label>Your name<input name="requester" required defaultValue="Demo Occupant" /></label><label>Location<select name="location_id" defaultValue="BLDG-A-F04-CONF-4B"><option value="BLDG-A-F01-FITNESS">Fitness center</option><option value="BLDG-A-F04-CONF-4B">Conference Room 4B</option><option value="BLDG-A-F07-EAST">Floor 7 East</option></select></label></div><button disabled={busy}>Submit to Autopilot</button></form></div>}
  </main>;
}
