from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    database_path: Path = Path("data/buildingops.db")
    agent_runtime: str = "deterministic"
    openai_api_key: str | None = None
    openai_model_id: str = "gpt-5.2"
    openai_store: bool = False
    openai_reasoning_effort: str = "low"
    openai_max_output_tokens: int = 1200
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    aws_region: str = "us-east-1"
    worker_poll_seconds: float = 0.25
    agent_worker_count: int = 3
    message_max_attempts: int = 3
    message_retry_base_seconds: float = 1.0
    message_lease_seconds: float = 30.0
    intake_delay_seconds: float = 0.8
    agent_analysis_seconds: float = 2.2
    action_delay_seconds: float = 1.6
    technician_delay_seconds: float = 12.0
    verification_delay_seconds: float = 3.0
    simulation_enabled: bool = False
    simulation_interval_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "local"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/buildingops.db")),
            agent_runtime=os.getenv("AGENT_RUNTIME", "deterministic").lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model_id=os.getenv("OPENAI_MODEL", "gpt-5.2"),
            openai_store=os.getenv("OPENAI_STORE", "false").lower()
            in {"1", "true", "yes", "on"},
            openai_reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "low"),
            openai_max_output_tokens=max(
                300, int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1200"))
            ),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
            ),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            worker_poll_seconds=max(0.05, float(os.getenv("WORKER_POLL_SECONDS", "0.25"))),
            agent_worker_count=max(1, int(os.getenv("AGENT_WORKER_COUNT", "3"))),
            message_max_attempts=max(1, int(os.getenv("MESSAGE_MAX_ATTEMPTS", "3"))),
            message_retry_base_seconds=max(
                0.0, float(os.getenv("MESSAGE_RETRY_BASE_SECONDS", "1"))
            ),
            message_lease_seconds=max(
                1.0, float(os.getenv("MESSAGE_LEASE_SECONDS", "30"))
            ),
            intake_delay_seconds=max(0.0, float(os.getenv("INTAKE_DELAY_SECONDS", "0.8"))),
            agent_analysis_seconds=max(0.0, float(os.getenv("AGENT_ANALYSIS_SECONDS", "2.2"))),
            action_delay_seconds=max(0.0, float(os.getenv("ACTION_DELAY_SECONDS", "1.6"))),
            technician_delay_seconds=max(
                0.0, float(os.getenv("TECHNICIAN_DELAY_SECONDS", "12"))
            ),
            verification_delay_seconds=max(
                0.0, float(os.getenv("VERIFICATION_DELAY_SECONDS", "3"))
            ),
            simulation_enabled=os.getenv("SIMULATION_ENABLED", "false").lower()
            not in {"0", "false", "no", "off"},
            simulation_interval_seconds=max(
                5.0, float(os.getenv("SIMULATION_INTERVAL_SECONDS", "45"))
            ),
        )
