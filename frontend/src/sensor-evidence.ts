import type { LiveOperations, TicketDetail } from "./types";
export type Reading = { at: string; value: number; state: string; label: string };
export function sensorEvidence(detail: TicketDetail, live: LiveOperations, id: string): Reading[] {
  const rows: Reading[] = [];
  const add = (raw: unknown, at = "", label = "Recorded reading") => {
    if (!raw || typeof raw !== "object") return;
    const r = raw as Record<string, unknown>;
    const time = String(r.recorded_at || r.updated_at || at);
    if (typeof r.numeric_value !== "number" || !Number.isFinite(r.numeric_value) || !Number.isFinite(Date.parse(time))) return;
    rows.push({at: time, value: r.numeric_value, state: String(r.state || "Unknown"), label: r.simulated_minutes_after_repair != null ? `Simulated +${r.simulated_minutes_after_repair} min after repair` : label});
  };
  for (const e of detail.events) {
    const p = e.payload as Record<string, any>;
    for (const r of p.sensor_histories?.[id] || []) add(r);
    if (p.asset?.id === id || p.telemetry?.id === id) {
      for (const r of p.history || []) add(r);
      add(p.telemetry, e.created_at, "Investigation reading");
    }
    for (const r of p.repair?.recovery_samples?.[id] || []) add(r, e.created_at);
    add(p.repair?.before?.[id], e.created_at, "Before technician repair");
    add(p.repair?.after?.[id], e.created_at, "After simulated repair");
  }
  for (const a of detail.actions) {
    if (a.before_state?.id === id || a.before_state?.asset_id === id) add(a.before_state, a.created_at, "Before agent action");
    const after = a.after_state as Record<string, any> | null;
    if (after?.after?.id === id) add({...after.after, updated_at: a.completed_at || after.after.updated_at}, a.created_at, "After simulated control response");
  }
  for (const r of live.building.sensor_history[id] || []) add(r);
  const end = detail.ticket.resolved_at ? Date.parse(detail.ticket.resolved_at) : Infinity;
  const unique = new Map<string, Reading>();
  for (const r of rows.sort((a,b) => Date.parse(a.at) - Date.parse(b.at))) {
    if (Date.parse(r.at) <= end) unique.set(`${r.at}/${r.value}`, r);
  }
  return [...unique.values()];
}

export function targetBounds(target: string): [number, number] | null {
  const values = target.replaceAll(",", "").match(/\d+(?:\.\d+)?/g)?.map(Number) || [];
  if (values.length >= 2) return [values[0], values[1]];
  if (values.length === 1 && target.includes("<")) return [0, values[0]];
  return null;
}
