import type { LiveOperations, Metrics, Ticket } from "./types";
import "./request-summary.css";

export function RequestSummary({ metrics, tickets, contributions }: { metrics: Metrics; tickets: Ticket[]; contributions?: LiveOperations["impact"]["contributions"] }) {
  const working = tickets.filter(ticket => ["new", "triaging", "working", "waiting_verification"].includes(ticket.status)).length;
  const waiting = tickets.filter(ticket => ticket.status === "waiting_technician").length;
  const assisted = Math.max(0, metrics.resolved - metrics.autonomous_resolutions);
  const cards = [
    ["Requests received", metrics.received, "All requests in this workspace", "blue"],
    ["Resolved without your help", metrics.autonomous_resolutions, "Agent finished · no staff reply or approval", "green"],
    ["Resolved with your help", assisted, "Finished after a staff reply or approval", "blue"],
    ["Agent working", working, "Queued, investigating or verifying", "violet"],
    ["Waiting for technician", waiting, "Work remains open", "amber"],
    ["Needs your attention", metrics.needs_approval + metrics.escalated, `${metrics.needs_approval} approval · ${metrics.escalated} staff review`, "red"],
  ] as const;
  return <section className="request-summary" aria-label="Request outcomes and ownership">
    {cards.map(([label, count, description, color]) => <article key={label} className={color}><small>{label}</small><strong key={String(count)} className="metric-updated">{count}</strong><span>{description}</span></article>)}
    <p>{metrics.received} received · {metrics.resolved} resolved ({metrics.autonomous_resolutions} automatically, {assisted} with staff) · {metrics.active} still open</p>
    <p>Work completed so far: <b>{contributions?.agent_actions ?? "—"} agent actions ({contributions?.agent_percent ?? "—"}%)</b> · <b>{contributions?.human_actions ?? "—"} staff actions ({contributions?.human_percent ?? "—"}%)</b>. Actions are steps, not resolved requests.</p>
    <details className="summary-help"><summary>How these numbers are counted</summary><p>The five outcome cards add up to requests received. Action percentages include work on open requests; 100% agent actions does not mean every request is resolved. Physical repair and routing events are excluded. Technician completions: {contributions?.technician_completions ?? "—"} (simulated).</p></details>
  </section>;
}
