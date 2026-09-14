import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { ticketContributions } from "./automation";
import { humanize, ticketStatusLabel } from "./format";
import type { LiveOperations, Ticket, TicketDetail } from "./types";
import "./mission-control.css";
import { sortByProgress, progressStage } from "./live-progress";
import { LiveWork } from "./LiveWork";
import { singleFlightRefresh } from "./live-refresh";
import { SensorEvidence } from "./SensorEvidence";

const roles = ["Intake & Safety Agent", "Building Context Agent", "Resident Knowledge Agent", "Sensor Intelligence Agent", "Maintenance Intelligence Agent", "Verification Agent"];
const names = ["Intake & safety", "Building context", "Resident knowledge", "Sensor intelligence", "Maintenance history", "Verification"];
const time = (value: string) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
export function pipelineIndex(ticket: Ticket): number {
  return progressStage(ticket);
}
export function Pipeline({ ticket, running = false, eventTypes = [] }: { ticket: Ticket; running?: boolean; eventTypes?: string[] }) {
  const index = progressStage(ticket, eventTypes);
  const blocked = ["needs_approval", "escalated"].includes(ticket.status);
  return <ol className="mc-pipeline" aria-label={`Request pipeline: ${ticketStatusLabel(ticket.status)}`}>
    {["Received", "Investigate", "Act", "Verify", "Resolved"].map((label, i) => {
      const missingVerification = i === 3 && ticket.status === "resolved" && !eventTypes.some(t => ["verification.passed", "coordinator.completion_requested"].includes(t));
      const passed = !missingVerification && (i < index || ticket.status === "resolved");
      return <li key={label} className={`${passed ? "passed" : ""} ${i === index ? "current" : ""} ${i === index && blocked ? "blocked" : ""} ${i === index && running && !blocked ? "executing" : ""}`}><span>{missingVerification ? "—" : passed ? "✓" : i + 1}</span><small>{missingVerification ? "Not verified" : label}</small></li>;
    })}
  </ol>;
}

