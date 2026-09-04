from fastapi.testclient import TestClient

from backend.app.domain.models import TicketCreate
from backend.app.main import create_app


def test_seed_and_enquiry_vertical_slice(system):
    client = TestClient(create_app(system))
    response = client.post("/api/workspace/sample-requests")
    assert response.status_code == 200
    for _ in range(20):
        system.workflow.process_due(limit=10)
    detail = client.get("/api/tickets/TKT-1001").json()
    assert detail["ticket"]["status"] == "resolved"
    assert any("Source:" in event["summary"] for event in detail["events"])


def test_system_endpoint_names_replaceable_providers(system):
    payload = TestClient(create_app(system)).get("/api/system").json()
    assert payload["portable_contracts"] is True
    assert payload["providers"]["persistence"] == "SQLiteOperationsRepository"


def test_staff_can_answer_an_escalated_request_and_close_it(system):
    client = TestClient(create_app(system))
    ticket = system.tickets.create(
        TicketCreate(
            subject="Unexpected request",
            description="Something unusual happened and I need help.",
            requester="Priya Shah",
            location_id="BLDG-A-LOBBY",
        )
    )
    for _ in range(20):
        system.workflow.process_due(limit=10)
    assert system.tickets.detail(ticket.ticket_id).ticket.status == "escalated"

    response = client.post(
        f"/api/tickets/{ticket.ticket_id}/staff-response",
        json={
            "response": "Northstar Residences is a residential apartment tower.",
            "actor": "Maya Roberts",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"

    detail = client.get(f"/api/tickets/{ticket.ticket_id}").json()
    assert detail["workflow"]["status"] == "completed"
    assert detail["workflow"]["checkpoint"]["resolution"] == "staff_response"
    assert [event["event_type"] for event in detail["events"]][-2:] == [
        "staff.response_sent",
        "ticket.resolved",
    ]
    assert detail["events"][-2]["payload"]["notification"]["channel"] == "ticket_conversation"

    metrics = client.get("/api/metrics").json()
    assert metrics["active"] == 0
    assert metrics["escalated"] == 0
    assert metrics["resolved"] == 1
    assert metrics["autonomous_resolutions"] == 0

    repeated = client.post(
        f"/api/tickets/{ticket.ticket_id}/staff-response",
        json={
            "response": "Northstar Residences is a residential apartment tower.",
            "actor": "Maya Roberts",
        },
    )
    assert repeated.status_code == 200
    assert len(system.repository.list_events(ticket.ticket_id)) == len(detail["events"])


def test_building_type_question_is_answered_from_trusted_knowledge(system):
    ticket = system.tickets.create(
        TicketCreate(
            subject="Is this an office building or residential?",
            description="Please tell me what type of building this is.",
            requester="Priya Shah",
            location_id="BLDG-A-LOBBY",
        )
    )
    for _ in range(20):
        system.workflow.process_due(limit=10)

    detail = system.tickets.detail(ticket.ticket_id)
    assert detail.ticket.status == "resolved"
    answer = next(event for event in detail.events if event.event_type == "message.sent" and "Source:" in event.summary)
    assert "residential apartment tower" in answer.summary
    assert "Property Profile" in answer.summary
