from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.config import Settings
from backend.app.domain.models import TicketCreate
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
    assert payload["simulation"]["status"] == "paused"
    assert payload["simulation"]["running"] is False
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

    rejected = client.post(
        "/api/simulation/control",
        json={"running": True, "interval_seconds": 90},
    )
    assert rejected.status_code == 409
    assert "disabled" in rejected.json()["detail"]

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
    assert all(
        message["payload"]["scenario"]["source"] == "request_generator_console"
        for message in messages
    )
    assert system.simulation.status()["issues_generated"] == 3


def test_paused_request_generation_keeps_building_sensors_live(system):
    system.simulation.configure(running=False, interval_seconds=45)
    ticket_count = len(system.tickets.list())

    system.building.advance_sensors(now=datetime.now(UTC) + timedelta(seconds=5))

    assert system.simulation.tick() is None
    assert len(system.tickets.list()) == ticket_count
    snapshot = system.building.snapshot()
    assert snapshot["last_sensor_tick"] is not None
    assert snapshot["health"]["total"] == 60


def test_receptionist_request_is_published_then_consumed_by_operations(system):
    client = TestClient(create_app(system))
    published = client.post(
        "/api/simulation/request",
        json={
            "request_type": "enquiry",
            "subject": "Fitness center hours",
            "description": "What time does the fitness center close tonight?",
            "requester": "Priya Shah",
            "location_id": "BLDG-A-F02-FITNESS",
        },
    )

    assert published.status_code == 202
    message = published.json()
    ticket_id = message["payload"]["ticket_id"]
    assert message["topic"] == "building.events"
    assert message["payload"]["request"]["kind"] == "enquiry"
    assert message["payload"]["scenario"]["source"] == "receptionist_console"
    assert system.repository.get_ticket(ticket_id) is None

    system.operations.process_due(
        now=datetime.now(UTC) + timedelta(hours=1), limit=10
    )

    ticket = system.repository.get_ticket(ticket_id)
    assert ticket is not None
    assert ticket.subject == "Fitness center hours"
    assert system.repository.get_workflow_state(ticket_id) is not None
    assert system.message_bus.stats()["completed"] >= 1


def test_request_type_injects_correlated_building_condition(system):
    assert system.building.telemetry("AHU-ZONE-4B")["temperature_f"] == 72.7
    assert system.building.telemetry("ELEC-PNL-7A")["status"] == "operational"

    system.simulation.publish_request(
        request=TicketCreate(
            subject="Apartment 4B is too warm",
            description="The living room is hot.",
            requester="Marcus Lee",
            location_id="BLDG-A-F04-APT-4B",
            kind="service_request",
        ),
        request_type="service_request",
        condition_type="temperature_high",
    )
    assert system.building.telemetry("AHU-ZONE-4B")["temperature_f"] == 77.2

    system.simulation.publish_request(
        request=TicketCreate(
            subject="Burning smell on Floor 7",
            description="The lights are flickering and there is a burning smell.",
            requester="Elena Garcia",
            location_id="BLDG-A-F07-EAST",
            kind="incident",
        ),
        request_type="incident",
        condition_type="electrical_overheat",
    )
    assert system.building.telemetry("ELEC-PNL-7A")["status"] == "fault"


def test_floor_five_pantry_odor_correlates_ticket_sensor_and_agent(system):
    client = TestClient(create_app(system))
    published = client.post(
        "/api/simulation/request",
        json={
            "request_type": "incident",
            "condition_type": "smoke_or_odor",
            "subject": "Burning smell in the Floor 5 pantry",
            "description": "There is a strong burning smell in the pantry and it is getting worse.",
            "requester": "Building Resident",
            "location_id": "BLDG-A-F05-APT-5E",
        },
    )
    assert published.status_code == 202
    ticket_id = published.json()["payload"]["ticket_id"]
    snapshot = system.building.snapshot()
    alarm = snapshot["sensor_overrides"]["VOC-05-01"]
    assert alarm["area"] == "Apt 5E"
    assert alarm["state"] == "Critical"
    assert snapshot["active_conditions"][ticket_id]["sensor_id"] == "VOC-05-01"

    for _ in range(3):
        system.operations.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=10)
    detail = system.tickets.detail(ticket_id)
    assert detail.ticket.status == "waiting_technician"
    assert detail.actions[0].requested["asset_id"] == "VOC-05-01"
    assert detail.actions[0].requested["trade"] == "indoor_air_quality"
    assert detail.actions[0].status == "completed"
    assert detail.work_order and detail.work_order.status == "in_progress"


