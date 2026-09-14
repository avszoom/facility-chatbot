import { MissionControl } from "./MissionControl";
import { singleFlightRefresh } from "./live-refresh";
import { RequestSummary } from "./RequestSummary";
import { TicketAutomation } from "./TicketAutomation";
import { FormEvent, lazy, Suspense, useEffect, useMemo, useState } from "react";
import { api, apiBase } from "./api";
import { floors, sensors, totalCapacity, totalOccupancy } from "./facility";
import { humanize, ticketStatusLabel } from "./format";
import { GeneratorView } from "./GeneratorView";
import { OverviewView } from "./OverviewView";
import type { CustomRequestInput, LiveOperations, Metrics, Ticket, TicketDetail, TicketEvent, TicketStatus } from "./types";

type View = "overview" | "requests" | "agent" | "generator" | "tickets" | "building" | "people";
type Resident = { name: string; initials: string; role: string; home: string; floor: string; email: string; phone: string; access: string };
const BuildingScene = lazy(() => import("./BuildingScene").then((module) => ({ default: module.BuildingScene })));

const residents: Record<string, Resident> = {
  "Priya Shah": { name: "Priya Shah", initials: "PS", role: "Resident", home: "Apartment 5E", floor: "Floor 5 · Apartment 5E", email: "priya.shah@northstar.example", phone: "+1 212 555 0148", access: "Resident · 24/7 + amenities" },
  "Marcus Lee": { name: "Marcus Lee", initials: "ML", role: "Resident", home: "Apartment 4B", floor: "Floor 4 · Apartment 4B", email: "marcus.lee@northstar.example", phone: "+1 212 555 0162", access: "Resident · 24/7 + amenities" },
  "Elena Garcia": { name: "Elena Garcia", initials: "EG", role: "Resident council", home: "Apartment 7E", floor: "Floor 7 · Apartment 7E", email: "elena.garcia@northstar.example", phone: "+1 212 555 0191", access: "Resident · council access" },
  "Building Resident": { name: "Building Resident", initials: "BR", role: "Registered resident", home: "Northstar Residences", floor: "Residence on file", email: "resident@northstar.example", phone: "+1 212 555 0100", access: "Standard resident access" },
};

const locationDirectory = {
  "BLDG-A-F02-FITNESS": { name: "Fitness Center", floor: "Floor 2", zone: "Resident amenity · Z-2F", occupancy: "18 / 40", sensor: "AIR-02-01", reading: "512 ppm", state: "Normal" },
  "BLDG-A-F04-APT-4B": { name: "Apartment 4B", floor: "Floor 4", zone: "Residence · 4B", occupancy: "2 residents", sensor: "TMP-04-01", reading: "72.7°F", state: "Normal" },
  "BLDG-A-F04-CONF-4B": { name: "Apartment 4B", floor: "Floor 4", zone: "Residence · 4B", occupancy: "2 residents", sensor: "TMP-04-01", reading: "72.7°F", state: "Normal" },
  "BLDG-A-F07-EAST": { name: "East Residential Wing", floor: "Floor 7", zone: "Apartments 701–709", occupancy: "24 residents", sensor: "ELEC-7A", reading: "126.4°F", state: "Alert" },
  "BLDG-A-LOBBY": { name: "Main Lobby & Concierge", floor: "Floor 1", zone: "Resident services · Z-1L", occupancy: "23 people", sensor: "OCC-01-01", reading: "23 present", state: "Normal" },
};

