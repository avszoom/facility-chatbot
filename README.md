# BuildingOps Autopilot

A durable Strands-based professional agent that works building-support tickets from intake to verified outcome. It answers enquiries, safely adjusts comfort controls, investigates incidents, pauses for consequential human approval, waits for technicians without holding a request open, and closes only after independent verification.

## Run locally

Requirements: Python 3.11+ and Node.js 22+.

```bash
make setup
make seed
make run
```

Open <http://127.0.0.1:5173>. The API runs at <http://127.0.0.1:8000>.

The committed default `AGENT_RUNTIME=deterministic` is credential-free and repeatable.
For the real local agent, put these values in the ignored `.env` file:

```dotenv
AGENT_RUNTIME=openai
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-5.2
OPENAI_STORE=false
```

The key is read only by the Operations service and is never returned by an API,
written to an event, or bundled into the browser. The Strands agent uses OpenAI's
Responses API, while the ticket state machine and policy gateway remain provider
independent. `AGENT_RUNTIME=bedrock` plus AWS credentials selects the AWS model path.
The Agent activity page identifies the active runtime, provider, and model.

`make run` starts three independently replaceable service groups: **Operations**
(API plus three durable workers), **Building World**, and **Web UI**.
Building World and Operations communicate only through a SQLite-backed durable
pub/sub adapter. The local broker provides at-least-once delivery, leased consumers,
exponential retry, a dead-letter state, and idempotent message publication. Every
ticket also has a saved `WF-*` checkpoint, so a worker restart resumes the current
step instead of starting the ticket over.

The Building World owns a 60-device digital twin across all ten floors. It advances
temperature, CO₂, humidity, VOC/odor, occupancy, and electrical telemetry every two
seconds and keeps bounded rolling history. It never creates tickets on a timer. Every
request must come from an explicit console action: New request, the Request generator
composer, Trigger test event, or an intentional load-test batch. Sensor monitoring
continues independently without adding tickets. The **Agent live** workspace shows
both engines, the durable handoff, public decision summaries, tool outcomes, and
continuously updated impact totals.

The compact **Request generator** tab controls the Building World without bypassing
the production-shaped path. Compose a location-specific request or deliberately
publish 1–20 enquiry, service-request, or incident scenarios for a concurrency test.
Every request is still published to `building.events` and consumed by Operations.

For every operational ticket, the model chooses among six live sensors at the
reported floor, reads the relevant rolling histories, and can search maintenance
records and the building knowledge base. Its typed decision must cite exact sensor
IDs; unknown or cross-floor IDs are rejected. Public `agent.tools_completed` and
`evidence.correlated` events show what evidence was used without exposing private
chain-of-thought. A sensor-only ticket follows the same durable workflow as an
occupant report.

To run each service boundary in its own terminal instead:

```bash
# Terminal 1: API plus the ticket-clearing worker pool
make run-operations

# Terminal 2: sensors, building conditions, and occupant request generation
make run-world

# Terminal 3: receptionist web application
make run-ui
```

Set `AGENT_WORKER_COUNT` to control how many independent ticket steps can execute
concurrently. The local default is `3`. Reliability controls are
`MESSAGE_MAX_ATTEMPTS`, `MESSAGE_RETRY_BASE_SECONDS`, and `MESSAGE_LEASE_SECONDS`.

## Scenario walkthrough

1. Open Agent live and generate a building-world event, or wait for the next scheduled event.
2. Show the gym enquiry already answered and closed from a cited source.
3. Show the warm room’s policy-approved setpoint change and verified closure.
4. Open the electrical incident, inspect correlated evidence, then approve dispatch.
5. Advance waiting work twice to show technician completion followed by independent verification.

## Verify

```bash
make verify
make demo-rehearsal RUNS=3
make verify-strands
# Makes one live API request using the ignored .env key
make verify-openai
```

See [the AWS replacement map](docs/aws-migration.md), [reuse disclosure](REUSE_DISCLOSURE.md), and [implementation checklist](docs/hackathon-build/checklist.md).

Licensed under MIT.
