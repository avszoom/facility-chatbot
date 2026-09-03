# Build Notes

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
