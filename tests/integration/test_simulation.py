from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.config import Settings
from backend.app.system import build_system


def test_building_simulator_emits_durable_tickets_and_conditions(system):
    first_message = system.simulation.tick(force=True)
    second_message = system.simulation.tick(force=True)

    assert first_message and first_message.topic == "building.events"
    assert second_message and "too warm" in second_message.payload["request"]["subject"]
    assert system.repository.get_ticket(first_message.payload["ticket_id"]) is None
    system.operations.process_due(
        now=datetime.now(UTC) + timedelta(hours=1), limit=10
    )
    assert system.repository.get_ticket(first_message.payload["ticket_id"])
    assert system.repository.get_ticket(second_message.payload["ticket_id"])
    assert system.building.telemetry("AHU-ZONE-4B")["temperature_f"] == 77.2
    status = system.simulation.status()
    assert status["issues_generated"] == 2
    assert status["scenario_count"] == 10
    assert status["last_event"]["ticket_id"] == second_message.payload["ticket_id"]


def test_live_operations_reports_both_engines_and_impact(system):
    client = TestClient(create_app(system))
    created = client.post("/api/simulation/pulse")
    assert created.status_code == 200
    system.operations.process_due(
        now=datetime.now(UTC) + timedelta(hours=1), limit=10
    )

    live = client.get("/api/operations/live")
    assert live.status_code == 200
    payload = live.json()
    assert payload["simulation"]["status"] == "online"
    assert payload["agent"]["status"] == "online"
    assert payload["agent"]["worker_count"] == 3
    assert payload["agent"]["active_tickets"][0]["ticket_id"] == created.json()["payload"]["ticket_id"]
    assert payload["messaging"]["delivery"] == "at_least_once"
    assert payload["messaging"]["idempotent_consumers"] is True
    assert payload["impact"]["actions_performed"] == 0
    assert payload["impact"]["autonomy_rate"] == 100


def test_published_building_event_survives_process_restart(system):
    message = system.simulation.tick(force=True)
    assert message

    restarted = build_system(
        Settings(
            database_path=system.settings.database_path,
            intake_delay_seconds=0,
            agent_analysis_seconds=0,
            action_delay_seconds=0,
            technician_delay_seconds=0,
            verification_delay_seconds=0,
        )
    )
    restarted.operations.process_due(
        now=datetime.now(UTC) + timedelta(hours=1), limit=10
    )

    ticket_id = str(message.payload["ticket_id"])
    assert restarted.repository.get_ticket(ticket_id)
    assert restarted.repository.get_workflow_state(ticket_id)
    assert restarted.message_bus.stats()["completed"] >= 1


def test_generator_controls_cadence_count_and_request_type(system):
    client = TestClient(create_app(system))
    controlled = client.post(
        "/api/simulation/control",
        json={"running": False, "interval_seconds": 90},
    )
    assert controlled.status_code == 200
    assert controlled.json()["status"] == "paused"
    assert controlled.json()["interval_seconds"] == 90

    generated = client.post(
        "/api/simulation/generate",
        json={"count": 3, "scenario_type": "incident"},
    )
    assert generated.status_code == 200
    messages = generated.json()
    assert len(messages) == 3
    assert len({message["message_id"] for message in messages}) == 3
    assert all(
        message["payload"]["scenario"]["scenario_type"] == "incident"
        for message in messages
    )
    assert system.simulation.status()["issues_generated"] == 3
