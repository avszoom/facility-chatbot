import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RequestSummary } from "./RequestSummary";
import type { Metrics, Ticket } from "./types";

const metrics: Metrics = { received: 1, active: 0, resolved: 1, autonomous_resolutions: 0, needs_approval: 0, escalated: 0, human_touches_saved: 0, verified_closures: 0 };

describe("Request ownership summary", () => {
  it("accounts for a staff-resolved request even when automatic resolutions are zero", () => {
    const html = renderToStaticMarkup(<RequestSummary metrics={metrics} tickets={[]} />);
    expect(html).toContain("1 received · 1 resolved (0 automatically, 1 with staff) · 0 still open");
  });

  it("does not count technician waiting time as active agent work", () => {
    const html = renderToStaticMarkup(<RequestSummary metrics={{ ...metrics, active: 1, resolved: 0 }} tickets={[{ status: "waiting_technician" } as Ticket]} />);
    expect(html).toContain("<small>Agent working</small><strong>0</strong>");
    expect(html).toContain("<small>Waiting for technician</small><strong>1</strong>");
  });
});
