from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_seed_and_enquiry_vertical_slice(system):
    client = TestClient(create_app(system))
    response = client.post("/api/demo/seed")
    assert response.status_code == 200
    detail = client.get("/api/tickets/TKT-1001").json()
    assert detail["ticket"]["status"] == "resolved"
    assert any("Source:" in event["summary"] for event in detail["events"])


def test_system_endpoint_names_replaceable_providers(system):
    payload = TestClient(create_app(system)).get("/api/system").json()
    assert payload["portable_contracts"] is True
    assert payload["providers"]["persistence"] == "SQLiteOperationsRepository"
