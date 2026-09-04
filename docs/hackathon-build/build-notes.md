# Build Notes

## 2026-09-03 — Manual-first request generation

- Confirmed from durable message metadata that four unexpected requests came from the `synthetic_occupant` source at the configured 45-second cadence; the user-created request was separately identified as `receptionist_console`.
- Changed clean-start behavior so automatic synthetic ticket creation is paused until explicitly enabled in Request generator.
- Kept the Building World independent: all 60 sensors continue advancing and recording history while automatic request generation is paused.
- Preserved the persisted generator control so operators can deliberately start, stop, and tune continuous scenarios without changing sensor monitoring.

## 2026-09-03 — Live OpenAI reasoning through Strands

- Added an OpenAI Responses API model adapter behind the existing `AgentRuntime` contract while retaining the Bedrock adapter for the AWS stage and the deterministic adapter for repeatable tests.
- The Strands agent now has bounded tools to read the ticket, list all six sensors at the reported floor, inspect individual live readings and rolling histories, search relevant maintenance records, and query authoritative building knowledge.
- Extended typed decisions with exact evidence sensor IDs, a concise diagnosis, provider/model identity, and an observed tool-call trace. Cross-floor or invented sensor IDs are rejected before any workflow action.
- Updated service and incident execution to use the model-selected sensor instead of a fixed Floor 4/7 asset, including a general “burning smell in the Floor 5 pantry” report with no pre-scripted fault.
- Added judge-visible runtime/model identity and `agent.tools_completed` events while keeping API keys out of browser payloads and audit records.
- Verified one live `gpt-5.2` decision through Strands and OpenAI: the model inspected Floor 5 telemetry/history, cited `VOC-05-01` and `PWR-05-01`, and selected approval-gated incident investigation. Offline verification remains deterministic.

## 2026-09-03 — Implementation plan

- The participant redirected the guided flow from interviewing to a concrete implementation plan: “I mean plan for implementation of project” and “can you retry.”
- Product direction: a new Strands-based building-support operations product, not a recreation of the prior incident-investigation application.
- Local-first architecture chosen; AWS migration begins only after the three-ticket local demo is stable.
- MVP paths locked to enquiry, safe service request, and long-running building incident.
- Offers/promotions, real enterprise integrations, multi-tenancy, production authentication, and a multi-agent swarm are cut from the MVP.
- Working title: BuildingOps Concierge.
- Assumed autonomous build mode with balanced visual checkpoints; participant can revise before implementation starts.
- Deepening rounds: 0, per the participant's request to proceed directly to the implementation plan.

## 2026-09-03 — Build checkpoint 1 (items 1–4)

- Added the Python/React monorepo, typed domain contracts, SQLite persistence, leased jobs, FastAPI endpoints, SSE updates, local worker, and a composition root that names every active provider.
- Completed the grounded enquiry path and implemented deterministic action selection for all three hero tickets.
- Added a genuine Strands SDK runtime using typed tools and `AgentDecision` structured output. Live Bedrock invocation remains credential-dependent; offline tests use the explicit deterministic adapter.
- Verification: 6 Python tests passed, frontend unit test passed, frontend production build passed, Strands SDK 1.54 imported successfully, and all three local demo scenarios resolved.
- Git checkpoint could not be created because the workspace `.git` path is read-only in this environment. No implementation work was discarded.

## 2026-09-03 — Local implementation complete (items 5–10)

- Added deterministic pre-tool enforcement, forbidden/approval/autonomous tiers, redacted before/after action records, and idempotent command execution.
- Completed the policy-safe HVAC path, simulated failed verification, approval-gated electrical dispatch, durable technician wait, restart/resume, repair evidence, and verified closure.
- Rebuilt the React UI as a judge-facing operations console with prioritized tickets, intake, approval, action/evidence audit, work-order status, durable-wait messaging, metrics, SSE plus cross-process polling, and responsive layouts.
- Added a one-click three-ticket seed, accelerated time controls, failure injection API, deterministic fixtures, decision/prompt-injection evaluation data, model failure recovery tests, and a source secret scan.
- Added the explicit adapter map in `docs/aws-migration.md`, AWS-stage module seams, a README, MIT license, and transparent reuse disclosure.
- Verification: 13 Python tests and 1 frontend test passed; production UI built; all three scenarios passed three consecutive rehearsals; secret scan passed; the installed Strands SDK and structured-output boundary passed structural verification.
- Visual QA: the live local console rendered successfully at its compact breakpoint; approval → work order → technician completion → independent verification → closure was exercised through the UI.
- Local limitation: a live Bedrock model invocation was not run because AWS credentials are not configured. The default deterministic adapter is deliberately labeled in the UI; `AGENT_RUNTIME=strands` selects the real SDK path.

## 2026-09-03 — Professional operations experience refinement

- Replaced presentation-oriented interface language with a professional operations control center and removed “demo” from every user-facing surface.
- Added a complete request-intake modal, immediate optimistic queue insertion, 600 ms cross-process refresh, and a live six-stage workflow rail from receipt through completion.
- Split triage into durable queued phases so New, Triaging, Working, coordination, verification, and final outcomes remain observable and restart-safe instead of completing inside one worker invocation.
- Added professional workspace API aliases while retaining hidden compatibility routes for existing automation.
- Browser-verified two fresh requests: an unsupported display issue preserved its evidence and escalated safely; a supported comfort issue executed the policy-approved building action, independently verified the result, and closed automatically.
- Verification: 14 Python tests, the frontend unit test and production build, all three workflow checks, and the secret scan passed.

