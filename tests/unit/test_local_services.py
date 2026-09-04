from backend.app.config import Settings
from scripts.run_operations import operations_commands


def test_operations_service_launches_api_and_configured_worker_pool(monkeypatch):
    monkeypatch.setenv("AGENT_WORKER_COUNT", "4")
    settings = Settings.from_env()
    commands = operations_commands(settings.agent_worker_count)

    assert settings.agent_worker_count == 4
    assert len(commands) == 5
    assert "uvicorn" in commands[0]
    assert all("local_worker" in command[-1] for command in commands[1:])
