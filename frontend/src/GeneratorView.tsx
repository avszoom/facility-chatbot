import { FormEvent, useState } from "react";

import { floors } from "./facility";
import type { CustomRequestInput, LiveOperations, PublishedRequest, RequestType } from "./types";

type ScenarioType = "all" | RequestType;
type ConditionType = CustomRequestInput["condition_type"];

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
  floor: number;
  room: string;
  condition: ConditionType;
  agentOutcome: string;
};

const requestPresets: Record<RequestType, RequestPreset> = {
  enquiry: {
    label: "Knowledge enquiry", shortLabel: "Knowledge",
    detail: "A resident asks about amenities, access, deliveries, or a building procedure.",
    subject: "Fitness center hours", description: "What time does the fitness center close tonight?",
    requester: "Priya Shah", floor: 2, room: "Fitness center", condition: "normal",
    agentOutcome: "Search approved residential knowledge, reply to the resident, and close the ticket.",
  },
  service_request: {
    label: "Service request", shortLabel: "Service",
    detail: "A resident reports an apartment problem that may allow a policy-safe operational change.",
    subject: "Apartment 4B is too warm",
    description: "My living room feels hot even though the thermostat is set correctly. Can building operations check it?",
    requester: "Marcus Lee", floor: 4, room: "Apartment 4B", condition: "temperature_high",
    agentOutcome: "Correlate the ticket with telemetry, perform an allowed adjustment, and verify recovery.",
  },
  incident: {
    label: "Safety incident", shortLabel: "Safety",
    detail: "A resident reports evidence of a potentially unsafe condition requiring investigation.",
    subject: "Unusual burning smell outside Apartment 5E",
    description: "There is a strong burning smell in the corridor outside Apartment 5E. I cannot see smoke, but the odor is getting stronger.",
    requester: "Building Resident", floor: 5, room: "Apartment 5E", condition: "smoke_or_odor",
    agentOutcome: "Correlate the report with local evidence, create a qualified technician work order, monitor progress, and verify clearance.",
  },
};

const conditionOptions: Record<RequestType, Array<{ value: ConditionType; label: string }>> = {
  enquiry: [{ value: "normal", label: "No equipment failure" }],
  service_request: [
    { value: "temperature_high", label: "Temperature above comfort range" },
    { value: "temperature_low", label: "Temperature below comfort range" },
    { value: "air_quality", label: "Air quality degradation" },
  ],
  incident: [
    { value: "smoke_or_odor", label: "Smoke / unusual odor alarm" },
    { value: "electrical_overheat", label: "Electrical cabinet overheating" },
  ],
};

const scenarioCopy: Record<ScenarioType, { label: string; detail: string }> = {
  all: { label: "Mixed scenarios", detail: "Rotate through the full building scenario catalog." },
  enquiry: { label: "Knowledge enquiries", detail: "Hours, access, visitors, deliveries, amenities, and procedures." },
  service_request: { label: "Service requests", detail: "Resident reports paired with relevant apartment telemetry." },
  incident: { label: "Safety incidents", detail: "Resident reports paired with critical local sensor alarms." },
};

