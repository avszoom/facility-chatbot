"""Isolated real-model regression: unrelated alarms cannot hijack a question."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
from backend.app.config import Settings
from backend.app.domain.models import TicketCreate
from backend.app.system import build_system


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["knowledge", "service", "safety"], default="knowledge")
    case = parser.parse_args().case
    with TemporaryDirectory(prefix="intent-flow-") as directory:
        system = build_system(replace(Settings.from_env(), database_path=Path(directory) / "test.db",
            intake_delay_seconds=0, agent_analysis_seconds=0, action_delay_seconds=0,
            technician_delay_seconds=0, verification_delay_seconds=0, simulation_enabled=False))
        if case == "knowledge":
            system.building.inject_simulated_condition("electrical_overheat", "BLDG-A-F07-EAST", "UNRELATED")
            subject = "Where should cardboard and recycling go?"
            description = "I have moving boxes and household recycling. Should I use the refuse room or service elevator area?"
            location = "BLDG-A-F07-EAST"
        elif case == "service":
            subject = description = "My living room in Apartment 4B is too warm. Please check the thermostat and restore a comfortable temperature."
            location = "BLDG-A-F04-APT-4B"
        else:
            subject = description = "There is a burning electrical smell from an outlet in the floor 4 laundry room. Please arrange qualified inspection."
            location = "BLDG-A-F04-LAUNDRY"
        ticket = system.tickets.create(TicketCreate(subject=subject, description=description,
            requester="Test resident", location_id=location))
        if case != "knowledge":
            system.building.inject_simulated_condition("temperature_high" if case == "service" else "electrical_overheat", location, ticket.ticket_id)
        for _ in range(20):
            system.workflow.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=1)
            detail = system.tickets.detail(ticket.ticket_id)
            print(detail.ticket.status, detail.events[-1].summary[:180], flush=True)
            if detail.ticket.status in {"resolved", "escalated", "needs_approval"}:
                break
        assert detail.ticket.status == "resolved", detail.ticket.status
        roles = [e.actor for e in detail.events if e.event_type == "specialist.completed"]
        if case == "knowledge":
            assert not detail.work_order
            assert "Resident Knowledge Agent" in roles, roles
            assert "Sensor Intelligence Agent" not in roles, roles
        else:
            assert any(e.event_type == "verification.passed" for e in detail.events)
            if case == "safety":
                assert detail.work_order and detail.work_order.trade == "electrical"
        print(f"PASS: {case} resolved with roles {roles}", flush=True)


if __name__ == "__main__":
    main()
