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

The default `AGENT_RUNTIME=deterministic` is credential-free and repeatable. Set `AGENT_RUNTIME=strands`, `AWS_REGION`, and `BEDROCK_MODEL_ID` to exercise the real Strands/Bedrock path with your AWS credentials. The UI shows the active runtime.

`make run` starts three independently replaceable service groups: **Operations**
(API plus three durable workers), **Building World**, and **Web UI**.
Building World and Operations communicate only through a SQLite-backed durable
pub/sub adapter. The local broker provides at-least-once delivery, leased consumers,
exponential retry, a dead-letter state, and idempotent message publication. Every
ticket also has a saved `WF-*` checkpoint, so a worker restart resumes the current
step instead of starting the ticket over.

The Building World owns a 60-device digital twin across all ten floors. It advances
temperature, CO₂, humidity, VOC/odor, occupancy, and electrical telemetry every two
seconds and keeps bounded rolling history. It can publish occupant requests or open
a ticket directly from an autonomous sensor anomaly every 45 seconds by default; set
`SIMULATION_INTERVAL_SECONDS` to change the cadence, or
`SIMULATION_ENABLED=false` to turn it off. The **Agent live** workspace shows both
engines, the durable handoff between them, public decision summaries, tool outcomes,
and continuously updated impact totals.

The compact **Request generator** tab controls the Building World without bypassing
the production-shaped path. Choose 1–20 requests, restrict the batch to enquiries,
service requests, or incidents, change the automatic cadence, and pause or resume
continuous generation. Every controlled request is still published to
`building.events` and consumed by Operations.

For every operational ticket, the agent correlates four sources before deciding:
the complaint (when present), the linked live sensor, nearby floor telemetry and
trend history, and relevant maintenance records. The resulting evidence summary is
stored as a public `evidence.correlated` event; private chain-of-thought is never
shown. A sensor-only ticket follows the same durable workflow as an occupant report.

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
```

See [the AWS replacement map](docs/aws-migration.md), [reuse disclosure](REUSE_DISCLOSURE.md), and [implementation checklist](docs/hackathon-build/checklist.md).

Licensed under MIT.
