from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.app.domain.models import PubSubMessage, TicketCreate
from backend.app.messaging.ports import MessageBusPort
from backend.app.repositories.ports import OperationsRepository
from backend.app.services.events import LocalEventBus
from backend.app.services.tickets import TicketService
from backend.app.tools.ports import BuildingPort


SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "event": "occupant_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "What time does the fitness center close?",
        "description": "I would like to use the fitness center after work. What are tonight’s hours?",
        "requester": "Priya Shah",
        "location_id": "BLDG-A-F01-FITNESS",
    },
    {
        "event": "comfort_drift",
        "scenario_type": "service_request",
        "condition": "comfort_drift",
        "subject": "Conference Room 4B is getting too warm",
        "description": "The room feels hot during our client meeting. Can facilities check the temperature?",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-F04-CONF-4B",
    },
    {
        "event": "visitor_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where should my visitor check in?",
        "description": "A client is arriving for a Floor 8 meeting. What is the visitor check-in process?",
        "requester": "Building Occupant",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "sensor_malfunction",
        "scenario_type": "incident",
        "condition": "electrical_overheat",
        "subject": "Flickering lights and burning smell on Floor 7",
        "description": "Lights are flickering near the east offices and we smell hot plastic.",
        "requester": "Elena Garcia",
        "location_id": "BLDG-A-F07-EAST",
    },
    {
        "event": "delivery_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where should today’s catering delivery arrive?",
        "description": "The catering team is downstairs and needs the approved delivery entrance.",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "mailroom_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "When can I collect a package from the mailroom?",
        "description": "I received a delivery notification. What are the staffed package collection hours?",
        "requester": "Building Occupant",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "amenity_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "How do I access the bicycle room?",
        "description": "I plan to cycle tomorrow. Where is bicycle storage and what access is required?",
        "requester": "Priya Shah",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "amenity_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where is the wellness room?",
        "description": "Could you tell me where the wellness room is and whether it needs a reservation?",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "operations_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where should confidential recycling go?",
        "description": "We have several boxes of documents. What is the secure recycling procedure?",
        "requester": "Elena Garcia",
        "location_id": "BLDG-A-F07-EAST",
    },
    {
        "event": "occupant_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Is the fitness center open on weekends?",
        "description": "What are the Saturday and Sunday fitness center hours?",
        "requester": "Building Occupant",
        "location_id": "BLDG-A-F01-FITNESS",
    },
)


