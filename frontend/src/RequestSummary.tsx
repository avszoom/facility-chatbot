import type { LiveOperations, Metrics, Ticket } from "./types";
import "./request-summary.css";

export function RequestSummary({ metrics, tickets, contributions }: { metrics: Metrics; tickets: Ticket[]; contributions?: LiveOperations["impact"]["contributions"] }) {
  const working = tickets.filter(ticket => ["new", "triaging", "working", "waiting_verification"].includes(ticket.status)).length;
  const waiting = tickets.filter(ticket => ticket.status === "waiting_technician").length;
  const assisted = Math.max(0, metrics.resolved - metrics.autonomous_resolutions);
  const cards = [
    ["Requests received", metrics.received, "All requests in this workspace", "blue"],
    ["Agent actions completed", contributions?.agent_actions ?? "—", contributions?.agent_percent == null ? "No coordination work recorded" : `${contributions.agent_percent}% of recorded work · not completion %`, "green"],
    ["Staff actions completed", contributions?.human_actions ?? "—", contributions?.human_percent == null ? "No staff work recorded" : `${contributions.human_percent}% of recorded work · replies & approvals`, "blue"],
    ["Agent working", working, "Queued, investigating or verifying", "violet"],
    ["Waiting for technician", waiting, "Work remains open", "amber"],
    ["Needs your attention", metrics.needs_approval + metrics.escalated, `${metrics.needs_approval} approval · ${metrics.escalated} staff review`, "red"],
  ] as const;
  return <section className="request-summary" aria-label="Request outcomes and ownership">
    {cards.map(([label, count, description, color]) => <article key={label} className={color}><small>{label}</small><strong key={String(count)} className="metric-updated">{count}</strong><span>{description}</span></article>)}
    <p>{metrics.received} received · {metrics.resolved} resolved ({metrics.autonomous_resolutions} automatically, {assisted} with staff) · {metrics.active} still open</p>
    <details className="summary-help"><summary>How these numbers are counted</summary><p>Percentages cover recorded coordination actions, including staff-assisted resolutions. Physical repair and routing events are excluded; this is not time saved. Technician completions: {contributions?.technician_completions ?? "—"} (simulated). Open a request for its breakdown.</p></details>
  </section>;
}
