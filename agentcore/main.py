"""Amazon Bedrock AgentCore entrypoint for BuildingOps specialist reasoning."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from backend.app.agents.runtime import StrandsAgentRuntime
from backend.app.config import Settings
from backend.app.domain.models import CoordinatorDirective, SpecialistReport, Ticket


app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    if payload.get("schema_version") != "1":
        raise ValueError("Unsupported request schema")
    runtime = StrandsAgentRuntime(Settings.from_env())
    ticket = Ticket.model_validate(payload["ticket"])
    operation = payload.get("operation")
    if operation == "run_specialist":
        report = runtime.run_specialist(payload["role"], ticket, payload["context"])
        return {"schema_version": "1", "report": report.model_dump(mode="json")}
    if operation == "coordinate":
        reports = [SpecialistReport.model_validate(item) for item in payload.get("reports", [])]
        directive = runtime.coordinate(
            ticket,
            payload["context"],
            reports,
            int(payload["iteration"]),
        )
        return {"schema_version": "1", "directive": directive.model_dump(mode="json")}
    raise ValueError(f"Unsupported operation: {operation}")


if __name__ == "__main__":
    app.run()