## 2026-09-03 — Receptionist workplace redesign

- Reframed the primary user from a facilities operator to the Building A receptionist, with a dense enterprise work surface inspired by workplace service systems.
- Replaced the generic request queue with an email-style inbox, incoming-message reader, linked agent workflow, approval controls, and simulated email preview clearly marked as not externally sent.
- Added linked occupant master records beside each request, including role, company, workplace, contact, and access context.
- Added Building and Occupants registers with floor/zone status, occupancy, sensor readings and thresholds, building health, request history counts, and working directory search.
- Preserved live ticket updates, autonomous actions, verification, approvals, long-running technician work, local data boundaries, and the existing AWS-replaceable service ports.
- Verification: 14 Python tests, frontend test and production build, all three workflow checks, and the secret scan passed.

## 2026-09-03 — Ticket worklist and building digital twin

- Added a dedicated Tickets module separate from request email, including an SAP-style worklist, open/assigned filters, next-action status, and a prominent “My pending actions” queue for approvals and exceptions assigned to the receptionist.
- Rebuilt Building as a black digital-twin workspace with a true interactive WebGL model of a ten-story smart building, floor selection from the model or building stack, orbit and zoom controls, and live operational status colors.
- Added ten complete floor master records, selectable schematic floor maps, room names, area, occupancy, use, open-ticket counts, and normal/warning/critical health.
- Added a fifty-device sensor register spanning every floor with temperature, CO₂, humidity, occupancy, and electrical telemetry, plus thresholds, health, and last-signal timing. Local simulation is explicitly labeled.
- Lazy-loaded the 3D scene so the receptionist inbox and Tickets worklist remain lightweight.

## 2026-09-03 — Continuous building world and agent live view

- Split the running product into two independent engines connected only through the durable ticket boundary: a building-world simulator that produces occupant requests and equipment conditions, and an operations worker that consumes and resolves them.
- Added six rotating scenarios across enquiries, comfort requests, access coordination, electrical incidents, delivery questions, and device faults. Building incidents mutate the local sensor/asset state before ticket creation so investigations inspect meaningful evidence.
- Added durable simulator progress, configurable cadence, restart-safe scheduling, a manual event pulse, and explicit local/AWS adapter boundaries.
- Added the Agent live workspace with world-engine and operations-engine status, active workflow progress, public agent decisions and tool outcomes, and cumulative actions, resolutions, human-needed cases, and estimated human touches saved.
- Live verification: the simulator generated an amenities enquiry and a warm-room condition; the agent answered the enquiry and autonomously adjusted and independently verified the HVAC outcome.
- Verification: 16 Python tests, 2 frontend test files, the production UI build, all three workflow checks, and the secret scan passed.

## 2026-09-03 — Autopilot overview and local service boundaries

- The participant incorporated external critique that the interface overstated receptionist workload and asked for explicit Building World, ticket-clearing, and UI services.
- Added a receptionist-first Overview led by autonomy, avoided touches, Autopilot-owned work, external waits, and the intentionally small human-decision queue. Only human decisions receive a navigation badge.
- Reworked Requests and Tickets language so every row makes Autopilot ownership, external waiting, or human responsibility explicit.
- Reframed Agent Activity around parallel ticket workflow instances, a bounded worker pool, public evidence, and a single policy boundary. The simulator control is now subordinate and labeled as a local synthetic feed.
- Grouped local execution into three service boundaries: Operations (API plus configurable three-worker pool), Building World, and Web UI. Multiple workers claim one bounded job each, allowing independent tickets to progress concurrently.
- Expanded the building activity catalog from six to ten varied scenarios, added grounded operational knowledge, and suppressed recently repeated subjects.
- Verification: 17 Python tests, 2 frontend test files, the production UI build, all three lifecycle checks, the safety decision evaluation, and the secret scan passed. The combined three-service launcher reported Building World online, Operations online, and three configured workers.

## 2026-09-03 — Durable pub/sub and workflow recovery

- The participant strengthened the service boundary: Building World and Operations must communicate through pub/sub, with retry, idempotency, and saved workflow state.
- Added SQLite-backed durable topics and per-subscription deliveries with leases, at-least-once semantics, exponential backoff, configurable attempt limits, acknowledgements, and a terminal dead-letter state.
- Building World now publishes `building.request.detected`; the Operations intake consumer materializes the ticket idempotently. Due workflow outbox jobs publish to `workflow.commands`, which the worker pool consumes independently.
- Added a versioned `WF-*` checkpoint for each ticket recording current step, ticket version, wait reason, wake time, attempt, and terminal outcome. Redelivery remains safe through stable message/job/event/action identifiers and status guards.
- Updated Agent Activity to expose the message broker, queued deliveries, retries, dead letters, acknowledgement count, and checkpoint version.
- Verification: 20 Python tests, 2 frontend tests, production UI build, all three lifecycle checks, a real three-process pub/sub run, and the source secret scan passed.

## 2026-09-03 — Controlled request generation

- Added a compact Request generator navigation tab for controlling the Building World during testing and presentation.
- Operators can publish 1–20 requests at once, select a mixed batch or only enquiries, service requests, or incidents, change the continuous-generation interval, and pause or resume the background source.
- Generator controls publish through `building.events`; they do not call the ticket workflow directly. The page exposes generated, queued, acknowledged, retrying, dead-lettered, and worker totals.
- Verification: 21 Python tests, 2 frontend tests, production UI build, and a live three-worker run that published three enquiry events, acknowledged all deliveries, and resolved all generated requests autonomously.
