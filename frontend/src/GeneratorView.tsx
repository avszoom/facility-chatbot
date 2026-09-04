import { FormEvent, useEffect, useState } from "react";

import type { CustomRequestInput, LiveOperations, PublishedRequest, RequestType } from "./types";

type ScenarioType = "all" | RequestType;

type Props = {
  live: LiveOperations;
  busy: boolean;
  onPublishRequest: (request: CustomRequestInput) => Promise<PublishedRequest>;
  onGenerate: (count: number, scenarioType: ScenarioType) => Promise<void>;
  onConfigure: (running: boolean, intervalSeconds: number) => Promise<void>;
  onOpenActivity: () => void;
  onOpenBuilding: () => void;
};

type RequestPreset = {
  label: string;
  shortLabel: string;
  detail: string;
  subject: string;
  description: string;
  requester: string;
  locationId: string;
  worldEffect: string;
  agentOutcome: string;
};

const requestPresets: Record<RequestType, RequestPreset> = {
  enquiry: {
    label: "Knowledge enquiry",
    shortLabel: "Knowledge",
    detail: "An occupant asks for building information, hours, access, or a procedure.",
    subject: "Fitness center hours",
    description: "What time does the fitness center close tonight?",
    requester: "Priya Shah",
    locationId: "BLDG-A-F01-FITNESS",
    worldEffect: "Creates an occupant request. Sensor values remain normal.",
    agentOutcome: "Search approved building knowledge, reply to the occupant, and close the ticket.",
  },
  service_request: {
    label: "Service request",
    shortLabel: "Service",
    detail: "An occupant reports a comfort or routine building problem that may allow a safe adjustment.",
    subject: "Conference Room 4B is too warm",
    description: "The room feels hot during our client meeting. Can facilities check the temperature?",
    requester: "Marcus Lee",
    locationId: "BLDG-A-F04-CONF-4B",
    worldEffect: "Raises the Floor 4 temperature to 77.2°F and publishes the occupant request.",
    agentOutcome: "Correlate the ticket with HVAC telemetry, apply an approved setpoint, and verify recovery.",
  },
  incident: {
    label: "Safety incident",
    shortLabel: "Safety",
    detail: "An occupant reports evidence of a potentially unsafe condition requiring investigation.",
    subject: "Flickering lights and burning smell on Floor 7",
    description: "Lights are flickering near the east offices and we smell hot plastic.",
    requester: "Elena Garcia",
    locationId: "BLDG-A-F07-EAST",
    worldEffect: "Trips the Floor 7 electrical panel alarm to 126.4°F and publishes the incident.",
    agentOutcome: "Collect evidence, apply safety policy, request dispatch approval, then track and verify repair.",
  },
};

const scenarioCopy: Record<ScenarioType, { label: string; detail: string }> = {
  all: { label: "Mixed scenarios", detail: "Rotate through the full building scenario catalog." },
  enquiry: { label: "Knowledge enquiries", detail: "Hours, access, visitors, deliveries, amenities, and procedures." },
  service_request: { label: "Service requests", detail: "Comfort conditions paired with abnormal telemetry." },
  incident: { label: "Safety incidents", detail: "Occupant reports paired with safety sensor alarms." },
};

