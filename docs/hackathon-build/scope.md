# Scope — BuildingOps Concierge

## Product Promise

BuildingOps Concierge is a professional agent that clears repetitive residential-building work from a property team's queue. It receives resident requests, understands the need, takes policy-safe action, waits for external work when necessary, keeps residents informed, verifies the outcome, and closes the ticket.

## Primary User

The primary user is a concierge or property operations manager responsible for Northstar Residences, a ten-story tower with 132 apartments, shared lounges, a gym, yoga studio, pool, café, parcel room, and roof terrace. Residents submit requests, but the product is judged by how much repetitive operational work it removes from the professional team.

## MVP Ticket Paths

1. **Enquiry:** “What time does the gym close?” The agent retrieves an authoritative answer, replies with its source, and closes the ticket.
2. **Service request:** “Apartment 4B is too warm.” The agent checks telemetry and policy, applies an allowlisted setpoint adjustment, verifies the result, and closes the ticket.
3. **Building incident:** “The Floor 7 corridor lights are flickering and there is a burning smell.” The agent performs safety triage, investigates evidence, creates a technician work order, waits durably, sends updates, interprets completion notes, verifies telemetry recovery, and closes or escalates.

## Hero Outcome

The inbox starts with three new tickets. The agent resolves two with zero operator effort and surfaces one meaningful safety/technician decision. The UI shows saved human touches, time to first response, action audit, and verified resolution.

## In Scope

- New React ticket-inbox experience with ticket creation.
- FastAPI API, SQLite persistence, and a separate durable local worker.
- Strands Agents SDK for classification, next-action selection, evidence synthesis, response drafting, and technician-note interpretation.
- Typed tools for knowledge lookup, telemetry, asset lookup, safe building commands, work orders, notifications, timers, and closure.
- Deterministic workflow guardrails around agent decisions.
- Policy tiers: autonomous, approval-required, and forbidden.
- Durable waits, retries, idempotency, restart recovery, and accelerated demo time.
- SSE updates from backend to UI.
- Seeded building data, knowledge base, telemetry, tickets, and technician outcomes.
- Local-first operation followed by AWS adapters and AgentCore deployment.
- Tests, architecture diagram, public README, reuse disclosure, and five-minute demo assets.

## Explicit Non-Goals

- Real integrations with property-management systems, BMS, email, resident apps, access control, parcel, or amenity-booking providers.
- Multi-building tenancy, production authentication, billing, or mobile applications.
- A general-purpose chatbot.
- Autonomous life-safety changes, electrical isolation, expensive purchases, or irreversible actions.
- Promotions/offers in the MVP; this dilutes the professional workflow and can be added later.
- An unbounded persona swarm. The product uses one accountable coordinator per isolated ticket workflow, bounded role-specific specialists, and a worker pool so unrelated tickets can progress concurrently.
- Reusing the previous project's agent, orchestration, UI, or demo code.

## Time Box

Plan for September 3–13, 2026, leaving September 14 as submission buffer. A complete local demo is the non-negotiable milestone; AWS deployment is a scored enhancement after the local proof is stable.

## Success Metrics

- Three seeded ticket paths complete reproducibly.
- Two of three hero tickets require zero human touches.
- Every write action has an audit record and policy decision.
- The incident survives a worker restart while waiting for a technician.
- Tickets close only after outcome verification.
- A judge can understand the problem and watch the entire story in under five minutes.
