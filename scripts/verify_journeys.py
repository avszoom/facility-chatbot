"""Rehearse a full journey in a disposable database; --live uses the configured model."""
from argparse import ArgumentParser
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.config import Settings
from backend.app.domain.models import ApprovalRequest, TicketCreate
from backend.app.system import build_system


def main():
    parser = ArgumentParser()
    parser.add_argument("--case", choices=["knowledge", "comfort", "safety"], required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    cases = {
        "knowledge": ("What time does the gym close?", "What time does the gym close, and can I bring a guest?", "BLDG-A-F02-FITNESS", "enquiry", "normal"),
        "comfort": ("Apartment 4B is too warm", "My living room in Apartment 4B feels too warm despite the thermostat setting.", "BLDG-A-F04-APT-4B", "service_request", "temperature_high"),
        "safety": ("Flickering lights and burning electrical smell on Floor 7", "The east residential wing lights flicker and smell like hot plastic.", "BLDG-A-F07-EAST", "incident", "electrical_overheat"),
    }
    subject, description, location, kind, condition = cases[args.case]
    with TemporaryDirectory(prefix="buildingops-journey-") as directory:
        settings = replace(Settings.from_env() if args.live else Settings(),
                           database_path=Path(directory) / "check.db", simulation_enabled=False,
                           intake_delay_seconds=0, agent_analysis_seconds=0, action_delay_seconds=0,
                           verification_delay_seconds=0)
        if args.live and settings.agent_runtime == "deterministic":
            raise SystemExit("Configure a live AGENT_RUNTIME before using --live")
        system = build_system(settings)
        message = system.simulation.publish_request(
            TicketCreate(subject=subject, description=description, requester="Verification resident", location_id=location),
            request_type=kind, condition_type=condition, technician_delay_seconds=15)
        ticket_id = message.payload["ticket_id"]
        saw_wait = False
        for step in range(40):
            system.operations.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=1)
            if not system.repository.get_ticket(ticket_id):
                continue
            detail = system.tickets.detail(ticket_id)
            print(args.case, step, detail.ticket.status, flush=True)
            if detail.ticket.status == "needs_approval":
                system.tickets.decide_approval(ticket_id, ApprovalRequest(approved=True, reason="Isolated rehearsal approval"))
            if detail.ticket.status == "waiting_technician":
                saw_wait = True
                assert detail.work_order and "Working diagnosis" in detail.work_order.procedure
            if detail.ticket.status == "escalated":
                raise AssertionError(detail.events[-1].summary)
            if detail.ticket.status == "resolved":
                if args.case == "knowledge":
                    assert any("Source:" in event.summary for event in detail.events)
                else:
                    assert any(event.event_type == "verification.passed" for event in detail.events)
                    if args.case == "safety":
                        assert saw_wait
                    else:
                        assert any(action.action_type == "set_temperature_setpoint" for action in detail.actions)
                print(f"PASS {'LIVE' if args.live else 'OFFLINE'} {args.case}", flush=True)
                return
        raise AssertionError("Journey did not finish within the rehearsal budget")


if __name__ == "__main__":
    main()
