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

## Hero demo

1. Reset the three-ticket demo.
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
