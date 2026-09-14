import { useState } from "react";
import type { LiveOperations, TicketDetail } from "./types";
import { sensorEvidence, targetBounds } from "./sensor-evidence";
import "./sensor-evidence.css";
const time = (at: string) => new Date(at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"});

export function SensorEvidence({detail, live}: {detail: TicketDetail; live: LiveOperations}) {
  const [selected, setSelected] = useState("");
  const ids = [...new Set(detail.events.flatMap(e => Array.isArray(e.payload.evidence_sensor_ids) ? e.payload.evidence_sensor_ids.filter((v): v is string => typeof v === "string") : []))].filter(id => live.building.sensors[id]);
  if (!ids.length) return null;
  const id = ids.includes(selected) ? selected : ids[0];
  const sensor = live.building.sensors[id];
  const readings = sensorEvidence(detail, live, id);
  const bounds = targetBounds(sensor.target);
  const values = readings.map(r => r.value);
  const low = Math.min(...values, bounds?.[0] ?? Infinity);
  const high = Math.max(...values, bounds?.[1] ?? -Infinity);
  const pad = Math.max((high-low)*.12, 1);
  const y = (v: number) => 155 - (v-low+pad)/(high-low+2*pad)*130;
  const x = (i: number) => 55 + i/Math.max(1, readings.length-1)*480;
  const verdict = [...detail.events].reverse().find(e => ["verification.passed", "verification.failed"].includes(e.event_type));
  const milestones = detail.events.filter(e => ["action.completed", "work_order.completed", "verification.passed", "verification.failed"].includes(e.event_type));
  return <section className="sensor-evidence" aria-label="Historical sensor evidence">
    <header><div><h3>Sensor history & verification</h3><p>Recorded simulation data · {detail.ticket.resolved_at ? "history up to ticket closure" : "updates while this request is open"}</p></div><select aria-label="Evidence sensor" value={id} onChange={e => setSelected(e.target.value)}>{ids.map(i => <option key={i} value={i}>{i} · {live.building.sensors[i].type}</option>)}</select></header>
    <div className="sensor-evidence-facts"><span>First recorded<b>{readings[0]?.value ?? "—"} {sensor.unit}</b></span><span>Last recorded<b>{readings.at(-1)?.value ?? "—"} {sensor.unit}</b></span><span>Expected range<b>{sensor.target}</b></span></div>
    {readings.length > 1 ? <svg viewBox="0 0 570 195" role="img" aria-label={`${id} historical readings in ${sensor.unit}; expected ${sensor.target}`}>
      {bounds && <rect x="55" y={y(bounds[1])} width="480" height={y(bounds[0])-y(bounds[1])} fill="#22c58a" opacity=".12"/>}
      {[low, (low+high)/2, high].map((v,i) => <g key={i}><line x1="55" x2="535" y1={y(v)} y2={y(v)} stroke="currentColor" opacity=".12"/><text x="48" y={y(v)+4} textAnchor="end">{v.toFixed(1)}</text></g>)}
      <polyline points={readings.map((r,i) => `${x(i)},${y(r.value)}`).join(" ")} fill="none" stroke="#3789f7" strokeWidth="2.5"/>
      {readings.map((r,i) => <circle key={`${r.at}-${i}`} cx={x(i)} cy={y(r.value)} r="3" fill={r.state === "Normal" ? "#20b77c" : "#e99b29"}><title>{time(r.at)} · {r.value} {sensor.unit} · {r.state} · {r.label}</title></circle>)}
      <text x="55" y="183">{time(readings[0].at)}</text><text x="535" y="183" textAnchor="end">{time(readings.at(-1)!.at)}</text>
    </svg> : <p>No historical trend yet. At least two recorded readings are needed.</p>}
    <p className="sensor-chart-note">Points follow observation order, not elapsed time. Green shading is the expected range. Hover a point for its recorded time; repair recovery may use accelerated simulated minutes.</p>
    <ol>{milestones.map(e => <li key={e.event_id}><time>{time(e.created_at)}</time><b>{e.event_type === "action.completed" ? "Agent control action" : e.event_type === "work_order.completed" ? "Simulated technician repair" : e.event_type === "verification.passed" ? "Verification passed" : "Verification failed"}</b><span>{e.summary}</span></li>)}</ol>
    <footer>{verdict ? `${verdict.event_type === "verification.passed" ? "✓" : "!"} ${verdict.summary}` : "Verification pending · normal readings alone do not close this request."}<small>These are simulated readings, not measurements from a connected physical building.</small></footer>
  </section>;
}
