import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { sortByProgress, progressStage } from "./live-progress";
import { singleFlightRefresh } from "./live-refresh";
import { LiveWork } from "./LiveWork";
import type { LiveOperations, Ticket } from "./types";

const ticket = (id: string, status: Ticket["status"]) => ({ ticket_id:id, subject:id, status, updated_at:"2026-09-14T04:00:00Z" }) as Ticket;
const live = { agent:{deliveries:[],workflow_states:{},ticket_progress:{}},recent_events:[] } as unknown as LiveOperations;

describe("Live progress", () => {
  it("moves furthest-progressed requests first without mutating API data", () => {
    const rows = [ticket("new","new"),ticket("investigation","triaging"),ticket("done","resolved"),ticket("verify","waiting_verification"),ticket("act","working")];
    expect(sortByProgress(rows,live).map(t=>t.ticket_id)).toEqual(["done","verify","act","investigation","new"]);
    expect(rows[0].ticket_id).toBe("new");
  });
  it("promotes specialist progress even before the ticket leaves triage", () => {
    const rows=[ticket("A","triaging"),ticket("B","triaging")];
    const updated={...live,agent:{...live.agent,workflow_states:{B:{checkpoint:{completed_specialists:["Sensor Intelligence Agent"]}}}}} as unknown as LiveOperations;
    expect(sortByProgress(rows,updated)[0].ticket_id).toBe("B");
    expect(progressStage(ticket("C","escalated"),["verification.failed"])).toBe(3);
  });
  it("stage chart accounts for every request exactly once", () => {
    const rows=[ticket("a","triaging"),ticket("b","resolved"),ticket("c","needs_approval"),ticket("d","waiting_technician")];
    const html=renderToStaticMarkup(<LiveWork live={live} tickets={rows} onSelect={()=>{}} />);
    expect(html).toContain("0 Queued, 1 Investigating, 1 Acting / field work, 0 Verifying, 1 Resolved, 1 Needs attention");
    expect(html).not.toContain("mc-running-dot");
  });
  it("coalesces refreshes, then permits the next fresh snapshot", async () => {
    let finish!:()=>void;
    const request=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve;}));
    const refresh=singleFlightRefresh(request);
    const first=refresh(), second=refresh();
    expect(first).toBe(second);
    await Promise.resolve();
    expect(request).toHaveBeenCalledTimes(1);
    finish(); await first;
    const next=refresh(); await Promise.resolve();
    expect(request).toHaveBeenCalledTimes(2);
    finish(); await next;
  });
});
