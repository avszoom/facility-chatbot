# Technical Spec — BuildingOps Concierge

## Overview

Build a new local-first application from scratch. A deterministic ticket state machine owns safety, permissions, durability, and closure rules. Strands Agents supplies bounded intelligence at classification and decision points. Tools perform all reads and writes, and hooks record auditable lifecycle events.

The same domain services run locally and on AWS. Persistence, event scheduling, notifications, telemetry, work orders, and agent invocation sit behind interfaces so the cloud phase replaces adapters rather than rewriting business logic.

## Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **Agent:** Strands Agents SDK for Python with Pydantic structured output, custom tools, and lifecycle hooks.
- **Model:** OpenAI Responses API through Strands for the verified local build; Amazon Bedrock through the same runtime port for AWS deployment; deterministic fixtures only for tests.
- **Local persistence:** SQLite in WAL mode.
- **Local workflow:** a transactional SQLite outbox publishes to a durable pub/sub adapter; a configurable pool of Operations subscribers consumes leased deliveries. No in-memory timer or process-local queue is a source of truth.
- **Frontend:** React, TypeScript, Vite, TanStack Query, React Router, CSS variables; avoid a heavyweight component system.
- **Streaming:** Server-Sent Events with API refetch on reconnect.
- **Tests:** pytest, FastAPI TestClient/httpx, Vitest, React Testing Library, and one Playwright hero-flow test if time permits.
- **Packaging:** `uv` or standard virtual environment for Python; npm for frontend; Makefile for one-command setup/run/test.

Official references:

