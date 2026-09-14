from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.runtime import StrandsAgentRuntime
from backend.app.config import Settings
from backend.app.system import build_system


def test_bedrock_uses_explicit_region_and_token_limit():
    with patch("strands.models.BedrockModel") as model:
        StrandsAgentRuntime(Settings(aws_region="us-east-2", bedrock_max_tokens=2048))._model()
    assert model.call_args.kwargs["region_name"] == "us-east-2"
    assert model.call_args.kwargs["max_tokens"] == 2048


def test_cloud_rejects_openai_and_deterministic(tmp_path):
    for runtime in ["openai", "deterministic"]:
        with pytest.raises(ValueError, match="requires Bedrock"):
            build_system(Settings(app_env="aws_ec2", agent_runtime=runtime, database_path=tmp_path / "app.db"))


def test_cloud_does_not_hide_model_errors_with_deterministic_reports():
    runtime = StrandsAgentRuntime(Settings(app_env="aws_ec2", agent_runtime="bedrock"))
    with patch.object(runtime, "_run_specialist", side_effect=RuntimeError("unavailable")):
        with pytest.raises(RuntimeError, match="Bedrock specialist failed"):
            runtime.run_specialist("Resident Knowledge Agent", None, {})


def test_cloud_reports_real_adapters_and_rejects_debug_and_cross_origin(tmp_path):
    from backend.app.main import create_app

    system = build_system(Settings(app_env="aws_ec2", agent_runtime="bedrock", database_path=tmp_path / "app.db"))
    with TestClient(create_app(system)) as client:
        info = client.get("/api/system").json()
        assert info["environment"] == "aws_ec2"
        assert info["providers"]["agent_provider"] == "amazon-bedrock"
        assert info["providers"]["persistence"] == "SQLiteOperationsRepository"
        assert client.post("/api/workspace/process-scheduled").status_code == 404
        assert client.post("/api/tickets", headers={"origin": "https://untrusted.example"}, json={}).status_code == 403
        assert client.post("/api/tickets", headers={"origin": "https://testserver"}, json={}).status_code == 422
