# Three resident journeys

Use Agent activity → Request generator for physical scenarios. Creating an ordinary
resident message alone does not necessarily inject a matching equipment fault.
All handbook rules describe the fictional Northstar property; validate them before
using this system with a real building.

## 1. Knowledge — no human intervention

Resident message: “What time does the gym close, and can I bring a guest?”
Location: Floor 2 / Fitness center. Type: enquiry. Condition: normal.

Show the request pipeline, open the workflow explorer, select Resident knowledge,
and show the handbook-backed answer in the evidence trail. Closure requires a
recorded sourced response, not merely successful classification.

## 2. Comfort — permitted action and measured recovery

Resident message: “My living room in Apartment 4B is too warm even though the
thermostat is set correctly. Can you check it?”
Location: Floor 4 / Apartment 4B. Type: service request. Condition: temperature high.

Show the warning sensor in Building, then the sensor and maintenance reports in the
workflow explorer. Expand the setpoint action for its before/after values and policy
rule. The local equipment model produces the recovery readings; the agent does not
overwrite telemetry to manufacture verification. Show the independent verification
event before closure. This demonstrates supported HVAC control, not automatic
repair of arbitrary service incidents.

## 3. Electrical safety — substantial automation, bounded human authority

Resident message: “The lights are flickering and there is a burning electrical smell
on Floor 7 near the east residential wing. Please investigate urgently.”
Location: Floor 7 / East residential wing. Type: incident. Condition: electrical fault.
Choose a technician duration long enough to show the waiting state.

Show intake, correlated sensor readings, maintenance history and proposed handling.
Approve the dispatch from the request actions. Show the assigned work order, evidence
and procedure. Keep the request open while the simulated technician works; only
fresh successful verification permits closure. Never present a suspected cause as
a physically confirmed diagnosis. No hazardous electrical switching is autonomous.

## Presentation rules

- Pipeline progress follows saved ticket state; pulsing indicates a valid worker lease.
- Specialist nodes show actual reports and handoffs, not six permanently running agents.
- Agent/staff percentages measure counted coordination actions, not time or physical repair.
- Old failed tickets remain in history. New code does not silently reopen them.
- Preflight the real-model paths before recording; passing offline fixtures alone is
  not evidence that a live model rehearsal succeeded.

Checks: `make test`, `make frontend-build`, `make demo-check`.

Full isolated live-model rehearsal (uses the configured API key and model, may incur
API charges, does not modify dashboard data):

```sh
.venv/bin/python scripts/verify_journeys.py --case knowledge --live
.venv/bin/python scripts/verify_journeys.py --case comfort --live
.venv/bin/python scripts/verify_journeys.py --case safety --live
```

Omit `--live` for offline regression checks. The safety rehearsal supplies an
approval inside its temporary database and advances simulated time; this is not
an approval or dispatch in the running dashboard.
