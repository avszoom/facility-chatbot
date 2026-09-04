import { FormEvent, useEffect, useState } from "react";

import type { LiveOperations } from "./types";

type ScenarioType = "all" | "enquiry" | "service_request" | "incident";

type Props = {
  live: LiveOperations;
  busy: boolean;
  onGenerate: (count: number, scenarioType: ScenarioType) => Promise<void>;
  onConfigure: (running: boolean, intervalSeconds: number) => Promise<void>;
};

const scenarioCopy: Record<ScenarioType, { label: string; detail: string }> = {
  all: { label: "Mixed requests", detail: "Rotate through the full building scenario catalog." },
  enquiry: { label: "Knowledge enquiries", detail: "Hours, access, visitors, deliveries, amenities, and procedures." },
  service_request: { label: "Service requests", detail: "Comfort conditions that may allow a policy-safe building change." },
  incident: { label: "Safety incidents", detail: "Abnormal sensor evidence requiring investigation and approval." },
};

export function GeneratorView({ live, busy, onGenerate, onConfigure }: Props) {
  const [count, setCount] = useState(3);
  const [scenarioType, setScenarioType] = useState<ScenarioType>("all");
  const [intervalSeconds, setIntervalSeconds] = useState(live.simulation.interval_seconds);
  const [published, setPublished] = useState(0);

  useEffect(() => setIntervalSeconds(live.simulation.interval_seconds), [live.simulation.interval_seconds]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await onGenerate(count, scenarioType);
    setPublished(count);
  };

  return <section className="generator-view">
    <header className="generator-heading">
      <div><p>BUILDING WORLD CONTROL</p><h2>Request generator</h2><span>Publish controlled occupant and sensor events into the same durable intake used by live building activity.</span></div>
      <span className={`generator-state ${live.simulation.running ? "running" : "paused"}`}><i />{live.simulation.running ? "Automatic generation running" : "Automatic generation paused"}</span>
    </header>

    <div className="generator-layout">
      <form className="generator-card generator-controls" onSubmit={submit}>
        <div className="generator-card-title"><span>01</span><div><h3>Create a controlled batch</h3><p>Choose exactly what the Building World should publish.</p></div></div>
        <label>Request type<select value={scenarioType} onChange={(event) => setScenarioType(event.target.value as ScenarioType)}>{Object.entries(scenarioCopy).map(([value, copy]) => <option value={value} key={value}>{copy.label}</option>)}</select></label>
        <div className="generator-type-note"><b>{scenarioCopy[scenarioType].label}</b><span>{scenarioCopy[scenarioType].detail}</span></div>
        <label>Number of requests<div className="quantity-control"><button type="button" aria-label="Decrease request count" onClick={() => setCount((value) => Math.max(1, value - 1))}>−</button><input type="number" min="1" max="20" value={count} onChange={(event) => setCount(Math.min(20, Math.max(1, Number(event.target.value) || 1)))} /><button type="button" aria-label="Increase request count" onClick={() => setCount((value) => Math.min(20, value + 1))}>＋</button></div><small>Up to 20 events per batch</small></label>
        <button className="publish-button" disabled={busy}>Publish {count} request{count === 1 ? "" : "s"}</button>
        {published > 0 && <p className="generator-confirmation">✓ Last command published {published} event{published === 1 ? "" : "s"} to <b>building.events</b>.</p>}
      </form>

      <section className="generator-card cadence-controls">
        <div className="generator-card-title"><span>02</span><div><h3>Automatic cadence</h3><p>Control continuous background request creation.</p></div></div>
        <label>Time between requests<div className="interval-control"><input type="number" min="5" max="3600" value={intervalSeconds} onChange={(event) => setIntervalSeconds(Math.min(3600, Math.max(5, Number(event.target.value) || 5)))} /><span>seconds</span></div></label>
        <div className="cadence-preview"><span>At this rate</span><b>~{Math.max(1, Math.round(3600 / intervalSeconds))}</b><small>requests per hour</small></div>
        <button className={live.simulation.running ? "pause-button" : "publish-button"} disabled={busy} onClick={() => onConfigure(!live.simulation.running, intervalSeconds)}>{live.simulation.running ? "Pause automatic generation" : "Start automatic generation"}</button>
        <button className="save-cadence" disabled={busy} onClick={() => onConfigure(live.simulation.running, intervalSeconds)}>Save cadence</button>
      </section>

      <aside className="generator-card generator-observability">
        <div className="generator-card-title"><span>03</span><div><h3>Delivery visibility</h3><p>Every generated request crosses the pub/sub boundary.</p></div></div>
        <dl><div><dt>Generated</dt><dd>{live.simulation.issues_generated}</dd></div><div><dt>Queued</dt><dd>{live.messaging.pending}</dd></div><div><dt>Acknowledged</dt><dd>{live.messaging.completed}</dd></div><div><dt>Retrying</dt><dd>{live.messaging.retrying}</dd></div><div><dt>Dead letters</dt><dd>{live.messaging.dead_letters}</dd></div><div><dt>Workers</dt><dd>{live.agent.worker_count}</dd></div></dl>
        <div className="generator-route"><span>BUILDING WORLD</span><i>→</i><b>building.events</b><i>→</i><span>OPERATIONS</span></div>
        {live.simulation.last_event ? <div className="generator-latest"><small>LATEST PUBLISHED EVENT</small><b>{live.simulation.last_event.subject}</b><span>{live.simulation.last_event.ticket_id} · {live.simulation.last_event.location_id}</span></div> : <div className="generator-latest"><small>READY</small><b>No generated events yet</b><span>Publish a batch or start the automatic cadence.</span></div>}
      </aside>
    </div>
  </section>;
}