- [Strands tools](https://strandsagents.com/docs/user-guide/concepts/tools/)
- [Strands hooks](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/)
- [Strands structured output](https://strandsagents.com/docs/examples/structured_output/)
- [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
- [AgentCore CLI deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html)
- [AgentCore observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)

## Architecture

```text
React Autopilot Workspace
        │ REST + SSE
        ▼
Operations service ─────────────────┐
  FastAPI + worker pool             │
        │                           │
        ▼                           ▼
Ticket service                 Approval service
        │                           │
        ▼                           │
SQLite repositories ◀──────────────┘
        │ transactional workflow outbox + checkpoints
        ▼
Durable pub/sub topics
  building.events ──► operations.intake subscription
  workflow.commands ► operations.workflow subscription
        │ leased at-least-once delivery
        ▼
Isolated Strands agent execution
        │ typed decision + tool calls
        ▼
Policy gateway
   ├── knowledge tool
   ├── asset/telemetry tools
   ├── safe-command tool
   ├── work-order tool
   ├── notification tool
   └── verification tool
```

The agent never directly edits database records or calls arbitrary code. The worker supplies current ticket context and eligible actions. The policy gateway validates every write even if the model requests it.

## Domain Model

### Ticket

- `id`, `subject`, `description`, `requester`, `location_id`
- `kind`: `enquiry | service_request | incident`
- `priority`: `low | normal | high | emergency`
- `status`: `new | triaging | working | needs_approval | waiting_technician | waiting_verification | resolved | escalated`
- `safety_flags`, `confidence`, `sla_due_at`, `assigned_owner`
- `created_at`, `updated_at`, `resolved_at`, `version`

### TicketEvent

Append-only event with stable `event_id`, ticket version, actor, event type, public summary, structured payload, timestamp, and correlation ID.

### WorkflowJob

Persisted job with deterministic ID, ticket ID, expected ticket version, kind, payload, availability time, lease, attempt count, and terminal status.

### ActionRecord

Records proposed action, risk tier, policy rule, before state, requested parameters, approval, execution result, after state, verification, and idempotency key.

### WorkOrder

Records ticket, asset, location, trade, priority, requested procedure, technician, status, due time, completion notes, and parts.

## State Machine

```text
new → triaging → working
                  ├─ grounded answer → resolved
                  ├─ safe command → waiting_verification → resolved/escalated
                  ├─ approval required → needs_approval → working/escalated
                  ├─ physical work → waiting_technician → waiting_verification
                  └─ unsafe/uncertain → escalated
```

Only the domain service transitions state. The agent returns a proposed `NextDecision`; it cannot declare a ticket resolved. Closure requires a domain-specific verifier.

## Agent Design

### FacilityOps Orchestrator

Implements: `prd.md > Epic 2`, `Epic 3`, `Epic 4`, `Epic 5`

Use one primary Strands agent with a focused system prompt, ticket context, eligible actions, and typed tools. The agent produces `NextDecision` as structured output:

- intent and priority
- safety flags
- current objective
- selected action
- tool arguments
- confidence and evidence references
- user-facing update draft
- requested wake-up or escalation reason

Do not create a multi-agent swarm for the MVP. If specialist behavior is useful, expose triage, investigation, and response drafting as explicit bounded functions or later Strands agents behind the same interface.

One agent role definition can have several isolated executions at the same time. Each
execution is scoped to one ticket/workflow correlation ID, and each worker claims only
one bounded workflow step. `AGENT_WORKER_COUNT` limits local concurrency. Waiting for a
person, technician, or verification window persists state and releases the worker.

Every message has a stable message ID, correlation ID, and idempotency key. Consumers
acknowledge only after the bounded workflow step succeeds. Failures use exponential
backoff and move to a dead-letter state after the configured attempt limit. Ticket
versions, deterministic event/action IDs, and idempotent tool writes make redelivery
safe. A versioned `WorkflowState` checkpoint records the last completed step, wait
reason, wake time, and ticket version for restart recovery and operator visibility.

### Tools

Implements: `prd.md > Epic 3`, `Epic 4`

- `search_building_knowledge(query)`
- `list_location_sensors(sensor_type)`
- `read_live_sensor(sensor_id)`
- `read_sensor_history(sensor_id, limit)`
- `search_maintenance_history(sensor_type)`
- `get_asset(location_id, asset_type)`
- `get_current_telemetry(asset_id, point_names)`
- `get_telemetry_history(asset_id, point_names, window)`
- `propose_building_command(asset_id, command, value)`
- `execute_approved_command(action_id)`
- `create_work_order(ticket_id, asset_id, trade, procedure, priority)`
- `get_work_order(work_order_id)`
- `send_ticket_update(ticket_id, message, audience)`
- `schedule_ticket_wakeup(ticket_id, reason, wake_at)`
- `verify_ticket_outcome(ticket_id)`

Every tool uses typed parameters, a narrow permission scope, and an idempotency key for writes.

### Policy Gateway

Implements: `prd.md > Story 3.2`, `Story 4.1`

- **Autonomous reads:** knowledge, asset, telemetry, ticket history.
- **Autonomous writes:** grounded reply, ticket metadata update, notification, diagnostic run, and HVAC setpoint adjustment within the seeded demo range.
- **Approval required:** reset of important equipment, out-of-hours changes, disruptive commands, or spend above the demo threshold.
- **Forbidden:** life-safety disablement, electrical isolation, access-control override, arbitrary shell/network calls, or values beyond equipment limits.

### Hooks And Audit

Implements: `prd.md > Story 5.2`

Use Strands hooks before and after tool calls to attach ticket/correlation IDs, enforce eligible-tool policy, capture duration and outcome, redact secrets, and publish public activity summaries. Store summaries and tool metadata, never hidden chain-of-thought.

## API

### Ticket endpoints

- `POST /api/tickets` — create a ticket.
- `GET /api/tickets` — list with status/kind/priority filters.
- `GET /api/tickets/{id}` — detail including events, actions, and work order.
- `POST /api/tickets/{id}/run` — enqueue the next step.
- `POST /api/tickets/{id}/approve` — approve or deny a pending action.
- `POST /api/tickets/{id}/simulate-technician` — demo-only technician completion.
- `POST /api/tickets/{id}/advance-time` — demo-only accelerated wait.
- `POST /api/demo/seed` — reset and create the three hero tickets.
- `POST /api/simulation/generate` — publish a controlled batch by count and scenario type.
- `POST /api/simulation/control` — compatibility endpoint; rejects attempts to enable background ticket generation.
- `GET /api/events` — SSE activity stream.

All mutation endpoints accept or derive an idempotency key and return the current ticket representation.

## File Structure

```text
backend/
  app/
    main.py                 FastAPI composition and routes
    config.py               environment-driven settings
    domain/
      models.py             ticket, action, event, work-order contracts
      state_machine.py      legal transitions and closure invariants
      policies.py           autonomous/approval/forbidden rules
    agents/
      facility_ops.py       Strands agent construction and prompt
      contracts.py          NextDecision structured outputs
      hooks.py              policy, audit, and tracing hooks
    tools/
      knowledge.py          grounded building information
      telemetry.py          simulated BMS reads
      commands.py           policy-checked simulated writes
      work_orders.py        technician lifecycle
      notifications.py      ticket conversation updates
    services/
      operations.py         pub/sub intake and workflow subscriber router
      tickets.py            use cases and state transitions
      workflow.py           one bounded durable step
      verification.py       outcome-specific closure checks
    repositories/
      ports.py              persistence interfaces
      sqlite.py             local implementation
      dynamodb.py           AWS phase implementation
    messaging/
      ports.py              durable pub/sub contract
      local.py              SQLite topics, subscriptions, retry, and DLQ
    scheduling/
      ports.py              enqueue/schedule interface
      local_worker.py       SQLite leasing and polling
      aws.py                EventBridge/SQS implementation
    seed/
      knowledge/            hours, rules, amenities
      building.py           locations, assets, telemetry
      demo.py               reproducible three-ticket story
frontend/
  src/
    app/                    routing, query client, shell
    features/inbox/         queue and filters
    features/ticket/        detail, conversation, timeline
    features/approvals/     risk and approval cards
    features/demo/          seed, accelerated wait, restart cues
    components/             shared visual primitives
    styles/                 tokens and layouts
tests/
  unit/                     state, policy, contracts
  integration/              ticket lifecycles and idempotency
  e2e/                      hero demo
docs/
  architecture.*            submission diagram
  reuse-disclosure.md       relationship to earlier idea
deploy/
  agentcore/                runtime entry point and config
  aws/                      infrastructure definitions/scripts
```

## Data Flow

1. Building World publishes `building.request.detected` to `building.events`; the Operations intake subscription creates the ticket idempotently. Direct receptionist intake enters through the same ticket service.
2. Ticket changes and the next deterministic job are persisted together. A relay publishes due outbox jobs to `workflow.commands` with an idempotency key.
3. A worker leases one `operations.workflow` delivery, loads the current ticket version, computes eligible actions, and invokes the Strands agent.
4. The structured decision is validated. Reads execute immediately; writes pass through policy and idempotency checks.
5. On success the consumer saves a versioned workflow checkpoint and acknowledges the message. On failure it retries with backoff; exhaustion dead-letters and safely escalates the ticket.
6. SSE announces the update; the browser refetches canonical state.
7. Waiting tickets have no open model invocation or web request. A persisted future outbox job resumes them.
8. Verification uses tool evidence and domain rules. Only the service can close the ticket.

## Local Runtime

Provide these commands:

```text
make setup
make seed
make run-operations
make run-world
make run-ui
make test
make demo-check
```

The three logical services are Operations (API plus worker pool), Building World
(sensors and event publication), and Web UI. Building World and Operations communicate
through durable pub/sub rather than direct method calls. `make run` starts all three. Stopping
Operations during `waiting_technician`, then restarting it, must visibly resume the
same ticket without duplicate actions.

## AWS Migration

### Agent execution

Package the same Strands agent behind the AgentCore Runtime HTTP contract and deploy it with the AgentCore CLI. Keep ticket state outside model sessions.

### Persistence and scheduling

- SQLite repositories → DynamoDB repositories.
- Local workflow jobs → EventBridge Scheduler for future wake-ups plus SQS/Lambda for immediate delivery and retries.
- Local model invocation → AgentCore Runtime invocation.
- Local hook logs → OpenTelemetry/AgentCore Observability and CloudWatch.
- Local knowledge files → S3 or packaged versioned content for the demo.

### Web delivery

Deploy the React build to S3/CloudFront. Keep FastAPI in a small container service or Lambda adapter; choose the lower-risk path after the local MVP is complete.

## Stage Plan

### Stage 0 — Product and demo lock, September 3

Freeze the three ticket stories, action policy, success metrics, and UI storyboard. Output: this spec, checklist, reuse disclosure outline, and architecture sketch.

### Stage 1 — Local vertical slice, September 3–4

Create the repository, contracts, migrations, API, worker loop, SSE, and a simple inbox. A seeded enquiry must travel from `new` to `resolved` without Strands first.

### Stage 2 — Real Strands path, September 4–5

Add classification, structured decisions, typed read tools, and provider configuration. Verify the local Strands + OpenAI invocation, retain deterministic tests, and preserve the Bedrock adapter for the AWS stage.

### Stage 3 — Safe action path, September 5–6

Implement telemetry, policy gateway, before/after command records, verification, and the “room too warm” ticket.

### Stage 4 — Long-running technician path, September 6–7

Implement work orders, scheduled wake-ups, stakeholder updates, technician completion, restart recovery, and failed-verification escalation.

### Stage 5 — Judge-ready UI, September 7–9

Build the operations inbox, ticket conversation, evidence/action timeline, approval drawer, work-order progress, verification state, and impact metrics. Add polished empty, loading, failure, and reconnect states.

### Stage 6 — Reliability and evaluation, September 9–10

Add lifecycle, policy, idempotency, restart, and prompt-evaluation tests. Record traces that prove Strands usage without exposing chain-of-thought.

### Stage 7 — AWS deployment, September 10–11

Deploy the agent to AgentCore Runtime, enable observability, then replace persistence/scheduling adapters as time allows. A live AgentCore invocation is the minimum scored cloud milestone.

### Stage 8 — Presentation freeze, September 12–13

Finalize README, license, architecture diagram, reuse disclosure, public demo, screenshots, five-minute video, builder.aws article, and Devpost draft. September 14 is buffer only.

## UI Demo Storyboard

### Screen 1 — Operations inbox

Show a professional queue, not a chatbot. Top metrics: `3 received`, `2 autonomous`, `1 human decision`, `6 touches saved`. Ticket rows visibly change state.

### Screen 2 — Enquiry closes instantly

Open “What time does the gym close?” Show grounded answer, source citation, one Strands decision, message sent, and verified closure.

### Screen 3 — Safe change with proof

Open “Conference room too warm.” Show telemetry, policy boundary, command before/after values, verification window, and automatic close.

### Screen 4 — Meaningful human escalation

Open the burning-smell ticket. Show safety triage, compact evidence, work order, technician delay, updates sent, and the single decision requiring a person.

### Screen 5 — Long-running recovery and impact

Restart the local worker or use the accelerated technician control. The ticket resumes from its checkpoint, processes notes, verifies recovery, and closes. Finish on the queue metrics and architecture view.

## Judging-Criteria Design

- **Technological Implementation:** real Strands structured output, typed tools, hooks, durable state, idempotent writes, restart recovery, AgentCore deployment, and visible traces.
- **Design:** coherent ticket-first product, calm professional hierarchy, understandable action/approval cards, and honest failure states.
- **Potential Impact:** quantify deflection, human touches saved, first-response time, SLA risk, and verified closures for facility teams.
- **Creativity & Originality:** one agent handles informational, transactional, and physical-world workflows while separating safe automation from human judgment.
- **Presentation:** one reproducible three-ticket story with a visible queue transformation and a single memorable durable-wait moment.

## Risks And Verification

1. **Looks like the prior project.** Use a new name, ticket-first UI, new Strands code, new state model, new demo, and a precise reuse disclosure.
2. **Too broad.** Keep exactly three ticket paths and one safe command. Cut offers, real integrations, and multi-agent expansion.
3. **Agent appears decorative.** Show real Strands decisions and tool calls that change external state; do not pre-script the live model path.
4. **Model variability breaks the demo.** Validate structured output, bound actions, seed evidence, add retry/escalation, and rehearse the exact model/configuration.
5. **AWS consumes the schedule.** Do not begin cloud work until all three local paths and the UI are demo-stable.
6. **Long wait is boring.** Use compressed time, ongoing status messages, and a visible durable checkpoint rather than a spinner.

## Demo And Submission Flow

Target a 4:30 video: 30 seconds problem, 30 seconds queue/product, 2:30 live three-ticket flow, 40 seconds architecture/Strands/AgentCore, and 20 seconds measured impact and close. Capture the hero workflow in one take after an automated preflight verifies the seed, model access, and three lifecycle outcomes.
