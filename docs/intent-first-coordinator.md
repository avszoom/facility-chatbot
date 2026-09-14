# Intent-first coordinator

The production model first receives the resident request, a specialist capability directory,
and persisted reports. It does not receive prefetched alarms or a code-selected investigation path.
It records intent and chooses one specialist and a specific objective per durable iteration.

Specialist execution loads role-specific records on demand. The actual objective and previous
reports are passed to the specialist. The coordinator then evaluates the report and chooses
another investigation step or proposes a typed action. The directory is optional, not a checklist.

Knowledge enquiries retrieve handbook evidence and close after a grounded reply is delivered.
Operational actions still require cited sensor evidence and deterministic policy authorization.
Equipment setpoints are controlled through the action gateway; the local building provider
simulates the physical response. The model cannot write arbitrary sensor readings.

Maintenance dispatch leaves the resident ticket in waiting_technician (open, not attention).
The local technician simulator supplies completion evidence; independent verification must
pass before closure. Failed adjustments get a maintenance work order before staff escalation.
Repeated failure after repair requires staff review. Overdue maintenance is escalated after
five minutes beyond the promised time. Shared-infrastructure changes still require approval.

Pub/sub delivery, job checkpoints, retries and idempotent work-order/action keys remain in use.
The offline fixture runtime remains deterministic for tests; it is not the production coordinator.

Validation: `python -m scripts.check_intent_flow --case knowledge|service|safety`
uses the configured model and an isolated temporary database (one case per invocation).

Current limits: maintenance completion is simulated, not an external CMMS integration.
Resident clarification is still a staff-reviewed exception, not a separate resident reply loop.
The model may repeat a specialist for a new diagnostic question within a ten-step investigation budget.
Operator-driven repair updates require further work. These limits must not be presented as
completed production capabilities.
