import type { ReviewSummary } from "./types";

export function RequestReview({ summary }: { summary?: ReviewSummary }) {
  if (!summary) return null;
  return <section className="resolution-outcome request-review">
    <h3>Why this needs you</h3><p>{summary.reason}</p>
    <h4>What the agent did</h4>
    {summary.done.length ? <ul>{summary.done.map(line => <li key={line}>{line}</li>)}</ul> : <p>No completed investigation steps are recorded.</p>}
    <h4>What was fixed</h4><p>{summary.changed}</p>
    <h4>What you need to do</h4><p>{summary.next_step}</p>
    {summary.finding && <details><summary>Read the agent’s findings</summary><p>{summary.finding}</p></details>}
    {summary.technical_detail && <details><summary>Technical failure details</summary><p>{summary.technical_detail}</p></details>}
  </section>;
}