class BuildingSimulationService:
    """Independent world engine that emits durable demand into the ticket boundary."""

    STATE_KEY = "building_simulation"
    DEDUP_WINDOW = timedelta(minutes=20)

    def __init__(
        self,
        repository: OperationsRepository,
        tickets: TicketService,
        building: BuildingPort,
        events: LocalEventBus,
        message_bus: MessageBusPort,
        *,
        enabled: bool = True,
        interval_seconds: float = 45.0,
    ):
        self.repository = repository
        self.tickets = tickets
        self.building = building
        self.events = events
        self.message_bus = message_bus
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        if self.repository.get_state(self.STATE_KEY) is None:
            self.repository.set_state(self.STATE_KEY, self._default_state())

    def _default_state(self) -> dict[str, Any]:
        return {
            "status": "online" if self.enabled else "paused",
            "running": self.enabled,
            "sequence": 0,
            "issues_generated": 0,
            "interval_seconds": self.interval_seconds,
            "last_tick": None,
            "next_tick": (datetime.now(UTC) + timedelta(seconds=4)).isoformat(),
            "last_event": None,
        }

    def status(self) -> dict[str, Any]:
        state = self.repository.get_state(self.STATE_KEY)
        if state is None:
            state = self._default_state()
            self.repository.set_state(self.STATE_KEY, state)
        return {
            **state,
            "status": "online" if state.get("running", self.enabled) else "paused",
            "running": bool(state.get("running", self.enabled)),
            "interval_seconds": float(
                state.get("interval_seconds", self.interval_seconds)
            ),
            "scenario_count": len(SCENARIOS),
            "scenario_types": {
                scenario_type: sum(
                    scenario["scenario_type"] == scenario_type
                    for scenario in SCENARIOS
                )
                for scenario_type in ("enquiry", "service_request", "incident")
            },
        }

    def configure(self, *, running: bool, interval_seconds: float) -> dict[str, Any]:
        state = self.status()
        now = datetime.now(UTC)
        state.update(
            {
                "running": running,
                "status": "online" if running else "paused",
                "interval_seconds": interval_seconds,
                "next_tick": (now + timedelta(seconds=interval_seconds)).isoformat(),
            }
        )
        state.pop("scenario_count", None)
        state.pop("scenario_types", None)
        self.repository.set_state(self.STATE_KEY, state)
        self.events.publish({"type": "simulation.configured", "running": running})
        return self.status()

    def generate_batch(
        self, *, count: int, scenario_type: str = "all"
    ) -> list[PubSubMessage]:
        messages: list[PubSubMessage] = []
        for _ in range(count):
            message = self.tick(force=True, scenario_type=scenario_type)
            if message:
                messages.append(message)
        return messages

    def tick(
        self,
        *,
        now: datetime | None = None,
        force: bool = False,
        scenario_type: str = "all",
    ) -> PubSubMessage | None:
        current = now or datetime.now(UTC)
        state = self.status()
        if not state.get("running", self.enabled) and not force:
            return None
        next_tick = datetime.fromisoformat(state["next_tick"]) if state.get("next_tick") else current
        if not force and next_tick > current:
            return None
        start = int(state.get("sequence", 0))
        recent_subjects = {
            ticket.subject
            for ticket in self.tickets.list()
            if ticket.created_at >= current - self.DEDUP_WINDOW
        }
        candidates = [
            (start + offset, SCENARIOS[(start + offset) % len(SCENARIOS)])
            for offset in range(len(SCENARIOS))
            if (
                scenario_type == "all"
                or SCENARIOS[(start + offset) % len(SCENARIOS)]["scenario_type"]
                == scenario_type
            )
            and (
                force
                or str(SCENARIOS[(start + offset) % len(SCENARIOS)]["subject"])
                not in recent_subjects
            )
        ]
        if not candidates:
            state["next_tick"] = (
                current + timedelta(seconds=float(state["interval_seconds"]))
            ).isoformat()
            state["duplicates_suppressed"] = int(state.get("duplicates_suppressed", 0)) + 1
            self.repository.set_state(self.STATE_KEY, state)
            return None
        scenario_index, scenario = candidates[0]
        condition = self.building.inject_simulated_condition(str(scenario["condition"]))
        request = TicketCreate(
            subject=str(scenario["subject"]),
            description=str(scenario["description"]),
            requester=str(scenario["requester"]),
            location_id=str(scenario["location_id"]),
        )
        ticket_id = f"TKT-{uuid4().hex[:6].upper()}"
        message = self.message_bus.publish(
            topic="building.events",
            message_type="building.request.detected",
            payload={
                "ticket_id": ticket_id,
                "request": request.model_dump(mode="json"),
                "scenario": {
                    "type": scenario["event"],
                    "scenario_type": scenario["scenario_type"],
                    "condition": condition,
                },
            },
            correlation_id=f"CORR-{ticket_id}",
            idempotency_key=f"BUILDING-EVENT-{ticket_id}",
            message_id=f"MSG-BUILDING-{ticket_id}",
            available_at=current,
        )
        next_at = current + timedelta(seconds=float(state["interval_seconds"]))
        next_state = {
            "status": "online" if state.get("running", self.enabled) else "paused",
            "running": bool(state.get("running", self.enabled)),
            "interval_seconds": float(state["interval_seconds"]),
            "sequence": scenario_index + 1,
            "issues_generated": int(state.get("issues_generated", 0)) + 1,
            "duplicates_suppressed": int(state.get("duplicates_suppressed", 0)),
            "last_tick": current.isoformat(),
            "next_tick": next_at.isoformat(),
            "last_event": {
                "type": scenario["event"],
                "message_id": message.message_id,
                "ticket_id": ticket_id,
                "subject": request.subject,
                "location_id": request.location_id,
                "condition": condition,
            },
        }
        self.repository.set_state(self.STATE_KEY, next_state)
        self.events.publish({"type": "simulation.generated", "ticket_id": ticket_id})
        return message