function Investigation({ detail, live, onReview }: { detail: TicketDetail; live: LiveOperations; onReview: (ticket: Ticket) => void }) {
  const { ticket, events, workflow } = detail;
  const delivery = live.agent.deliveries?.find(d => d.ticket_id === ticket.ticket_id && d.status === "processing");
  const activeRole = delivery?.role || (delivery ? "Operations Coordinator" : null);
  const [chosen, setChosen] = useState<string | null>(null);
  const selectedEvents = chosen ? events.filter(e => e.actor === chosen || e.payload.specialist_role === chosen) : events;
  const c = ticketContributions(events);
  const sensorIds = [...new Set(events.flatMap(e => Array.isArray(e.payload.evidence_sensor_ids) ? e.payload.evidence_sensor_ids.filter((id): id is string => typeof id === "string") : []))].filter(id => live.building.sensors[id]).slice(0, 3);
  const resolved = ticket.status === "resolved";
  const dispatch = detail.actions.find(action => action.action_type.startsWith("dispatch_"));
  return <section className="mc-investigation" aria-label="Selected request investigation">
    <header><div><span className="mc-eyebrow">INSIDE THE WORKFLOW · {workflow?.workflow_id || ticket.ticket_id}</span><h2>{ticket.subject}</h2><p>{ticket.requester} · {humanize(ticket.location_id.replace("BLDG-A-", ""))}</p></div><button className="mc-detail-link" onClick={() => onReview(ticket)}>Open request & actions ↗</button></header>
    <div className="mc-detail-stats"><span><b>{c.agent.length}</b> agent actions</span><span><b>{c.human.length}</b> staff actions</span><span><b>{c.percentage == null ? "—" : `${c.percentage}%`}</b> coordination automated</span><span className="mc-state">{ticketStatusLabel(ticket.status)}</span></div>
    <div className="mc-investigation-grid"><div className="mc-map"><div className="mc-map-title"><h3>One coordinator. The right specialists.</h3><small>Solid connections = recorded reports · animation = executing now</small></div>
      <button className={`mc-coordinator ${activeRole === "Operations Coordinator" ? "executing" : ""}`} onClick={() => setChosen(null)}><span className="mc-node-icon">◈</span><div><b>Operations Coordinator</b><small>{resolved ? "Workflow closed · history preserved" : activeRole === "Operations Coordinator" ? "Reviewing evidence & choosing next step" : ticket.waiting_reason || "Waiting for durable handoff"}</small></div><em>{workflow ? `Checkpoint ${workflow.version}` : "Queued"}</em></button>
      <div className="mc-specialists"><svg className="mc-graph-edges" viewBox="0 0 600 291" preserveAspectRatio="none" aria-hidden="true">{roles.map((role, i) => <path key={role} className={events.some(e => e.event_type === "specialist.completed" && e.actor === role) ? "reported" : ""} d={i < 3 ? `M300 0 H${100 + i * 200} V25` : `M300 0 H2 V158 H${100 + (i - 3) * 200} V169`} />)}</svg>{roles.map((role, i) => {
        const reports = events.filter(e => e.event_type === "specialist.completed" && e.actor === role);
        const delegated = events.some(e => e.event_type === "coordinator.delegated" && e.payload.specialist_role === role);
        const running = activeRole === role;
        const state = running ? "executing" : reports.length ? "reported" : delegated && !resolved && ticket.status !== "escalated" ? "queued" : "unused";
        return <button key={role} className={`mc-specialist ${state} ${chosen === role ? "selected" : ""}`} onClick={() => setChosen(chosen === role ? null : role)}><span className="mc-node-icon">{reports.length ? "✓" : String(i + 1).padStart(2, "0")}</span><b>{names[i]}</b><small>{running ? "Working now" : reports.length ? `${reports.length} report recorded` : state === "queued" ? "Handoff queued" : "No recorded run"}</small></button>;
      })}</div>
      <div className={`mc-outcome ${resolved ? "resolved" : ""}`}><b>{resolved ? "Resolution recorded" : ticket.status === "needs_approval" ? "Human checkpoint · dispatch approval" : ticket.status === "waiting_technician" ? "Technician assigned · request remains open" : ticket.status === "escalated" ? "Workflow needs review" : "Next outcome"}</b><p>{events.filter(e => ["ticket.resolved", "approval.requested", "work_order.created", "ticket.escalated"].includes(e.event_type)).at(-1)?.summary || ticket.waiting_reason || "Evidence collection is in progress."}</p></div>
      {dispatch && !detail.work_order && <div className="mc-work-order"><span className="mc-eyebrow">TECHNICIAN BRIEF · {dispatch.status}</span><h3>{humanize(String(dispatch.requested.trade || "Facilities"))} inspection</h3><p><b>Working diagnosis:</b> {String(dispatch.requested.diagnosis || "Requires on-site confirmation")}</p><p><b>Evidence:</b> {Array.isArray(dispatch.requested.evidence_sensor_ids) ? dispatch.requested.evidence_sensor_ids.join(", ") : "See investigation reports"}</p><p><b>Procedure:</b> {String(dispatch.requested.procedure || "Pending")}</p><small>Dispatch is subject to {dispatch.policy_rule}. No physical repair has been performed.</small></div>}
      {detail.work_order && <div className="mc-work-order"><span className="mc-eyebrow">TECHNICIAN WORK ORDER · {detail.work_order.work_order_id}</span><h3>{detail.work_order.trade} · {detail.work_order.technician}</h3><p style={{whiteSpace:"pre-line"}}>{detail.work_order.procedure}</p><small>{detail.work_order.status} · Due {time(detail.work_order.due_at)}</small></div>}
      {sensorIds.length > 0 && <div className="mc-sensor-strip">{sensorIds.map(id => {
        const sensor = live.building.sensors[id];
        const history = live.building.sensor_history[id] || [];
        const values = history.map(h => h.numeric_value);
        const low = Math.min(...values), high = Math.max(...values);
        const points = values.map((v, i) => `${i / Math.max(1, values.length - 1) * 160},${40 - (v - low) / (high - low || 1) * 32}`).join(" ");
        return <article key={id} className={sensor.state.toLowerCase()}><small>{id} · live now</small><b>{sensor.value}</b><span>{sensor.state} · target {sensor.target}</span>{values.length > 1 && <svg viewBox="0 0 160 45" role="img" aria-label={`${id}: recent sensor readings`}><polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" /></svg>}<small>Recent readings · relative scale</small></article>;
      })}</div>}
      <SensorEvidence detail={detail} live={live} />
      {detail.actions.map(a => <details className="mc-action" key={a.action_id}><summary>{humanize(a.action_type)} · {a.status} · {a.policy_rule}</summary><p>{a.rationale}</p><div><pre>{JSON.stringify(a.before_state, null, 2)}</pre><span>→</span><pre>{JSON.stringify(a.after_state, null, 2)}</pre></div></details>)}
    </div><aside className="mc-evidence"><h3>{chosen ? names[roles.indexOf(chosen)] : "Live evidence trail"}</h3><small>{chosen ? "Select again to see all activity" : "Recorded findings, actions and resident updates"}</small><div>{[...selectedEvents].reverse().map(e => <article key={e.event_id}><span>{time(e.created_at)}</span><b>{e.actor}</b><p>{e.summary}</p><small>{humanize(e.event_type.replaceAll(".", " "))}</small></article>)}</div></aside></div>
  </section>;
}

export function MissionControl({ live, tickets, onReview }: { live: LiveOperations; tickets: Ticket[]; onReview: (ticket: Ticket) => void }) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [error, setError] = useState("");
  const opener = useRef<HTMLButtonElement | null>(null);
  const closeDetail = () => { setSelected(null); opener.current?.focus(); };
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") { setSelected(null); opener.current?.focus(); } };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setDetail(null); setError("");
    const refresh = singleFlightRefresh(async () => { try { const result = await api.ticket(selected); if (!cancelled) { setDetail(result); setError(""); } } catch { if (!cancelled) setError("Unable to refresh this workflow. Showing the last available history."); } });
    void refresh(); const timer = setInterval(refresh, 1000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [selected]);
  const running = new Set((live.agent.deliveries || []).filter(d => d.status === "processing").map(d => d.ticket_id));
  const groups = { all: tickets, open: tickets.filter(t => t.status !== "resolved"), attention: tickets.filter(t => ["escalated", "needs_approval"].includes(t.status)), resolved: tickets.filter(t => t.status === "resolved") };
  const visible = sortByProgress(groups[filter as keyof typeof groups].filter(t => `${t.subject} ${t.ticket_id} ${t.location_id}`.toLowerCase().includes(query.toLowerCase())), live);
  return <section className="mc-workspace"><header className="mc-heading"><div><span className="mc-eyebrow">RESIDENT SERVICES / LIVE OPERATIONS</span><h2>From request to resolution.</h2><p>Follow the work. Open any request to see the agents, evidence and human checkpoints.</p></div><div className="mc-live-badge"><i />{live.agent.deliveries ? running.size : "—"} executing <span>/ {live.agent.worker_count} workers</span></div></header>
    <LiveWork live={live} tickets={tickets} onSelect={setSelected} />
    <p className="mc-sort-note">Most progressed first · ties use specialist reports, completed actions, then latest update. Select any request for its agent graph.</p>
    <div className="mc-toolbar"><nav aria-label="Workflow filters">{Object.entries(groups).map(([key, rows]) => <button key={key} onClick={() => setFilter(key)} className={filter === key ? "selected" : ""}>{({all:"All requests",open:"In progress",attention:"Needs attention",resolved:"Resolved"})[key]} <b>{rows.length}</b></button>)}</nav><input aria-label="Search workflows" placeholder="Search request or location…" value={query} onChange={e => setQuery(e.target.value)} /></div>
    <div className="mc-worklist"><div className="mc-column-labels"><span>RESIDENT REQUEST</span><span>RESOLUTION PIPELINE</span><span>OWNERSHIP</span></div>{visible.map(t => {
      const p = live.agent.ticket_progress?.[t.ticket_id];
      const attention = ["needs_approval", "escalated"].includes(t.status);
      return <button key={t.ticket_id} className={`mc-request ${selected === t.ticket_id ? "selected" : ""}`} aria-expanded={selected === t.ticket_id} onClick={event => { opener.current = event.currentTarget; setSelected(selected === t.ticket_id ? null : t.ticket_id); }}><div className="mc-request-name"><span className={`mc-kind ${t.kind}`}>{t.kind === "unknown" ? "Classifying" : humanize(t.kind)}</span><b>{t.subject}</b><small>{t.ticket_id} · {t.requester}</small></div><div><Pipeline ticket={t} running={running.has(t.ticket_id)} eventTypes={p?.event_types} /><p className="mc-next">{t.status === "resolved" ? "Closed · select to review the outcome" : t.waiting_reason || (attention ? "Review the recorded error or decision" : "Waiting for intake")}</p></div><div className="mc-ownership"><strong className={attention ? "attention" : ""}>{attention ? "Your attention" : t.status === "resolved" ? "Resolved" : t.status === "waiting_technician" ? "Technician working" : running.has(t.ticket_id) ? "Agent working" : "Queued / scheduled"}</strong><small>{p ? `${p.contributions.agent_actions} agent · ${p.contributions.human_actions} staff actions` : "Loading action counts"}</small><span>Explore workflow {selected === t.ticket_id ? "−" : "↗"}</span></div></button>;
    })}{!visible.length && <div className="mc-empty">No requests here yet. Create a resident request to follow its journey.</div>}</div>
    {selected && <div className="mc-overlay"><section className="mc-selected" role="dialog" aria-modal="true" aria-label="Workflow detail" onKeyDown={event => { if (event.key !== "Tab") return; const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button, summary, input, [tabindex='0']")).filter(el => el.getClientRects().length); const first = items[0], last = items.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } }}><div className="mc-drawer-bar"><span>WORKFLOW EXPLORER</span><button autoFocus onClick={closeDetail}>Close ×</button></div>{error && <p role="alert">{error}</p>}{detail ? <Investigation key={selected} detail={detail} live={live} onReview={onReview} /> : <p>Loading saved workflow…</p>}</section></div>}
    <details className="mc-diagnostics"><summary>Service diagnostics · {live.messaging.dead_letters} failed deliveries</summary><p>{live.messaging.pending} pending · {live.messaging.processing} leased · {live.messaging.retrying} retrying. These are message counts, not request counts.</p><p>{live.agent.runtime} · {live.agent.model}. Sensor readings and technician work are simulated locally.</p></details>
  </section>;
}
