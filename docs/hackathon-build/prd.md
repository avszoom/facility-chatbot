# Product Requirements — BuildingOps Concierge

## Epic 1: Ticket Intake And Queue

### Story 1.1 — Create a ticket

As a resident, I want to describe a building question or problem in ordinary language so that I do not need to know the correct department or form.

Acceptance criteria:

- The create-ticket form accepts requester, location, subject, description, and optional category.
- Submitting creates a visible ticket with a stable ID and `new` status.
- Empty descriptions and unknown locations produce clear validation messages.

### Story 1.2 — Operate the queue

As a concierge, I want one queue sorted by urgency and SLA risk so I can see what the agent handled and what needs me.

Acceptance criteria:

- The queue supports New, Agent working, Waiting, Needs approval, Resolved, and Escalated states.
- Each row shows type, priority, requester, location, age, owner, and current state.
- Filters do not hide a ticket requiring approval without showing an approval count.

## Epic 2: Agent Triage And Routing

### Story 2.1 — Classify and prioritize

As a property manager, I want the agent to identify enquiry, service request, or incident and assign urgency with evidence.

Acceptance criteria:

- The Strands path returns a schema-validated classification, priority, safety flags, confidence, and rationale.
- Safety language overrides a low model priority through deterministic policy.
- Low confidence routes to human review rather than an invented decision.

### Story 2.2 — Choose the next action

As a property manager, I want the agent to continue without supervision when policy permits.

Acceptance criteria:

- Every step records considered action, selected action, tool inputs, result, and next state.
- Repeated delivery of the same event cannot duplicate a message, work order, command, or closure.

## Epic 3: Autonomous Resolution

### Story 3.1 — Answer enquiries

As a resident, I want an authoritative answer with a source so I can trust it.

Acceptance criteria:

- The answer is grounded in the local building knowledge base.
- Missing or conflicting knowledge results in escalation.
- A grounded answer is sent and the ticket closes automatically.

### Story 3.2 — Apply a safe building change

As a property manager, I want low-risk apartment and amenity requests completed within an explicit policy boundary.

Acceptance criteria:

- The tool rejects commands outside the configured asset, time, and value range.
- The UI displays before value, proposed value, policy, execution result, and verification value.
- The ticket closes only when telemetry confirms the intended outcome.

## Epic 4: Human Decisions And Technician Work

### Story 4.1 — Ask for approval only when necessary

As a property manager, I want concise approval requests for consequential actions.

Acceptance criteria:

- Approval cards show evidence, proposed action, risk, alternatives, and expiration.
- Denial returns the ticket to the agent with the denial reason.
- Forbidden actions cannot be approved through the UI.

### Story 4.2 — Manage a long-running work order

As a property manager, I want the agent to coordinate technician work without requiring an open browser.

Acceptance criteria:

- The agent creates one idempotent work order with location, asset, evidence, priority, trade, and requested procedure.
- The ticket persists `waiting_for_technician` with a durable wake-up time.
- Restarting the worker preserves state and does not duplicate the work order.
- Simulated technician completion resumes the ticket automatically.

### Story 4.3 — Keep stakeholders informed

As a requester, I want useful status updates without repeatedly contacting the facility team.

Acceptance criteria:

- Receipt, investigation, dispatch, delay, repair, verification, and closure updates appear in the ticket conversation.
- Duplicate retries cannot send duplicate updates.

## Epic 5: Verification, Closure, And Trust

### Story 5.1 — Verify before closing

As a property manager, I want independent evidence that the problem is fixed.

Acceptance criteria:

- Completion notes alone cannot close an incident.
- A stable verification window closes a successful ticket.
- Failed verification reopens investigation or escalates with the reason.

### Story 5.2 — Inspect the audit trail

As a judge or operator, I want to see exactly what the agent observed and changed.

Acceptance criteria:

- The timeline distinguishes agent reasoning summaries, tool reads, write actions, waits, human decisions, and verification.
- Hidden chain-of-thought is never displayed.
- The UI exposes useful metrics: automated resolutions, human touches saved, median first response, open SLA risks, and verified closures.

## Epic 6: Demo And Failure States

### Story 6.1 — Run the hero demo

As a presenter, I want one button to seed and run the three-ticket story reproducibly.

Acceptance criteria:

- The run completes in under four minutes using accelerated waits.
- A presenter can pause, approve, deny, advance simulated technician time, and restart the worker.
- The demo clearly labels simulated integrations and real Strands/model actions.

### Story 6.2 — Degrade safely

As an operator, I want failures to be visible and recoverable.

Acceptance criteria:

- Model failure retries safely and then escalates after a bounded limit.
- Tool errors preserve ticket state and show an actionable UI message.
- SSE reconnection restores the current ticket state from the API.

## Submission Proof Points

- Real Strands agent invocation and typed tools are visible in code, UI, and video.
- The demo shows end-to-end work, not a chat response.
- The public repository contains an MIT or Apache license, setup instructions, architecture diagram, test command, and reuse disclosure.
- The five-minute video covers problem, audience, importance, live workflow, architecture, and measurable outcome.
