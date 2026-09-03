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
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    aws_region: str = "us-east-1"
    worker_poll_seconds: float = 0.25
    intake_delay_seconds: float = 0.8
    agent_analysis_seconds: float = 2.2
    action_delay_seconds: float = 1.6
    technician_delay_seconds: float = 12.0
    verification_delay_seconds: float = 3.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "local"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/buildingops.db")),
            agent_runtime=os.getenv("AGENT_RUNTIME", "deterministic").lower(),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
            ),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            worker_poll_seconds=max(0.05, float(os.getenv("WORKER_POLL_SECONDS", "0.25"))),
            intake_delay_seconds=max(0.0, float(os.getenv("INTAKE_DELAY_SECONDS", "0.8"))),
            agent_analysis_seconds=max(0.0, float(os.getenv("AGENT_ANALYSIS_SECONDS", "2.2"))),
            action_delay_seconds=max(0.0, float(os.getenv("ACTION_DELAY_SECONDS", "1.6"))),
            technician_delay_seconds=max(
                0.0, float(os.getenv("TECHNICIAN_DELAY_SECONDS", "12"))
            ),
            verification_delay_seconds=max(
                0.0, float(os.getenv("VERIFICATION_DELAY_SECONDS", "3"))
            ),
        )
