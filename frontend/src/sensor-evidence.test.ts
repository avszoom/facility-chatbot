import { expect, it } from "vitest";
import { sensorEvidence, targetBounds } from "./sensor-evidence";
import type { LiveOperations, TicketDetail } from "./types";

it("parses ranges without losing thousands separators", () => {
  expect(targetBounds("68–75°F")).toEqual([68,75]);
  expect(targetBounds("< 1,000 ppm")).toEqual([0,1000]);
  expect(targetBounds("Unknown")).toBeNull();
});
it("preserves recorded pre-repair evidence and excludes readings after closure", () => {
  const row = (at: string, value: number) => ({recorded_at: at, numeric_value:value,state:"Normal"});
  const detail = {ticket:{resolved_at:"2026-09-14T01:02:00Z"},actions:[],events:[{created_at:"2026-09-14T01:01:00Z",payload:{asset:{id:"TMP"},history:[row("2026-09-14T01:00:00Z",78)]}}]} as unknown as TicketDetail;
  const live = {building:{sensor_history:{TMP:[row("2026-09-14T01:01:00Z",72),row("2026-09-14T01:03:00Z",90)]}}} as unknown as LiveOperations;
  expect(sensorEvidence(detail,live,"TMP").map(r=>r.value)).toEqual([78,72]);
});
