import { expect, it } from "vitest";
import { ticketContributions } from "./automation";
import type { TicketEvent } from "./types";

const event = (event_id: string, event_type: string, actor = "Agent") => ({ event_id, event_type, actor, summary: "Recorded work", created_at: "2026-09-14T01:00:00Z" } as TicketEvent);

it("shows agent contributions even when staff closes a request", () => {
  const result = ticketContributions([
    event("1", "specialist.completed"), event("2", "agent.decision"),
    event("3", "message.sent"), event("4", "staff.response_sent", "Maya"),
    event("5", "ticket.resolved", "Maya"), event("6", "coordinator.delegated"),
  ]);
  expect(result.percentage).toBe(75);
  expect(result.agent).toHaveLength(3);
  expect(result.human).toHaveLength(1);
});

it("does not inflate automation with retries, verification duplicates, or field work", () => {
  const result = ticketContributions([
    event("1", "work_order.created"), event("1", "work_order.created"),
    event("2", "work_order.completed", "Technician"),
    event("3", "specialist.completed", "Verification Agent"),
    event("4", "verification.passed"), event("5", "approval.decided", "Maya"),
    event("6", "agent.tools_completed"), event("7", "ticket.resolved"),
  ]);
  expect(result.agent).toHaveLength(2);
  expect(result.technician).toHaveLength(1);
  expect(result.human).toHaveLength(1);
  expect(result.percentage).toBe(67);
});

it("does not invent automation for a staff-only or unstarted request", () => {
  expect(ticketContributions([event("1", "staff.response_sent", "Maya")]).percentage).toBe(0);
  expect(ticketContributions([event("1", "ticket.created")]).percentage).toBeNull();
});
