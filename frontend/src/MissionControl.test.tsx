import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Pipeline, pipelineIndex } from "./MissionControl";
import type { Ticket } from "./types";

describe("Live pipeline", () => {
  it("never displays an escalation as completed", () => {
    const ticket = { status: "escalated" } as Ticket;
    expect(pipelineIndex(ticket)).toBeLessThan(4);
    expect(renderToStaticMarkup(<Pipeline ticket={ticket} running />)).toContain("blocked");
    expect(renderToStaticMarkup(<Pipeline ticket={ticket} running />)).not.toContain("executing");
  });
  it("animates only leased work and keeps technician work before verification", () => {
    const ticket = { status: "waiting_technician" } as Ticket;
    expect(pipelineIndex(ticket)).toBe(2);
    expect(renderToStaticMarkup(<Pipeline ticket={ticket} />)).not.toContain("executing");
    expect(renderToStaticMarkup(<Pipeline ticket={{status:"triaging"} as Ticket} running />)).toContain("executing");
  });
  it("does not claim a staff closure was independently verified", () => {
    const ticket = { status: "resolved" } as Ticket;
    expect(renderToStaticMarkup(<Pipeline ticket={ticket} />)).toContain("Not verified");
    expect(renderToStaticMarkup(<Pipeline ticket={ticket} eventTypes={["verification.passed"]} />)).not.toContain("Not verified");
  });
});