function locationIdForSpace(floor: number, room: string) {
  if (floor === 1 && room === "Main lobby") return "BLDG-A-LOBBY";
  if (floor === 2 && room === "Fitness center") return "BLDG-A-F02-FITNESS";
  if (floor === 4 && room === "Apartment 4B") return "BLDG-A-F04-APT-4B";
  if (floor === 7 && room === "East residential wing") return "BLDG-A-F07-EAST";
  const roomCode = room.toUpperCase().replaceAll("&", "AND").replace(/[^A-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `BLDG-A-F${String(floor).padStart(2, "0")}-${roomCode}`;
}

const emptyMetrics: Metrics = { received: 0, active: 0, resolved: 0, autonomous_resolutions: 0, needs_approval: 0, escalated: 0, human_touches_saved: 0, verified_closures: 0 };
const emptyLive: LiveOperations = { simulation: { status: "paused", running: false, sequence: 0, issues_generated: 0, last_tick: null, next_tick: new Date().toISOString(), interval_seconds: 45, scenario_count: 10, scenario_types: { enquiry: 7, service_request: 1, incident: 2 }, last_event: null }, building: { assets: {}, history: {}, sensors: {}, sensor_history: {}, maintenance_history: [], health: { total: 0, normal: 0, warning: 0, critical: 0, monitoring: "autonomous" }, sensor_overrides: {}, active_conditions: {}, last_sensor_tick: null, updated_at: null }, agent: { status: "connecting", runtime: "local", provider: "starting", model: "starting", real_model: false, coordinator_role: "Operations Coordinator", specialist_roles: [], worker_count: 3, active_executions: 0, queued_tasks: 0, active_tickets: [], workflow_states: {} }, messaging: { broker: "SQLite durable pub/sub", topics: 0, pending: 0, processing: 0, completed: 0, retrying: 0, dead_letters: 0, delivery: "at_least_once", idempotent_consumers: true }, recent_events: [], impact: { actions_performed: 0, issues_resolved: 0, resolved_autonomously: 0, needs_user: 0, human_touches_saved: 0, autonomy_rate: 100, verified_resolutions: 0, waiting_external: 0 } };
const activeStatuses = new Set<TicketStatus>(["new", "triaging", "working", "waiting_technician", "waiting_verification"]);
const stageIndex: Record<TicketStatus, number> = { new: 0, triaging: 1, working: 2, needs_approval: 3, waiting_technician: 3, waiting_verification: 4, resolved: 5, escalated: 5 };
const activityCopy: Record<TicketStatus, string> = { new: "Queued for agent pickup", triaging: "Reading the email and checking context", working: "Executing the selected plan", needs_approval: "Waiting for your approval", waiting_technician: "Technician work is in progress", waiting_verification: "Checking fresh sensor evidence", resolved: "Request completed", escalated: "Transferred for staff review" };
const initials = (name: string) => name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
const ticketTime = (value: string) => new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(value));
const eventTone = (event: TicketEvent) => event.event_type.includes("failed") || event.event_type.includes("escalated") ? "danger" : event.event_type.includes("approval") ? "attention" : event.event_type.includes("verified") || event.event_type.includes("resolved") ? "success" : "neutral";

function residentFor(ticket: Ticket): Resident {
  return residents[ticket.requester] || { name: ticket.requester, initials: initials(ticket.requester), role: "Resident or guest", home: "Residence not linked", floor: ticket.location_id, email: `${ticket.requester.toLowerCase().replaceAll(" ", ".")}@resident.example`, phone: "Not provided", access: "Concierge verification required" };
}
function locationFor(ticket: Ticket, live?: LiveOperations) {
  const condition = live?.building.active_conditions[ticket.ticket_id];
  const alarm = condition && live ? live.building.sensors[condition.sensor_id] || live.building.sensor_overrides[condition.sensor_id] : null;
  if (alarm && condition) return { name: alarm.area, floor: `Floor ${alarm.floor}`, zone: `Live condition · ${condition.condition.replaceAll("_", " ")}`, occupancy: "Live zone", sensor: alarm.id, reading: alarm.value, state: alarm.state === "Normal" ? "Normal" : "Alert" };
  const known = locationDirectory[ticket.location_id as keyof typeof locationDirectory];
  if (known) return known;
  const floorNumber = Number(ticket.location_id.match(/F(\d{2})/)?.[1]);
  const areaCode = ticket.location_id.match(/F\d{2}-(.+)$/)?.[1] || ticket.location_id.split("-").at(-1) || "Building A";
  const name = areaCode.toLowerCase().split("-").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ");
  return { name, floor: floorNumber ? `Floor ${floorNumber}` : "Northstar Residences", zone: "Mapped residential zone", occupancy: "Live zone", sensor: "No active alarm", reading: "Normal", state: "Normal" };
}

function AgentProgress({ ticket }: { ticket: Ticket }) {
  const labels = ["Received", "Analyze", "Act", "Coordinate", "Verify", "Complete"];
  const current = stageIndex[ticket.status];
  return <div className="agent-progress"><div className="agent-now"><span className={activeStatuses.has(ticket.status) ? "pulse" : "complete-mark"}>AI</span><div><b>{activityCopy[ticket.status]}</b><small>Facility Operations Agent · {ticketStatusLabel(ticket.status)}</small></div></div><div className="progress-track">{labels.map((label, index) => <div className={index < current ? "done" : index === current ? "current" : ""} key={label}><i>{index < current ? "✓" : index + 1}</i><span>{label}</span></div>)}</div></div>;
}

function AppShell({ view, setView, metrics, children }: { view: View; setView: (view: View) => void; metrics: Metrics; children: React.ReactNode }) {
  const attentionCount = metrics.needs_approval + metrics.escalated;
  const navigation: Array<{ id: View; icon: string; label: string }> = [
    { id: "overview", icon: "⌂", label: "Overview" },
    { id: "requests", icon: "✉", label: "Requests" },
    { id: "building", icon: "▥", label: "Building" },
    { id: "agent", icon: "◉", label: "Agent activity" },
  ];
  return <div className="app-shell"><aside className="app-nav"><div className="app-logo"><span>BO</span><div>BuildingOps<small>Residential Autopilot</small></div></div><nav aria-label="Primary navigation">{navigation.map((item) => <button className={`${(view === item.id || (item.id === "requests" && view === "tickets") || (item.id === "building" && view === "people") || (item.id === "agent" && view === "generator")) ? "active" : ""} ${item.id === "generator" ? "generator-nav" : ""}`} onClick={() => setView(item.id)} key={item.id}><i>{item.icon}</i><span>{item.label}</span>{item.id === "overview" && attentionCount > 0 && <b className="attention-badge">{attentionCount}</b>}</button>)}</nav><div className="nav-status"><span /><div><b>Autopilot running</b><small>Residential operations healthy</small></div></div><div className="user-card"><span>MR</span><div><b>Maya Roberts</b><small>Concierge · Northstar Residences</small></div></div></aside><div className={`app-body ${view === "building" ? "building-mode" : view === "agent" || view === "generator" ? "agent-mode" : ""}`}>{children}</div></div>;
}

function Topbar({ view, connection, onCreate }: { view: View; connection: string; onCreate: () => void }) {
  const titles = { overview: ["Good morning, Maya", "BuildingOps Autopilot is handling resident services in the background."], requests: ["Resident requests", "Review incoming messages and agent ownership"], agent: ["Agent activity", "Inspect durable coordinator loops, specialist handoffs and outcomes"], generator: ["Request generator", "Control resident requests and building conditions"], tickets: ["Tickets", "Track all work while Autopilot owns the routine queue"], building: ["Residential digital twin", "Ten floors, apartments, amenities, assets and sensor conditions"], people: ["Resident directory", "Households, apartments, access and service context"] };
  return <header className={`topbar ${view === "overview" ? "overview-topbar" : ""}`}><div><p>{view === "overview" ? "NORTHSTAR RESIDENCES · OPERATIONS" : "Northstar Residences · New York"}</p><h1>{titles[view][0]}{view === "overview" && <span className="wave"> ◡̈</span>}</h1><span>{titles[view][1]}</span></div><div className="top-actions"><span className={`connection ${connection}`}><i />{connection === "live" ? "Autopilot running" : "Reconnecting"}</span><button className="icon-button" aria-label="Notifications">◉</button><button onClick={onCreate}>＋ New request</button></div></header>;
}

function MailPreview({ ticket, events }: { ticket: Ticket; events: TicketEvent[] }) {
  const message = [...events].reverse().find((event) => ["approval.requested", "message.sent", "staff.response_sent"].includes(event.event_type));
  const requiresAction = ["needs_approval", "escalated"].includes(ticket.status);
  const staffReply = message?.event_type === "staff.response_sent";
  return <section className={`mail-preview ${requiresAction ? "requires-action" : ""}`}><div className="panel-heading"><div><p>SIMULATED EMAIL</p><h3>{requiresAction ? "Action required" : staffReply ? "Staff reply delivered" : message ? "Latest agent update" : "No email sent yet"}</h3></div><span>Not sent externally</span></div>{message ? <><div className="mail-meta"><span className="agent-avatar">{staffReply ? "MR" : "AI"}</span><div><b>{staffReply ? "Maya Roberts" : "BuildingOps Agent"}</b><small>To: {staffReply ? ticket.requester : "Maya Roberts · Front Desk"}</small></div><time>{ticketTime(message.created_at)}</time></div><strong>{requiresAction ? `Attention needed · ${ticket.ticket_id}` : `${ticket.ticket_id} · Request update`}</strong><p>{message.summary}</p></> : <p className="placeholder-copy">The agent will create an email here when it needs a decision or has a meaningful update.</p>}</section>;
}

function StaffResponseBox({ requester, busy, onRespond }: { requester: string; busy: boolean; onRespond: (response: string) => void }) {
  const [response, setResponse] = useState("");
  return <form className="staff-response" onSubmit={(event) => { event.preventDefault(); onRespond(response.trim()); }}><div><span>!</span><div><b>Facility knowledge is needed</b><small>The agent did not find an authoritative answer. Reply as facility staff; this records the action, sends a simulated message to {requester}, and resolves the request.</small></div></div><textarea value={response} onChange={(event) => setResponse(event.target.value)} minLength={3} required placeholder="Enter the authoritative answer for the requester…" /><div className="staff-response-actions"><small>This reply becomes part of the ticket audit trail.</small><button disabled={busy || response.trim().length < 3}>Send response &amp; resolve</button></div></form>;
}

type InboxProps = { tickets: Ticket[]; metrics: Metrics; live: LiveOperations; selectedId: string; detail: TicketDetail | null; busy: boolean; onSelect: (id: string) => void; onCreate: () => void; onLoad: () => void; onProcess: () => void; onApprove: (approved: boolean) => void; onRespond: (response: string) => void };
function InboxView({ tickets, metrics, live, selectedId, detail, busy, onSelect, onCreate, onLoad, onProcess, onApprove, onRespond }: InboxProps) {
  const [filter, setFilter] = useState<"all" | "open" | "attention" | "resolved">("all");
  const sortedEvents = useMemo(() => [...(detail?.events || [])].reverse(), [detail]);
  const occupant = detail ? residentFor(detail.ticket) : null;
  const location = detail ? locationFor(detail.ticket, live) : null;
  const attentionCount = metrics.needs_approval + metrics.escalated;
  const filteredTickets = tickets.filter((ticket) => filter === "all" || (filter === "resolved" && ticket.status === "resolved") || (filter === "open" && ticket.status !== "resolved") || (filter === "attention" && ["needs_approval", "escalated"].includes(ticket.status)));
  return <>
    <section className="workdesk"><aside className="mailbox"><div className="mailbox-head"><div><h2>Requests</h2><span>{tickets.length} conversations</span></div><button className="mini-action" onClick={onCreate}>＋</button></div><div className="mailbox-tools"><button className={filter === "all" ? "selected" : ""} onClick={() => setFilter("all")}>All</button><button className={filter === "open" ? "selected" : ""} onClick={() => setFilter("open")}>Open <b>{metrics.active}</b></button><button className={filter === "attention" ? "selected" : ""} onClick={() => setFilter("attention")}>Needs attention <b>{attentionCount}</b></button><button className={filter === "resolved" ? "selected" : ""} onClick={() => setFilter("resolved")}>Resolved <b>{metrics.resolved}</b></button></div><div className="mail-list">{filteredTickets.length ? filteredTickets.map((ticket) => <button className={`mail-row ${selectedId === ticket.ticket_id ? "selected" : ""}`} onClick={() => onSelect(ticket.ticket_id)} key={ticket.ticket_id}><span className={`sender-avatar priority-${ticket.priority}`}>{initials(ticket.requester)}</span><span className="mail-copy"><span><b>{ticket.requester}</b><time>{ticketTime(ticket.updated_at)}</time></span><strong>{ticket.subject}</strong><small>{ticket.status === "needs_approval" ? "Your approval is needed" : ticket.status === "resolved" ? "Request completed" : ticket.status === "escalated" ? "Your facility response is needed" : `Autopilot handling · ${ticket.waiting_reason || activityCopy[ticket.status]}`}</small><em className={`status ${ticket.status}`}>{ticketStatusLabel(ticket.status)}</em></span></button>) : <div className="empty-state"><b>No matching request mail</b><span>Choose another filter or create a new request.</span></div>}</div><div className="mailbox-footer"><button onClick={onLoad} disabled={busy}>Load sample workspace</button><button onClick={onProcess} disabled={busy}>Process scheduled work</button></div></aside>
      <main className="request-workspace">{!detail ? <div className="empty-detail"><span>✉</span><h2>Select a request</h2><p>The resident message, agent work, and related building records will appear here.</p></div> : <>
        <div className="request-title"><div><span className="record-type">REQUEST · {detail.ticket.ticket_id}</span><h2>{detail.ticket.subject}</h2><p>Received by email · {ticketTime(detail.ticket.updated_at)}</p></div><span className={`status large ${detail.ticket.status}`}>{ticketStatusLabel(detail.ticket.status)}</span></div>
        <article className="incoming-message"><div className="mail-meta"><span className="sender-avatar">{occupant?.initials}</span><div><b>{detail.ticket.requester}</b><small>{occupant?.email} · To: Northstar Concierge</small></div><time>{ticketTime(detail.ticket.updated_at)}</time></div><h3>{detail.ticket.subject}</h3><p>{detail.ticket.description}</p></article>
        {detail.ticket.status === "resolved" ? <section className="resolution-outcome">
          <small>REQUEST OUTCOME</small>
          <h3>{detail.events.some(event => event.event_type === "staff.response_sent") ? `Resolved by ${detail.ticket.assigned_owner || "staff"}` : detail.events.some(event => event.event_type === "approval.decided") ? "Resolved by agent with staff approval" : "Resolved automatically by agent"}</h3>
          <p>{[...detail.events].reverse().find(event => event.event_type === "ticket.resolved")?.summary || "This request is closed. No response is waiting from you."}</p>
          <p>{detail.events.some(event => event.event_type === "verification.passed") ? "Building outcome verified from sensor evidence." : "No sensor verification is recorded for this closure."}</p>
          {location?.state === "Alert" && <p className="outcome-warning">The linked sensor still shows an alert. Closing this request does not confirm that the building condition was repaired.</p>}
        </section> : <AgentProgress ticket={detail.ticket} />}
        {detail.workflow && detail.ticket.status !== "resolved" && <section className="coordinator-checkpoint"><span>WF</span><div><small>DURABLE COORDINATOR CHECKPOINT · ITERATION {String(detail.workflow.checkpoint.loop_iteration || 0)}</small><b>{String(detail.workflow.checkpoint.active_agent || "Operations Coordinator")}</b><p>{String(detail.workflow.checkpoint.objective || detail.ticket.waiting_reason || "Waiting for the next durable workflow step.")}</p></div><em>{detail.workflow.current_step.replace(":", " · ")}</em></section>}
        {detail.ticket.status === "needs_approval" && <div className="decision-bar"><div><span>!</span><div><b>Your approval is needed</b><small>The agent recommends a qualified technician. It will not operate safety-critical equipment.</small></div></div><div><button className="secondary" onClick={() => onApprove(false)} disabled={busy}>Decline</button><button onClick={() => onApprove(true)} disabled={busy}>Approve dispatch</button></div></div>}
        {detail.ticket.status === "escalated" && <StaffResponseBox key={detail.ticket.ticket_id} requester={detail.ticket.requester} busy={busy} onRespond={onRespond} />}
        {detail.work_order && <section className="work-order-card"><div className="work-order-head"><div><span>TECHNICIAN WORK ORDER</span><h3>{detail.work_order.work_order_id}</h3></div><em className={detail.work_order.status}>{detail.work_order.status === "completed" ? "Completed" : "Ongoing"}</em></div><div className="work-order-facts"><span><small>Assigned technician</small><b>{detail.work_order.technician}</b></span><span><small>Trade</small><b>{humanize(detail.work_order.trade)}</b></span><span><small>Location</small><b>{location?.name}</b></span><span><small>{detail.work_order.status === "completed" ? "Finished" : "Estimated completion"}</small><b>{detail.work_order.status === "completed" && detail.work_order.completed_at ? ticketTime(detail.work_order.completed_at) : `${Math.max(0, Math.ceil((new Date(detail.work_order.due_at).getTime() - Date.now()) / 1000))}s remaining`}</b></span></div><div className="work-order-procedure"><small>WORK INSTRUCTIONS</small><p>{detail.work_order.procedure}</p></div>{detail.work_order.completion_notes && <div className="work-order-result"><small>CAUSE FOUND &amp; REPAIR COMPLETED</small><p>{detail.work_order.completion_notes}</p></div>}</section>}
        <TicketAutomation detail={detail} />
        <div className="record-tabs"><b>Activity</b><span>System changes {detail.actions.length}</span><span>Work order {detail.work_order ? "1" : "0"}</span></div>
        <div className="activity-list">{sortedEvents.map((event) => <article key={event.event_id}><span className={`event-icon ${eventTone(event)}`}>{["message.sent", "staff.response_sent"].includes(event.event_type) ? "✉" : event.event_type.includes("verification") || event.event_type === "ticket.resolved" ? "✓" : event.event_type.includes("approval") ? "!" : "AI"}</span><div><span><b>{humanize(event.event_type)}</b><time>{ticketTime(event.created_at)}</time></span><p>{event.summary}</p><small>{event.actor}</small></div></article>)}</div>
      </>}</main>
      <aside className="context-panel">{detail && occupant && location ? <><section className="context-card occupant-card"><div className="panel-heading"><div><p>REQUESTER</p><h3>Resident record</h3></div><button aria-label="More resident actions">•••</button></div><div className="person-summary"><span>{occupant.initials}</span><div><b>{occupant.name}</b><small>{occupant.role}</small><em>{occupant.home}</em></div></div><dl><div><dt>Email</dt><dd>{occupant.email}</dd></div><div><dt>Phone</dt><dd>{occupant.phone}</dd></div><div><dt>Home</dt><dd>{occupant.floor}</dd></div><div><dt>Access</dt><dd>{occupant.access}</dd></div></dl></section><section className="context-card"><div className="panel-heading"><div><p>LOCATION</p><h3>{location.name}</h3></div><span className={`condition ${location.state.toLowerCase()}`}>{location.state}</span></div><div className="location-meta"><span>{location.floor}</span><span>{location.zone}</span><span>{location.occupancy} occupied</span></div><div className="sensor-reading"><div><small>LINKED SENSOR</small><b>{location.sensor}</b></div><strong>{location.reading}</strong></div><div className="sparkline" aria-label="Sensor reading trend"><i /><i /><i /><i /><i /><i /><i /><i /></div><small className="freshness"><span /> Live reading · updated 8 seconds ago</small></section><MailPreview ticket={detail.ticket} events={detail.events} /></> : <div className="empty-context">Related resident and building records appear with the selected request.</div>}</aside></section></>;
}

function AgentLiveView({ live, tickets, onReview }: { live: LiveOperations; tickets: Ticket[]; onReview: (ticket: Ticket) => void }) {
  return <MissionControl live={live} tickets={tickets} onReview={onReview} />;
}


function TicketsView({ tickets, onReview }: { tickets: Ticket[]; onReview: (ticket: Ticket) => void }) {
  const [scope, setScope] = useState<"all" | "mine" | "open">("all");
  const pending = tickets.filter((ticket) => ["needs_approval", "escalated"].includes(ticket.status));
  const visible = tickets.filter((ticket) => scope === "all" || (scope === "mine" && pending.includes(ticket)) || (scope === "open" && ticket.status !== "resolved"));
  return <section className="tickets-view">
    <div className="ticket-summary-row"><article className="my-actions"><div><p>MY ACTIONS</p><h2>Only {pending.length} thing{pending.length === 1 ? "" : "s"} need you</h2><span>Approvals and facility answers are surfaced here.</span></div>{pending.length ? <div className="action-stack">{pending.slice(0, 2).map((ticket) => <button key={ticket.ticket_id} onClick={() => onReview(ticket)}><span className="amber">!</span><div><b>{ticket.subject}</b><small>{ticket.ticket_id} · {ticket.status === "needs_approval" ? "Approval due now" : "Staff response needed"}</small></div><em>Review →</em></button>)}</div> : <div className="all-clear"><span>✓</span><b>You are all caught up</b></div>}</article><article className="ticket-mini-kpis"><div><small>Open tickets</small><b>{tickets.filter((ticket) => ticket.status !== "resolved").length}</b></div><div><small>Autopilot owned</small><b>{tickets.filter((ticket) => activeStatuses.has(ticket.status)).length}</b></div><div><small>Waiting externally</small><b>{tickets.filter((ticket) => ticket.status === "waiting_technician").length}</b></div><div><small>Closed</small><b>{tickets.filter((ticket) => ticket.status === "resolved").length}</b></div></article></div>
    <section className="ticket-register"><div className="ticket-register-head"><div><p>SERVICE MANAGEMENT</p><h3>Ticket worklist</h3></div><div><button className={scope === "all" ? "active" : ""} onClick={() => setScope("all")}>All tickets</button><button className={scope === "mine" ? "active" : ""} onClick={() => setScope("mine")}>My actions <b>{pending.length}</b></button><button className={scope === "open" ? "active" : ""} onClick={() => setScope("open")}>Open</button></div></div><div className="ticket-table-wrap"><table><thead><tr><th>Ticket</th><th>Requester</th><th>Location</th><th>Category</th><th>Priority</th><th>Owner</th><th>Updated</th><th>Status</th><th>Next action</th></tr></thead><tbody>{visible.map((ticket) => <tr key={ticket.ticket_id}><td><button className="ticket-link" onClick={() => onReview(ticket)}><b>{ticket.ticket_id}</b><span>{ticket.subject}</span></button></td><td>{ticket.requester}</td><td>{locationFor(ticket).name}</td><td>{humanize(ticket.kind)}</td><td><span className={`priority-label ${ticket.priority}`}>{humanize(ticket.priority)}</span></td><td><span className="owner-cell"><i>{pending.includes(ticket) ? "MR" : "AI"}</i>{pending.includes(ticket) ? "Maya + Autopilot" : ticket.assigned_owner}</span></td><td>{ticketTime(ticket.updated_at)}</td><td><span className={`status ${ticket.status}`}>{ticketStatusLabel(ticket.status)}</span></td><td>{ticket.status === "needs_approval" ? <button className="review-action" onClick={() => onReview(ticket)}>Review approval</button> : ticket.status === "escalated" ? <button className="review-action" onClick={() => onReview(ticket)}>Send staff response</button> : <span className="automatic">Autopilot managed</span>}</td></tr>)}</tbody></table></div></section>
  </section>;
}

function FloorPlan({ selected }: { selected: (typeof floors)[number] }) {
  return <div className="floor-plan"><div className="plan-corridor">Residential corridor · Elevators · Refuse · Stairs</div>{selected.rooms.map((room, index) => <div key={room} className={`plan-room room-${index + 1}`}><span>{room}</span><small>{room.includes("Apartment") || room.includes("Residences") ? "Homes" : index % 2 === 0 ? "Open" : "Resident access"}</small></div>)}<div className="plan-core"><span>CORE</span><i>Lift</i><i>Stair</i></div></div>;
}

function BuildingView({ tickets, live }: { tickets: Ticket[]; live: LiveOperations }) {
  const [selectedFloor, setSelectedFloor] = useState(7);
  const [sensorScope, setSensorScope] = useState<"all" | "floor">("all");
  const observedSensors = useMemo(() => {
    const authoritative = Object.values(live.building.sensors || {});
    if (authoritative.length) return authoritative;
    const hvac = live.building.assets["AHU-ZONE-4B"];
    const panel = live.building.assets["ELEC-PNL-7A"];
    return sensors.map((sensor) => {
      const override = live.building.sensor_overrides[sensor.id];
      if (override) return { ...sensor, ...override };
      if (sensor.id === "TMP-04-01" && hvac?.temperature_f !== undefined) {
        return { ...sensor, value: `${hvac.temperature_f.toFixed(1)}°F`, state: hvac.temperature_f > 75 ? "Warning" as const : "Normal" as const, seen: "Live" };
      }
      if (sensor.id === "ELEC-7A" && panel?.cabinet_temperature_f !== undefined) {
        return { ...sensor, value: `${panel.cabinet_temperature_f.toFixed(1)}°F`, state: panel.status === "fault" || panel.cabinet_temperature_f >= 95 ? "Critical" as const : "Normal" as const, seen: "Live" };
      }
      return sensor;
    });
  }, [live.building]);
  const observedFloors = useMemo(() => floors.map((floor) => {
    const floorSensors = observedSensors.filter((sensor) => sensor.floor === floor.number);
    const status = floorSensors.some((sensor) => sensor.state === "Critical") ? "Critical" as const : floorSensors.some((sensor) => sensor.state === "Warning") ? "Warning" as const : "Normal" as const;
    const openTickets = tickets.filter((ticket) => ticket.status !== "resolved" && Number(ticket.location_id.match(/F(\d{2})/)?.[1]) === floor.number).length;
    return { ...floor, status, openTickets };
  }), [observedSensors, tickets]);
  const selected = observedFloors.find((floor) => floor.number === selectedFloor) || observedFloors[3];
  const visibleSensors = sensorScope === "all" ? observedSensors : observedSensors.filter((sensor) => sensor.floor === selectedFloor);
  const alerts = observedSensors.filter((sensor) => sensor.state !== "Normal");
  return <section className="building-view">
    <div className="building-command">
      <div className="building-title"><div><p>RESIDENTIAL DIGITAL TWIN · LIVE</p><h2>Northstar Residences</h2><span>10-story residential tower · 132 apartments · café and resident amenities · New York</span></div><div><article><small>Residents present</small><b>{totalOccupancy} / {totalCapacity}</b><span>{Math.round(totalOccupancy / totalCapacity * 100)}% of modeled capacity</span></article><article><small>Sensor network</small><b>{observedSensors.length} / {observedSensors.length}</b><span className="online">All reporting</span></article><article><small>Active alerts</small><b>{alerts.length}</b><span className={alerts.length ? "alert-copy" : "online"}>{alerts.length ? [...new Set(alerts.map((sensor) => `F${sensor.floor}`))].join(" and ") : "No active alarms"}</span></article><article><small>Open tickets</small><b>{tickets.filter((ticket) => ticket.status !== "resolved").length}</b><span>Agent monitored</span></article></div></div>
      <div className="twin-layout">
        <section className="tower-stage"><Suspense fallback={<div className="scene-loading"><span>3D</span><b>Loading residential twin</b></div>}><BuildingScene floors={observedFloors} selectedFloor={selectedFloor} onSelect={setSelectedFloor} /></Suspense><div className="scene-instructions">Drag to orbit · Scroll to zoom · Select a residential floor</div><div className="scene-legend"><span><i className="normal" />Normal</span><span><i className="warning" />Warning</span><span><i className="critical" />Critical</span></div></section>
        <aside className="floor-selector"><div><p>RESIDENTIAL STACK</p><h3>10 floors · 132 apartments</h3></div>{observedFloors.map((floor) => <button className={`${selectedFloor === floor.number ? "selected" : ""} ${floor.status.toLowerCase()}`} onClick={() => setSelectedFloor(floor.number)} key={floor.number}><span>{String(floor.number).padStart(2, "0")}</span><div><b>{floor.name}</b><small>{floor.occupancy}/{floor.capacity} residents present · {floor.openTickets} open</small></div><i /></button>)}</aside>
        <section className="floor-detail"><div className="dark-heading"><div><p>SELECTED FLOOR</p><h3>Floor {selected.number} · {selected.name}</h3></div><span className={`dark-status ${selected.status.toLowerCase()}`}>{selected.status}</span></div><div className="floor-metrics"><span><small>Primary use</small><b>{selected.use}</b></span><span><small>Area</small><b>{selected.area}</b></span><span><small>Residents present</small><b>{selected.occupancy} / {selected.capacity}</b></span><span><small>Open tickets</small><b>{selected.openTickets}</b></span></div><FloorPlan selected={selected} /></section>
      </div>
    </div>
    <section className="dark-sensor-register"><div className="dark-register-head"><div><p>RESIDENTIAL BUILDING MANAGEMENT SYSTEM</p><h3>Sensor register</h3><span>{visibleSensors.length} devices · apartments, corridors and amenities · telemetry updated {live.building.updated_at ? ticketTime(live.building.updated_at) : "on connection"}</span></div><div><button className={sensorScope === "all" ? "active" : ""} onClick={() => setSensorScope("all")}>All sensors <b>{observedSensors.length}</b></button><button className={sensorScope === "floor" ? "active" : ""} onClick={() => setSensorScope("floor")}>Floor {selectedFloor} <b>{observedSensors.filter((sensor) => sensor.floor === selectedFloor).length}</b></button></div></div><div className="dark-table-wrap"><table><thead><tr><th>Sensor ID</th><th>Floor</th><th>Residential area</th><th>Measurement</th><th>Live reading</th><th>Target</th><th>Health</th><th>Last signal</th></tr></thead><tbody>{visibleSensors.map((sensor) => <tr key={sensor.id} onClick={() => setSelectedFloor(sensor.floor)}><td><b>{sensor.id}</b></td><td>F{String(sensor.floor).padStart(2, "0")}</td><td>{sensor.area}</td><td>{sensor.type}</td><td><strong>{sensor.value}</strong></td><td>{sensor.target}</td><td><span className={`dark-status ${sensor.state.toLowerCase()}`}>{sensor.state}</span></td><td><span className="signal-time"><i />{sensor.seen}</span></td></tr>)}</tbody></table></div></section>
  </section>;
}

function PeopleView({ tickets }: { tickets: Ticket[] }) {
  const [query, setQuery] = useState("");
  const people = Object.values(residents).filter((person) => `${person.name} ${person.home} ${person.role} ${person.email}`.toLowerCase().includes(query.toLowerCase()));
  return <section className="register-view"><div className="people-toolbar"><div><p>RESIDENT DIRECTORY</p><h2>Residents and households</h2><span>Homes, contact information, entry permissions and service history</span></div><label>⌕<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search resident or apartment" /></label></div><section className="register-card people-table"><table><thead><tr><th>Resident</th><th>Home</th><th>Floor</th><th>Contact</th><th>Entry profile</th><th>Requests</th><th>Status</th></tr></thead><tbody>{people.map((person) => <tr key={person.email}><td><div className="table-person"><span>{person.initials}</span><div><b>{person.name}</b><small>{person.role}</small></div></div></td><td>{person.home}</td><td>{person.floor}</td><td><b className="email-value">{person.email}</b><small>{person.phone}</small></td><td>{person.access}</td><td>{tickets.filter((ticket) => ticket.requester === person.name).length}</td><td><span className="condition normal">Active</span></td></tr>)}</tbody></table>{people.length === 0 && <div className="empty-state"><b>No matching residents</b><span>Try a name, apartment, floor, or email address.</span></div>}</section></section>;
}

export default function App() {
  const [view, setView] = useState<View>("overview"); const [tickets, setTickets] = useState<Ticket[]>([]); const [metrics, setMetrics] = useState(emptyMetrics); const [live, setLive] = useState<LiveOperations>(emptyLive); const [selectedId, setSelectedId] = useState(""); const [detail, setDetail] = useState<TicketDetail | null>(null); const [connection, setConnection] = useState<"live" | "reconnecting">("reconnecting"); const [error, setError] = useState(""); const [creating, setCreating] = useState(false); const [busy, setBusy] = useState(false);
  const refresh = useMemo(() => singleFlightRefresh(async () => { try { const [nextTickets, nextMetrics, nextLive] = await Promise.all([api.tickets(), api.metrics(), api.live()]); setTickets(nextTickets); setMetrics(nextMetrics); setLive(nextLive); setError(""); setSelectedId((current) => current || nextTickets[0]?.ticket_id || ""); } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to reach the operations service"); } }), []);
  useEffect(() => { void refresh(); const polling = window.setInterval(() => void refresh(), 600); return () => window.clearInterval(polling); }, [refresh]);
  useEffect(() => { if (selectedId) void api.ticket(selectedId).then(setDetail).catch(() => setDetail(null)); }, [selectedId, tickets]);
  useEffect(() => { const stream = new EventSource(`${apiBase}/api/events`); stream.onopen = () => setConnection("live"); stream.onerror = () => setConnection("reconnecting"); stream.onmessage = () => void refresh(); return () => stream.close(); }, [refresh]);
  const operate = async (action: () => Promise<unknown>) => { setBusy(true); try { await action(); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "The operation could not be completed"); } finally { setBusy(false); } };
  const publishRequest = async (request: CustomRequestInput) => { setBusy(true); try { const published = await api.publishRequest(request); await refresh(); return published; } catch (reason) { setError(reason instanceof Error ? reason.message : "The request scenario could not be created"); throw reason; } finally { setBusy(false); } };
  const loadSamples = () => operate(async () => { const loaded = await api.loadSampleRequests(); setSelectedId(loaded.find((ticket) => ticket.ticket_id === "TKT-1003")?.ticket_id || loaded[0]?.ticket_id || ""); });
  const reviewTicket = (ticket: Ticket) => { setSelectedId(ticket.ticket_id); setView("requests"); };
  const create = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const form = new FormData(event.currentTarget); await operate(async () => { const ticket = await api.create({ subject: String(form.get("subject")), description: String(form.get("description")), requester: String(form.get("requester")), location_id: String(form.get("location_id")) }); setTickets((current) => [ticket, ...current.filter((item) => item.ticket_id !== ticket.ticket_id)]); setSelectedId(ticket.ticket_id); setDetail(await api.ticket(ticket.ticket_id)); setCreating(false); setView("requests"); }); };
  return <AppShell view={view} setView={setView} metrics={metrics}>
    <Topbar view={view} connection={connection} onCreate={() => setCreating(true)} />
    <RequestSummary metrics={metrics} tickets={tickets} contributions={live.impact.contributions} />
    {(["requests", "tickets"].includes(view)) && <nav className="workspace-tabs" aria-label="Request views"><button className={view === "requests" ? "selected" : ""} onClick={() => setView("requests")}>Inbox & responses</button><button className={view === "tickets" ? "selected" : ""} onClick={() => setView("tickets")}>All tickets</button></nav>}
    {(["building", "people"].includes(view)) && <nav className="workspace-tabs" aria-label="Building views"><button className={view === "building" ? "selected" : ""} onClick={() => setView("building")}>Building & sensors</button><button className={view === "people" ? "selected" : ""} onClick={() => setView("people")}>Residents</button></nav>}
    {(["agent", "generator"].includes(view)) && <nav className="workspace-tabs" aria-label="Agent views"><button className={view === "agent" ? "selected" : ""} onClick={() => setView("agent")}>Live activity</button><button className={view === "generator" ? "selected" : ""} onClick={() => setView("generator")}>Request generator</button></nav>}
    {error && <p className="error-banner">Operations service unavailable. Start the local services and this workspace will reconnect automatically.</p>}
    {view === "overview" && <OverviewView tickets={tickets} metrics={metrics} live={live} onReview={reviewTicket} />}
    {view === "requests" && <InboxView tickets={tickets} metrics={metrics} live={live} selectedId={selectedId} detail={detail} busy={busy} onSelect={setSelectedId} onCreate={() => setCreating(true)} onLoad={loadSamples} onProcess={() => operate(() => api.processScheduled())} onApprove={(approved) => detail && operate(() => api.approve(detail.ticket.ticket_id, approved))} onRespond={(response) => detail && operate(() => api.respond(detail.ticket.ticket_id, response))} />}
    {view === "agent" && <AgentLiveView live={live} tickets={tickets} onReview={reviewTicket} />}
    {view === "generator" && <GeneratorView live={live} busy={busy} onPublishRequest={publishRequest} onGenerate={(count, scenarioType) => operate(async () => { await api.generateRequests({ count, scenario_type: scenarioType }); setView("agent"); })} onConfigure={(running, intervalSeconds) => operate(() => api.configureSimulation({ running, interval_seconds: intervalSeconds }))} onOpenActivity={() => setView("agent")} onOpenBuilding={() => setView("building")} />}
    {view === "tickets" && <TicketsView tickets={tickets} onReview={reviewTicket} />}
    {view === "building" && <BuildingView tickets={tickets} live={live} />}
    {view === "people" && <PeopleView tickets={tickets} />}
    {creating && <div className="modal" onMouseDown={() => setCreating(false)}><form onSubmit={create} onMouseDown={(event) => event.stopPropagation()}>
      <div className="modal-head"><div><p>NEW RESIDENT REQUEST</p><h2>Create request message</h2><span>Submit on behalf of a resident. The agent will pick it up automatically.</span></div><button type="button" className="close" onClick={() => setCreating(false)}>×</button></div>
      <label>Resident<input name="requester" list="resident-list" required defaultValue="Building Resident" /><datalist id="resident-list">{Object.keys(residents).map((name) => <option value={name} key={name} />)}</datalist></label>
      <label>Subject<input name="subject" required minLength={3} autoFocus placeholder="Brief summary of the resident request" /></label>
      <label>Message<textarea name="description" required minLength={3} placeholder="Enter the resident's question or problem…" /></label>
      <label>Apartment or amenity<select name="location_id" defaultValue="BLDG-A-F04-APT-4B">{[...floors].sort((a, b) => a.number - b.number).flatMap((floor) => floor.rooms.map((room) => <option value={locationIdForSpace(floor.number, room)} key={`${floor.number}-${room}`}>Floor {floor.number} · {room}</option>))}</select></label>
      <div className="modal-actions"><button type="button" className="secondary" onClick={() => setCreating(false)}>Cancel</button><button disabled={busy}>Submit to agent</button></div>
    </form></div>}
  </AppShell>;
}
