import type { Metrics, Ticket } from "./types";
import "./request-summary.css";

export function RequestSummary({ metrics, tickets }: { metrics: Metrics; tickets: Ticket[] }) {
  const working = tickets.filter(ticket => ["new", "triaging", "working", "waiting_verification"].includes(ticket.status)).length;
  const waiting = tickets.filter(ticket => ticket.status === "waiting_technician").length;
  const assisted = Math.max(0, metrics.resolved - metrics.autonomous_resolutions);
  const cards = [
    ["Requests received", metrics.received, "All requests in this workspace", "blue"],
    ["Resolved automatically", metrics.autonomous_resolutions, "No staff reply or approval", "green"],
    ["Resolved with staff", assisted, "Staff replied or approved an action", "blue"],
    ["Agent working", working, "Queued, investigating or verifying", "violet"],
    ["Waiting for technician", waiting, "Work remains open", "amber"],
    ["Needs your attention", metrics.needs_approval + metrics.escalated, `${metrics.needs_approval} approval · ${metrics.escalated} staff review`, "red"],
  ] as const;
  return <section className="request-summary" aria-label="Request outcomes and ownership">
    {cards.map(([label, count, description, color]) => <article key={label} className={color}><small>{label}</small><strong>{count}</strong><span>{description}</span></article>)}
    <p>{metrics.received} received · {metrics.resolved} resolved ({metrics.autonomous_resolutions} automatically, {assisted} with staff) · {metrics.active} still open</p>
    <p className="summary-help">These numbers count requests. “With staff” includes agent work plus a human reply or approval. Open any request for its agent actions, human interventions and automation percentage.</p>
  </section>;
}
