from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_building_simulator_emits_durable_tickets_and_conditions(system):
    first = system.simulation.tick(force=True)
    second = system.simulation.tick(force=True)

    assert first and first.subject == "What time does the fitness center close?"
    assert second and "too warm" in second.subject
    assert system.repository.get_ticket(first.ticket_id)
    assert system.repository.get_ticket(second.ticket_id)
    assert system.building.telemetry("AHU-ZONE-4B")["temperature_f"] == 77.2
    status = system.simulation.status()
    assert status["issues_generated"] == 2
    assert status["last_event"]["ticket_id"] == second.ticket_id


def test_live_operations_reports_both_engines_and_impact(system):
    client = TestClient(create_app(system))
    created = client.post("/api/simulation/pulse")
    assert created.status_code == 200

    live = client.get("/api/operations/live")
    assert live.status_code == 200
    payload = live.json()
    assert payload["simulation"]["status"] == "online"
    assert payload["agent"]["status"] == "online"
    assert payload["agent"]["active_tickets"][0]["ticket_id"] == created.json()["ticket_id"]
    assert payload["impact"]["actions_performed"] == 0
