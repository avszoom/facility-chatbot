from __future__ import annotations

import json
from typing import Any

from backend.app.config import Settings
from backend.app.domain.models import (
    AgentDecision,
    Ticket,
    TicketKind,
    TicketPriority,
)


SYSTEM_PROMPT = """You are BuildingOps Autopilot, an accountable professional agent for a commercial building.
Classify one support ticket and select exactly one eligible next action. Treat burning smells, smoke,
sparking, trapped occupants, flooding near electricity, or life-safety failures as safety issues.
Never claim an action was performed: you propose a typed next step and deterministic policy decides
whether a tool may execute. Keep the user update concise and avoid hidden chain-of-thought.
"""


class DeterministicAgentRuntime:
    """Offline/test runtime behind the same contract used by Strands and AgentCore."""

    name = "deterministic-local"

    def decide(self, ticket: Ticket, context: dict[str, Any]) -> AgentDecision:
        text = f"{ticket.subject} {ticket.description}".lower()
        building_facts = context.get("building_facts", {})
        primary_sensor = building_facts.get("primary_sensor") or {}
        sensor_state = primary_sensor.get("state")
        sensor_type = str(primary_sensor.get("type", "")).lower()
        sensor_incident = sensor_state in {"Warning", "Critical"} and any(
            category in sensor_type
            for category in ("voc", "odor", "cabinet", "electrical", "smoke", "co₂")
        )
        safety = [
            label for term, label in (
                ("burning", "possible electrical fire"),
                ("smell", "unusual odor"),
                ("smoke", "possible smoke"),
                ("flicker", "electrical instability"),
                ("trapped", "occupant safety"),
                ("flood", "water damage"),
            )
            if term in text
        ]
        if sensor_incident:
            safety.append(f"{primary_sensor.get('id', 'building sensor')} {sensor_state.lower()} alarm")
        if safety or sensor_incident:
            return AgentDecision(
                kind=TicketKind.INCIDENT,
                priority=TicketPriority.EMERGENCY if "smoke" in text or "trapped" in text or sensor_state == "Critical" else TicketPriority.HIGH,
                safety_flags=safety,
                objective="Protect occupants, correlate building evidence, and route qualified physical work.",
                selected_action="investigate_incident",
                confidence=0.98 if sensor_incident else 0.96,
                rationale=(
                    f"Live telemetry from {primary_sensor.get('id')} confirms a {sensor_state.lower()} {primary_sensor.get('type')} condition; the request, trend and maintenance record require evidence-led incident handling."
                    if sensor_incident
                    else "Safety language and an abnormal building symptom require evidence-led incident handling."
                ),
                user_update="I flagged this for immediate safety triage and started checking the affected systems.",
            )
        sensor_comfort = sensor_state in {"Warning", "Critical"} and "temperature" in sensor_type
        if sensor_comfort or any(term in text for term in ("warm", "hot", "cold", "temperature", "stuffy")):
            return AgentDecision(
                kind=TicketKind.SERVICE_REQUEST,
                priority=TicketPriority.NORMAL,
                objective="Check room conditions and apply only a policy-safe comfort adjustment.",
                selected_action="inspect_temperature",
                confidence=0.97 if sensor_comfort else 0.93,
                rationale=(
                    f"Live telemetry from {primary_sensor.get('id')} confirms the reported comfort drift and a reversible control path is available."
                    if sensor_comfort
                    else "The request describes an occupied-zone comfort issue with a reversible control path."
                ),
                user_update="I’m checking the room conditions and the approved comfort range now.",
            )
        if any(
            term in text
            for term in (
                "when",
                "what time",
                "hours",
                "open",
                "close",
                "gym",
                "fitness",
                "delivery",
                "visitor check-in",
                "package",
                "mailroom",
                "bicycle",
                "bike",
                "wellness room",
                "recycling",
            )
        ):
            return AgentDecision(
                kind=TicketKind.ENQUIRY,
                priority=TicketPriority.LOW,
                objective="Answer from authoritative building information and close the request.",
                selected_action="answer_enquiry",
                confidence=0.95,
                rationale="The request asks for building information and does not require an operational change.",
                user_update="I’m checking the current building information for you.",
            )
        return AgentDecision(
            kind=TicketKind.UNKNOWN,
            priority=TicketPriority.NORMAL,
            objective="Route an unclear request to a facility operator.",
            selected_action="escalate",
            confidence=0.45,
            rationale="The request does not match a supported and safely automatable path.",
            user_update="I need a facility operator to review this request.",
        )


class StrandsAgentRuntime:
    """Real Strands runtime. Domain orchestration remains outside the model session."""

    name = "strands-local"

    def __init__(self, settings: Settings):
        self.settings = settings

    def decide(self, ticket: Ticket, context: dict[str, Any]) -> AgentDecision:
        try:
            from strands import Agent, tool
        except ImportError as exc:  # pragma: no cover - installation concern
            raise RuntimeError("Install the strands-agents package to use AGENT_RUNTIME=strands") from exc

        @tool
        def read_ticket_context() -> dict[str, Any]:
            """Return the trusted ticket and eligible-action context for this decision."""
            return {
                "ticket": ticket.model_dump(mode="json"),
                "eligible_actions": context.get("eligible_actions", []),
                "known_locations": context.get("known_locations", []),
            }

        @tool
        def read_relevant_building_facts() -> dict[str, Any]:
            """Return pre-fetched, read-only building facts relevant to the ticket."""
            return context.get("building_facts", {})

        @tool
        def search_building_knowledge(query: str) -> dict[str, Any]:
            """Search the trusted building handbook for a support-ticket question."""
            record = context.get("knowledge_result")
            return record or {"found": False, "query": query}

        model = self.settings.bedrock_model_id
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[read_ticket_context, read_relevant_building_facts, search_building_knowledge],
            callback_handler=None,
            agent_id="buildingops-ticket-triage",
            trace_attributes={"ticket.id": ticket.ticket_id, "app.name": "buildingops-autopilot"},
        )
        prompt = (
            "Decide the next action for this ticket. Use tools to inspect trusted context. "
            "Return only the requested structured decision.\n"
            + json.dumps(ticket.model_dump(mode="json"), default=str)
        )
        result = agent(prompt, structured_output_model=AgentDecision)
        if result.structured_output is None:
            raise RuntimeError("Strands returned no structured decision")
        return AgentDecision.model_validate(result.structured_output)


def runtime_from_settings(settings: Settings):
    if settings.agent_runtime == "strands":
        return StrandsAgentRuntime(settings)
    if settings.agent_runtime != "deterministic":
        raise ValueError(f"Unsupported AGENT_RUNTIME={settings.agent_runtime}")
    return DeterministicAgentRuntime()
