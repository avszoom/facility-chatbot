from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.config import Settings
from backend.app.domain.models import Ticket, utc_now
from backend.app.system import build_system


def main() -> None:
    settings = Settings.from_env()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is missing from the local .env file")
    with TemporaryDirectory(prefix="buildingops-openai-") as directory:
        system = build_system(
            replace(
                settings,
                database_path=Path(directory) / "verification.db",
                agent_runtime="openai",
                simulation_enabled=False,
            )
        )
        now = utc_now()
        ticket = Ticket(
            ticket_id="TKT-OPENAI-CHECK",
            subject="Unusual smell in the Floor 5 pantry",
            description="There is a sharp burning odor near the pantry exhaust. Please investigate.",
            requester="Local verification",
            location_id="BLDG-A-F05-PANTRY",
            sla_due_at=now,
            created_at=now,
            updated_at=now,
        )
        context = {
            "eligible_actions": [
                "answer_enquiry",
                "inspect_temperature",
                "investigate_incident",
                "escalate",
            ],
            "known_locations": [f"BLDG-A-F{floor:02d}" for floor in range(1, 11)],
            "knowledge_result": system.knowledge.search(f"{ticket.subject} {ticket.description}"),
            "building_facts": system.building.investigation_context(ticket),
        }
        decision = system.agent.decide(ticket, context)
        print(
            "PASS live OpenAI/Strands decision: "
            f"provider={decision.model_provider}, model={decision.model_id}, "
            f"action={decision.selected_action}, sensors={decision.evidence_sensor_ids}, "
            f"tools={decision.tool_calls}"
        )


if __name__ == "__main__":
    main()