def test_digital_twin_owns_all_sensors_and_rolling_history(system):
    initial = system.building.snapshot()
    assert len(initial["sensors"]) == 60
    assert initial["health"] == {
        "total": 60,
        "normal": 60,
        "warning": 0,
        "critical": 0,
        "monitoring": "autonomous",
    }

    system.building.advance_sensors(now=datetime.now(UTC) + timedelta(seconds=5))
    advanced = system.building.snapshot()
    assert advanced["last_sensor_tick"] is not None
    assert len(advanced["sensor_history"]["AIR-06-01"]) == 2


def test_agent_uses_sensor_alarm_and_maintenance_history_without_complaint(system):
    message = None
    for _ in range(10):
        candidate = system.simulation.tick(force=True)
        if candidate and candidate.payload["scenario"]["type"] == "sensor_anomaly":
            message = candidate
            break
    assert message is not None
    ticket_id = str(message.payload["ticket_id"])
    for _ in range(3):
        system.operations.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=20)

    detail = system.tickets.detail(ticket_id)
    correlated = next(event for event in detail.events if event.event_type == "evidence.correlated")
    decision = next(event for event in detail.events if event.event_type == "agent.decision")
    assert correlated.payload["primary_sensor"]["id"] == "VOC-06-01"
    assert correlated.payload["maintenance_history"]
    assert "Live telemetry" in decision.summary
    assert detail.ticket.status == "waiting_technician"
    assert detail.work_order and detail.work_order.trade == "indoor_air_quality"


def test_safety_language_corrects_a_mismatched_console_scenario_and_dispatches(system):
    client = TestClient(create_app(system))
    published = client.post(
        "/api/simulation/request",
        json={
            "request_type": "service_request",
            "condition_type": "temperature_high",
            "subject": "Fumes and a bad circuit smell on Floor 4",
            "description": "There are fumes and a bad circuit smell in the Floor 4 laundry room.",
            "requester": "Marcus Lee",
            "location_id": "BLDG-A-F04-APT-4B",
        },
    )

    assert published.status_code == 202
    payload = published.json()["payload"]
    ticket_id = payload["ticket_id"]
    scenario = payload["scenario"]
    assert scenario["scenario_type"] == "incident"
    assert scenario["condition"]["condition"] == "electrical_overheat"
    assert scenario["condition"]["sensor_id"] == "PWR-04-01"
    assert payload["request"]["location_id"] == "BLDG-A-F04-LAUNDRY-ROOM"
    assert scenario["requested_location_id"] == "BLDG-A-F04-APT-4B"
    assert scenario["normalization"]

    for _ in range(3):
        system.operations.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=10)

    detail = system.tickets.detail(ticket_id)
    assert detail.ticket.kind == "incident"
    assert detail.ticket.status == "waiting_technician"
    assert detail.work_order and detail.work_order.status == "in_progress"
    assert detail.work_order.asset_id == "PWR-04-01"
    assert "laundry" in detail.work_order.procedure.lower()
    assert detail.actions[0].policy_rule == "OPS-DISPATCH-003"
    assert not any(event.event_type == "approval.requested" for event in detail.events)
    evidence = next(event for event in detail.events if event.event_type == "evidence.collected")
    assert "PWR-04-01" in evidence.summary
    assert "126.4°F" in evidence.summary

    system.operations.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=10)
    system.operations.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=10)
    completed = system.tickets.detail(ticket_id)
    assert completed.ticket.status == "resolved"
    assert completed.work_order and "loose neutral terminal" in completed.work_order.completion_notes
