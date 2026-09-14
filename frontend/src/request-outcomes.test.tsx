import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { RequestSummary } from "./RequestSummary";
import { OverviewView } from "./OverviewView";
import type { Metrics, Ticket, LiveOperations } from "./types";

const metrics = {received: 11, resolved: 8, autonomous_resolutions: 8, active: 3, needs_approval: 1, escalated: 2} as Metrics;
const tickets = ["First", "Second", "Third"].map((subject, i) => ({subject, ticket_id: String(i), status: i ? "escalated" : "needs_approval", priority: "normal", location_id: "Lobby", kind: "enquiry", updated_at: "2026-09-14T00:00:00Z"})) as Ticket[];

it("leads with resolved requests rather than agent action totals", () => {
  const html = renderToStaticMarkup(<RequestSummary metrics={metrics} tickets={tickets} />);
  expect(html).toContain("Resolved without your help");
  expect(html).toContain("8 automatically, 0 with staff");
  expect(html).toContain("3 still open");
});

it("renders every attention request and request-based outcome percentage", () => {
  const live = {impact: {}, agent: {active_tickets: [], worker_count: 3}} as unknown as LiveOperations;
  const html = renderToStaticMarkup(<OverviewView metrics={metrics} tickets={tickets} live={live} onReview={() => {}} />);
  expect((html.match(/class="decision-row"/g) || [])).toHaveLength(3);
  expect(html).toContain("73%");
  expect(html).toContain("8 of 11 requests resolved without your help");
});
