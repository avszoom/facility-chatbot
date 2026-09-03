# Build Checklist

## Build Preferences

- **Build mode:** Autonomous after explicit build start
- **Comprehension checks:** N/A
- **Git:** Commit after each verified vertical slice
- **Verification:** Automated checks at every item; visual review after UI shell, hero workflow, and final polish
- **Check-in cadence:** Balanced
- **Critical rule:** Do not start AWS migration until the three local ticket paths pass end to end

## Checklist

- [x] **1. Bootstrap the new repository and contracts**
  Spec ref: `spec.md > File Structure`, `spec.md > Domain Model`
  What to build: Python/React monorepo, Makefile, environment template, typed ticket/action/event/work-order models, SQLite migration, and explicit reuse-disclosure stub.
  Acceptance: A fresh clone installs; migrations create an empty database; no previous agent/UI/orchestration code is present.
  Verify: `make setup && make test`

- [x] **2. Implement ticket API and durable job store**
  Spec ref: `spec.md > API`, `spec.md > Data Flow`
  What to build: Ticket CRUD, append-only event log, workflow job leases, deterministic IDs, transactionally-created next jobs, and three-ticket seed endpoint.
  Acceptance: Seeded tickets survive API/worker restarts and duplicate job delivery cannot duplicate events.
  Verify: `pytest tests/unit tests/integration -k 'ticket or workflow or idempotency'`

- [x] **3. Deliver the first local vertical slice**
  Spec ref: `spec.md > Local Runtime`, `prd.md > Story 3.1`
  What to build: Separate API and worker processes, local knowledge tool, grounded enquiry resolver, notification event, automatic closure, and SSE updates.
  Acceptance: The gym-hours ticket moves from New to Resolved with a cited knowledge source and no operator input.
  Verify: `make demo-check DEMO_CASE=enquiry`

- [x] **4. Integrate the real Strands agent**
  Spec ref: `spec.md > Agent Design > FacilityOps Orchestrator`
  What to build: Strands agent, Bedrock model configuration, `NextDecision` structured output, typed tools, retries, and deterministic test double.
  Acceptance: The live agent classifies all three seeded requests and selects only eligible actions; the UI/API identifies genuine Strands runs.
  Verify: `make test-agent && make verify-strands`

- [x] **5. Add policy enforcement and audit hooks**
  Spec ref: `spec.md > Agent Design > Policy Gateway`, `spec.md > Agent Design > Hooks And Audit`
  What to build: Autonomous/approval/forbidden rules, pre-tool enforcement, post-tool audit, redaction, correlation IDs, and idempotency for writes.
  Acceptance: Out-of-range HVAC and life-safety commands are blocked regardless of the model response; every allowed write has before/after records.
  Verify: `pytest tests/unit -k 'policy or hook or command'`

- [x] **6. Complete the safe service-request path**
  Spec ref: `prd.md > Story 3.2`, `prd.md > Story 5.1`
  What to build: Seeded telemetry, HVAC command simulator, narrow setpoint policy, verification window, and failed-verification escalation.
  Acceptance: The warm-room ticket adjusts one setpoint within policy and closes only after a stable verification reading.
  Verify: `make demo-check DEMO_CASE=service_request`

- [x] **7. Complete the durable technician path**
  Spec ref: `prd.md > Story 4.2`, `prd.md > Story 4.3`
  What to build: Safety triage, evidence reads, work-order creation, technician timer, status messages, completion notes, resume logic, and post-repair verification.
  Acceptance: The incident creates one work order, waits with no open request, survives a worker restart, resumes once, and closes or escalates based on evidence.
  Verify: `make demo-check DEMO_CASE=incident DEMO_RESTART=1`

- [x] **8. Build the judge-facing operations UI**
  Spec ref: `spec.md > UI Demo Storyboard`, `prd.md > Epic 1`, `prd.md > Story 5.2`
  What to build: Metrics header, prioritized inbox, ticket creation, conversation, agent/action timeline, evidence, approval card, work-order progress, verification panel, and reconnect/error states.
  Acceptance: A first-time viewer can identify what the agent did, what changed, what needs a person, and whether the result was verified without reading logs.
  Verify: `npm --prefix frontend test && npm --prefix frontend run build`; complete visual review at desktop and laptop widths.

- [x] **9. Assemble and lock the hero demo**
  Spec ref: `spec.md > UI Demo Storyboard`, `prd.md > Story 6.1`
  What to build: One-click seed/reset, accelerated wait, optional failure/restart control, stable demo fixtures, impact metrics, and presenter-safe labels.
  Acceptance: The three-ticket story completes in under four minutes on three consecutive runs with the real Strands path.
  Verify: `make demo-rehearsal RUNS=3`

- [x] **10. Add evaluations and reliability proof**
  Spec ref: `spec.md > Risks And Verification`, `prd.md > Story 6.2`
  What to build: Classification/action evaluation set, lifecycle invariants, model/tool failure tests, idempotency tests, prompt-injection cases, secret scan, and public trace summaries.
  Acceptance: No unsafe action executes; all lifecycle tests pass; model/tool failures preserve recoverable state.
  Verify: `make verify`

- [ ] **11. Deploy the scored AWS slice**
  Spec ref: `spec.md > AWS Migration`
  What to build: AgentCore Runtime entry point, deployment config, live invocation, CloudWatch/AgentCore observability, and—only if time remains—DynamoDB plus EventBridge/SQS adapters and hosted frontend/API.
  Acceptance: The same agent/tool contract runs in AgentCore and produces a trace visible in AWS; local mode remains functional.
  Verify: `make deploy-agentcore && make verify-agentcore`

- [ ] **12. Prepare Devpost handoff**
  Spec ref: `prd.md > Submission Proof Points`, `spec.md > Demo And Submission Flow`
  What to build: MIT or Apache license, polished README, architecture diagram, reuse disclosure, setup/testing instructions, screenshots, public demo, five-minute video, builder.aws post, and Devpost draft.
  Acceptance: A clean clone works; all required submission fields and proof points exist; the video shows the live end-to-end product and explicitly names Strands Agents.
  Verify: Run `make submission-check`, review the public repository as a logged-out user, and confirm the next command is `$prepare-submission`.