function locationIdFor(floor: number, room: string) {
  if (floor === 2 && room === "Fitness center") return "BLDG-A-F02-FITNESS";
  if (floor === 1 && room === "Main lobby") return "BLDG-A-LOBBY";
  if (floor === 4 && room === "Apartment 4B") return "BLDG-A-F04-APT-4B";
  if (floor === 7 && room === "East residential wing") return "BLDG-A-F07-EAST";
  const roomCode = room.toUpperCase().replaceAll("&", "AND").replace(/[^A-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `BLDG-A-F${String(floor).padStart(2, "0")}-${roomCode}`;
}

function sensorIdFor(condition: ConditionType, floor: number) {
  if (condition === "normal") return null;
  if (condition === "temperature_high" || condition === "temperature_low") return `TMP-${String(floor).padStart(2, "0")}-01`;
  if (condition === "air_quality" || condition === "smoke_or_odor") return `VOC-${String(floor).padStart(2, "0")}-01`;
  return floor === 7 ? "ELEC-7A" : `PWR-${String(floor).padStart(2, "0")}-01`;
}

export function GeneratorView({ live, busy, onPublishRequest, onGenerate, onOpenActivity, onOpenBuilding }: Props) {
  const initial = requestPresets.enquiry;
  const [requestType, setRequestType] = useState<RequestType>("enquiry");
  const [conditionType, setConditionType] = useState<ConditionType>(initial.condition);
  const [subject, setSubject] = useState(initial.subject);
  const [description, setDescription] = useState(initial.description);
  const [requester, setRequester] = useState(initial.requester);
  const [selectedFloor, setSelectedFloor] = useState(initial.floor);
  const [selectedRoom, setSelectedRoom] = useState(initial.room);
  const [technicianDelaySeconds, setTechnicianDelaySeconds] = useState(30);
  const [receipt, setReceipt] = useState<PublishedRequest | null>(null);
  const [count, setCount] = useState(3);
  const [scenarioType, setScenarioType] = useState<ScenarioType>("all");
  const [published, setPublished] = useState(0);

  const chooseType = (nextType: RequestType) => {
    const preset = requestPresets[nextType];
    setRequestType(nextType); setConditionType(preset.condition); setSubject(preset.subject);
    setDescription(preset.description); setRequester(preset.requester);
    setSelectedFloor(preset.floor); setSelectedRoom(preset.room); setReceipt(null);
  };
  const chooseFloor = (floorNumber: number) => {
    const floor = floors.find((item) => item.number === floorNumber)!;
    setSelectedFloor(floorNumber); setSelectedRoom(floor.rooms[0]); setReceipt(null);
  };
  const submitRequest = async (event: FormEvent) => {
    event.preventDefault();
    setReceipt(await onPublishRequest({
      request_type: requestType, condition_type: conditionType, subject, description, requester,
      location_id: locationIdFor(selectedFloor, selectedRoom),
      technician_delay_seconds: technicianDelaySeconds,
    }));
  };
  const submitBatch = async (event: FormEvent) => {
    event.preventDefault(); await onGenerate(count, scenarioType); setPublished(count);
  };

  const preset = requestPresets[requestType];
  const floor = floors.find((item) => item.number === selectedFloor)!;
  const sensorId = sensorIdFor(conditionType, selectedFloor);
  const worldEffect = sensorId
    ? `${sensorId} at Floor ${selectedFloor} · ${selectedRoom} will enter ${conditionType === "smoke_or_odor" || conditionType === "electrical_overheat" ? "critical alarm" : "warning"}.`
    : `Floor ${selectedFloor} · ${selectedRoom} remains healthy; only the resident request is published.`;
  const condition = live.simulation.last_event?.condition.condition;
  const publishedSensor = receipt?.payload.scenario.condition.sensor_id;

  return <section className="generator-view">
    <header className="generator-heading"><div><p>RESIDENTIAL TOWER CONTROL</p><h2>Create a real resident scenario</h2><span>Select any apartment or amenity, publish the resident report, and induce only the matching building condition.</span></div><span className="generator-state paused"><i />Console-only publishing</span></header>

    <div className="generator-layout request-scenario-layout">
      <form className="generator-card request-composer" onSubmit={submitRequest}>
        <div className="generator-card-title"><span>01</span><div><h3>Raise a resident request</h3><p>Compose the report exactly as the concierge would receive it.</p></div></div>
        <fieldset className="request-type-picker"><legend>What kind of request is this?</legend><div>{(Object.keys(requestPresets) as RequestType[]).map((type) => <button type="button" className={requestType === type ? "active" : ""} onClick={() => chooseType(type)} key={type}><b>{requestPresets[type].shortLabel}</b><span>{type === "enquiry" ? "Information only" : type === "service_request" ? "Operational change" : "Safety response"}</span></button>)}</div></fieldset>
        <div className="request-type-explanation"><b>{preset.label}</b><span>{preset.detail}</span></div>

        <section className="scenario-location-picker">
          <div className="location-picker-head"><div><small>BUILDING LOCATION</small><b>Floor {selectedFloor} · {selectedRoom}</b></div><span>{locationIdFor(selectedFloor, selectedRoom)}</span></div>
          <div className="location-picker-body">
            <div className="mini-floor-stack" aria-label="Select building floor">{[...floors].sort((a, b) => b.number - a.number).map((item) => <button type="button" className={item.number === selectedFloor ? "active" : ""} onClick={() => chooseFloor(item.number)} key={item.number}><i />F{String(item.number).padStart(2, "0")}</button>)}</div>
            <div className="scenario-floor-map"><header><div><small>FLOOR {String(selectedFloor).padStart(2, "0")}</small><b>{floor.name}</b></div><span>{floor.use}</span></header><div className="scenario-map-grid">{floor.rooms.map((room, index) => <button type="button" className={`map-space space-${index + 1} ${selectedRoom === room ? "active" : ""}`} onClick={() => { setSelectedRoom(room); setReceipt(null); }} key={room}><b>{room}</b><span>{selectedRoom === room ? "Selected location" : "Select space"}</span></button>)}<div className="scenario-map-core"><b>BUILDING CORE</b><span>Lift · Stair · Services</span></div></div></div>
          </div>
        </section>

        <div className="generator-form-grid"><label>Requester<input value={requester} onChange={(event) => setRequester(event.target.value)} required minLength={2} /></label><label>Simulated building condition<select value={conditionType} onChange={(event) => { setConditionType(event.target.value as ConditionType); setReceipt(null); }}>{conditionOptions[requestType].map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label></div>
        {requestType !== "enquiry" && <label className="technician-duration">Technician work duration<div><input type="range" min="5" max="180" step="5" value={technicianDelaySeconds} onChange={(event) => { setTechnicianDelaySeconds(Number(event.target.value)); setReceipt(null); }} /><output>{technicianDelaySeconds}s</output></div><small>Accelerated wall-clock time. The ticket remains ongoing and sensors stay abnormal until the technician finishes.</small></label>}
        <label>Subject<input value={subject} onChange={(event) => setSubject(event.target.value)} required minLength={3} maxLength={120} /></label>
        <label>Resident message<textarea value={description} onChange={(event) => setDescription(event.target.value)} required minLength={3} maxLength={2000} rows={4} placeholder="Describe what the resident is asking or reporting…" /><small>The agent classifies the text independently; the selected condition controls the simulated sensor evidence.</small></label>
        <button className="publish-button" disabled={busy}>Create request and building scenario</button>
        {receipt && <div className="request-receipt"><span>✓</span><div><b>{receipt.payload.ticket_id} published</b><p>Request and {publishedSensor || "normal building state"} are correlated on <strong>building.events</strong>{requestType !== "enquiry" ? `; technician work is configured for ${receipt.payload.scenario.technician_delay_seconds ?? technicianDelaySeconds} seconds if dispatched` : ""}.</p>{receipt.payload.scenario.normalization && <em>{receipt.payload.scenario.normalization}</em>}<div><button type="button" onClick={onOpenActivity}>Watch agent activity</button><button type="button" onClick={onOpenBuilding}>View building sensors</button></div></div></div>}
      </form>

      <section className="generator-card request-lifecycle"><div className="generator-card-title"><span>02</span><div><h3>What happens next</h3><p>One correlated scenario, visible across the product.</p></div></div><div className={`world-effect ${requestType}`}><small>BUILDING WORLD EFFECT</small><b>{worldEffect}</b>{sensorId && <span className="alarm-chip">● Correlated sensors remain abnormal through the {technicianDelaySeconds}s work window</span>}</div><ol><li><i>1</i><div><b>Publish</b><span>The report, condition, and timing enter durable pub/sub together.</span></div></li><li><i>2</i><div><b>Create workflow</b><span>An intake worker idempotently creates the ticket and checkpoint.</span></div></li><li><i>3</i><div><b>Investigate</b><span>The agent reads the request, policy, knowledge, correlated sensors, and history.</span></div></li><li><i>4</i><div><b>Act or coordinate</b><span>{preset.agentOutcome}</span></div></li><li><i>5</i><div><b>Recover and verify</b><span>Technician findings drive repair; sensor history records recovery before closure.</span></div></li></ol></section>

      <aside className="generator-card generator-observability"><div className="generator-card-title"><span>03</span><div><h3>Live delivery</h3><p>Requests and alarms cross the same service boundary.</p></div></div><dl><div><dt>Generated</dt><dd>{live.simulation.issues_generated}</dd></div><div><dt>Queued</dt><dd>{live.messaging.pending}</dd></div><div><dt>Acknowledged</dt><dd>{live.messaging.completed}</dd></div><div><dt>Retrying</dt><dd>{live.messaging.retrying}</dd></div><div><dt>Dead letters</dt><dd>{live.messaging.dead_letters}</dd></div><div><dt>Workers</dt><dd>{live.agent.worker_count}</dd></div></dl><div className="generator-route"><span>BUILDING WORLD</span><i>→</i><b>building.events</b><i>→</i><span>OPERATIONS</span></div>{live.simulation.last_event ? <div className="generator-latest"><small>LATEST PUBLISHED EVENT</small><b>{live.simulation.last_event.subject}</b><span>{live.simulation.last_event.ticket_id} · {live.simulation.last_event.location_id}</span><em className={condition === "normal" ? "normal" : "alarm"}>{condition === "normal" ? "Sensors unchanged" : `Condition: ${condition?.replaceAll("_", " ")}`}</em></div> : <div className="generator-latest"><small>READY</small><b>No generated events yet</b><span>Create a request or explicitly publish a catalog load test.</span></div>}</aside>

      <form className="generator-card batch-controls" onSubmit={submitBatch}><div className="generator-card-title"><span>04</span><div><h3>Load and concurrency test</h3><p>Publish multiple catalog scenarios to exercise parallel workflows.</p></div></div><div className="batch-row"><label>Scenario mix<select value={scenarioType} onChange={(event) => setScenarioType(event.target.value as ScenarioType)}>{Object.entries(scenarioCopy).map(([value, copy]) => <option value={value} key={value}>{copy.label}</option>)}</select></label><label>Number of requests<div className="quantity-control"><button type="button" aria-label="Decrease request count" onClick={() => setCount((value) => Math.max(1, value - 1))}>−</button><input type="number" min="1" max="20" value={count} onChange={(event) => setCount(Math.min(20, Math.max(1, Number(event.target.value) || 1)))} /><button type="button" aria-label="Increase request count" onClick={() => setCount((value) => Math.min(20, value + 1))}>＋</button></div></label></div><div className="generator-type-note"><b>{scenarioCopy[scenarioType].label}</b><span>{scenarioCopy[scenarioType].detail}</span></div><button className="publish-button" disabled={busy}>Publish {count} catalog scenario{count === 1 ? "" : "s"}</button>{published > 0 && <p className="generator-confirmation">✓ Last load test published {published} event{published === 1 ? "" : "s"}.</p>}</form>

      <section className="generator-card cadence-controls"><div className="generator-card-title"><span>05</span><div><h3>Manual intake boundary</h3><p>Background ticket generation is disabled.</p></div></div><div className="cadence-preview"><span>Building telemetry</span><b>LIVE</b><small>60 sensors continue updating without creating tickets</small></div><div className="generator-type-note"><b>Requests require an operator action</b><span>Use the request composer, New request, Trigger test event, or the explicit load test. No timer publishes tickets.</span></div></section>
    </div>
  </section>;
}