export function GeneratorView({ live, busy, onPublishRequest, onGenerate, onConfigure, onOpenActivity, onOpenBuilding }: Props) {
  const [requestType, setRequestType] = useState<RequestType>("enquiry");
  const [subject, setSubject] = useState(requestPresets.enquiry.subject);
  const [description, setDescription] = useState(requestPresets.enquiry.description);
  const [requester, setRequester] = useState(requestPresets.enquiry.requester);
  const [locationId, setLocationId] = useState(requestPresets.enquiry.locationId);
  const [receipt, setReceipt] = useState<PublishedRequest | null>(null);
  const [count, setCount] = useState(3);
  const [scenarioType, setScenarioType] = useState<ScenarioType>("all");
  const [intervalSeconds, setIntervalSeconds] = useState(live.simulation.interval_seconds);
  const [published, setPublished] = useState(0);

  useEffect(() => setIntervalSeconds(live.simulation.interval_seconds), [live.simulation.interval_seconds]);

  const chooseType = (nextType: RequestType) => {
    const preset = requestPresets[nextType];
    setRequestType(nextType);
    setSubject(preset.subject);
    setDescription(preset.description);
    setRequester(preset.requester);
    setLocationId(preset.locationId);
    setReceipt(null);
  };

  const submitRequest = async (event: FormEvent) => {
    event.preventDefault();
    const nextReceipt = await onPublishRequest({ request_type: requestType, subject, description, requester, location_id: locationId });
    setReceipt(nextReceipt);
  };

  const submitBatch = async (event: FormEvent) => {
    event.preventDefault();
    await onGenerate(count, scenarioType);
    setPublished(count);
  };

  const preset = requestPresets[requestType];
  const condition = live.simulation.last_event?.condition.condition;

  return <section className="generator-view">
    <header className="generator-heading">
      <div><p>BUILDING WORLD CONTROL</p><h2>Create a real request scenario</h2><span>Pair an occupant report with the building conditions the operations agents would actually observe.</span></div>
      <span className={`generator-state ${live.simulation.running ? "running" : "paused"}`}><i />{live.simulation.running ? "Automatic generation running" : "Automatic generation paused"}</span>
    </header>

    <div className="generator-layout request-scenario-layout">
      <form className="generator-card request-composer" onSubmit={submitRequest}>
        <div className="generator-card-title"><span>01</span><div><h3>Raise an occupant request</h3><p>Choose the situation, then edit the message as if it arrived at reception.</p></div></div>
        <fieldset className="request-type-picker">
          <legend>What kind of request is this?</legend>
          <div>{(Object.keys(requestPresets) as RequestType[]).map((type) => <button type="button" className={requestType === type ? "active" : ""} onClick={() => chooseType(type)} key={type}><b>{requestPresets[type].shortLabel}</b><span>{type === "enquiry" ? "Information only" : type === "service_request" ? "Operational change" : "Safety response"}</span></button>)}</div>
        </fieldset>
        <div className="request-type-explanation"><b>{preset.label}</b><span>{preset.detail}</span></div>
        <div className="generator-form-grid">
          <label>Requester<input value={requester} onChange={(event) => setRequester(event.target.value)} required minLength={2} /></label>
          <label>Building location<select value={locationId} onChange={(event) => setLocationId(event.target.value)}><option value="BLDG-A-F01-FITNESS">Floor 1 · Fitness Center</option><option value="BLDG-A-F04-CONF-4B">Floor 4 · Conference Room 4B</option><option value="BLDG-A-F07-EAST">Floor 7 · East Office Zone</option><option value="BLDG-A-LOBBY">Ground · Main Lobby</option></select></label>
        </div>
        <label>Subject<input value={subject} onChange={(event) => setSubject(event.target.value)} required minLength={3} maxLength={120} /></label>
        <label>Occupant message<textarea value={description} onChange={(event) => setDescription(event.target.value)} required minLength={3} maxLength={2000} rows={4} placeholder="Describe what the occupant is asking or reporting…" /><small>The agent will classify the message independently; the selected type controls the simulated world condition.</small></label>
        <button className="publish-button" disabled={busy}>Create request scenario</button>
        {receipt && <div className="request-receipt"><span>✓</span><div><b>{receipt.payload.ticket_id} published</b><p>Accepted on <strong>building.events</strong>. An operations worker will create and start workflow WF-{receipt.payload.ticket_id}.</p><div><button type="button" onClick={onOpenActivity}>Watch agent activity</button><button type="button" onClick={onOpenBuilding}>View building sensors</button></div></div></div>}
      </form>

      <section className="generator-card request-lifecycle">
        <div className="generator-card-title"><span>02</span><div><h3>What happens next</h3><p>One correlated scenario, visible across the product.</p></div></div>
        <div className={`world-effect ${requestType}`}><small>BUILDING WORLD EFFECT</small><b>{preset.worldEffect}</b>{requestType !== "enquiry" && <span className="alarm-chip">● Sensor alarm induced</span>}</div>
        <ol>
          <li><i>1</i><div><b>Publish</b><span>The report and condition enter durable pub/sub together.</span></div></li>
          <li><i>2</i><div><b>Create workflow</b><span>An intake worker idempotently creates the ticket and checkpoint.</span></div></li>
          <li><i>3</i><div><b>Investigate</b><span>The agent reads the request, policy, knowledge, and live building evidence.</span></div></li>
          <li><i>4</i><div><b>Act or coordinate</b><span>{preset.agentOutcome}</span></div></li>
          <li><i>5</i><div><b>Update everywhere</b><span>Agent Activity streams each step; Tickets and Building refresh live.</span></div></li>
        </ol>
      </section>

      <aside className="generator-card generator-observability">
        <div className="generator-card-title"><span>03</span><div><h3>Live delivery</h3><p>Requests and alarms cross the same service boundary.</p></div></div>
        <dl><div><dt>Generated</dt><dd>{live.simulation.issues_generated}</dd></div><div><dt>Queued</dt><dd>{live.messaging.pending}</dd></div><div><dt>Acknowledged</dt><dd>{live.messaging.completed}</dd></div><div><dt>Retrying</dt><dd>{live.messaging.retrying}</dd></div><div><dt>Dead letters</dt><dd>{live.messaging.dead_letters}</dd></div><div><dt>Workers</dt><dd>{live.agent.worker_count}</dd></div></dl>
        <div className="generator-route"><span>BUILDING WORLD</span><i>→</i><b>building.events</b><i>→</i><span>OPERATIONS</span></div>
        {live.simulation.last_event ? <div className="generator-latest"><small>LATEST PUBLISHED EVENT</small><b>{live.simulation.last_event.subject}</b><span>{live.simulation.last_event.ticket_id} · {live.simulation.last_event.location_id}</span><em className={condition === "normal" ? "normal" : "alarm"}>{condition === "normal" ? "Sensors unchanged" : `Condition: ${condition?.replaceAll("_", " ")}`}</em></div> : <div className="generator-latest"><small>READY</small><b>No generated events yet</b><span>Create a request scenario or start the automatic cadence.</span></div>}
      </aside>

      <form className="generator-card batch-controls" onSubmit={submitBatch}>
        <div className="generator-card-title"><span>04</span><div><h3>Load and concurrency test</h3><p>Publish multiple realistic catalog scenarios to exercise parallel workflows.</p></div></div>
        <div className="batch-row"><label>Scenario mix<select value={scenarioType} onChange={(event) => setScenarioType(event.target.value as ScenarioType)}>{Object.entries(scenarioCopy).map(([value, copy]) => <option value={value} key={value}>{copy.label}</option>)}</select></label><label>Number of requests<div className="quantity-control"><button type="button" aria-label="Decrease request count" onClick={() => setCount((value) => Math.max(1, value - 1))}>−</button><input type="number" min="1" max="20" value={count} onChange={(event) => setCount(Math.min(20, Math.max(1, Number(event.target.value) || 1)))} /><button type="button" aria-label="Increase request count" onClick={() => setCount((value) => Math.min(20, value + 1))}>＋</button></div></label></div>
        <div className="generator-type-note"><b>{scenarioCopy[scenarioType].label}</b><span>{scenarioCopy[scenarioType].detail}</span></div>
        <button className="publish-button" disabled={busy}>Publish {count} catalog scenario{count === 1 ? "" : "s"}</button>
        {published > 0 && <p className="generator-confirmation">✓ Last load test published {published} event{published === 1 ? "" : "s"}.</p>}
      </form>

      <section className="generator-card cadence-controls">
        <div className="generator-card-title"><span>05</span><div><h3>Automatic cadence</h3><p>Control continuous background request and condition creation.</p></div></div>
        <label>Time between scenarios<div className="interval-control"><input type="number" min="5" max="3600" value={intervalSeconds} onChange={(event) => setIntervalSeconds(Math.min(3600, Math.max(5, Number(event.target.value) || 5)))} /><span>seconds</span></div></label>
        <div className="cadence-preview"><span>At this rate</span><b>~{Math.max(1, Math.round(3600 / intervalSeconds))}</b><small>scenarios per hour</small></div>
        <button className={live.simulation.running ? "pause-button" : "publish-button"} disabled={busy} onClick={() => onConfigure(!live.simulation.running, intervalSeconds)}>{live.simulation.running ? "Pause automatic generation" : "Start automatic generation"}</button>
        <button className="save-cadence" disabled={busy} onClick={() => onConfigure(live.simulation.running, intervalSeconds)}>Save cadence</button>
      </section>
    </div>
  </section>;
}
