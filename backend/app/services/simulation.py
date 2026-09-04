from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
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
        "event": "resident_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "What time does the fitness center close?",
        "description": "I live in Apartment 5E and would like to use the fitness center tonight. What are its hours?",
        "requester": "Priya Shah",
        "location_id": "BLDG-A-F02-FITNESS",
    },
    {
        "event": "comfort_drift",
        "scenario_type": "service_request",
        "condition": "comfort_drift",
        "subject": "Apartment 4B is getting too warm",
        "description": "My living room feels hot even though the thermostat is set correctly. Can building operations check it?",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-F04-APT-4B",
    },
    {
        "event": "visitor_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where should my visitor check in?",
        "description": "A friend is visiting my apartment on Floor 8. What is the guest check-in process?",
        "requester": "Building Resident",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "sensor_malfunction",
        "scenario_type": "incident",
        "condition": "electrical_overheat",
        "subject": "Flickering lights and burning smell on Floor 7",
        "description": "The corridor lights are flickering in the east residential wing and we smell hot plastic.",
        "requester": "Elena Garcia",
        "location_id": "BLDG-A-F07-EAST",
    },
    {
        "event": "delivery_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where should my furniture delivery arrive?",
        "description": "My sofa delivery is scheduled today. Which entrance should the movers use, and do I need the service elevator?",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "parcel_room_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "When can I collect a package from the parcel room?",
        "description": "I received a delivery notification for a signature-required package. When can the concierge release it?",
        "requester": "Building Resident",
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
        "subject": "How do I reserve the sky lounge?",
        "description": "Could you tell me the sky lounge hours and whether I need a reservation for a birthday gathering?",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "operations_enquiry",
        "scenario_type": "enquiry",
        "condition": "normal",
        "subject": "Where should cardboard and recycling go?",
        "description": "I have moving boxes and household recycling. Should I use the refuse room or service elevator area?",
        "requester": "Elena Garcia",
        "location_id": "BLDG-A-F07-EAST",
    },
    {
        "event": "sensor_anomaly",
        "scenario_type": "incident",
        "condition": "air_quality",
        "subject": "Autonomous air-quality alert on Floor 6",
        "description": "No resident complaint is attached. The building monitor detected a sustained abnormal air-quality reading in the Floor 6 residential corridor.",
        "requester": "Building Monitoring",
        "location_id": "BLDG-A-F06-CORRIDOR",
        "source": "building_monitor",
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
        else:
            state = self.repository.get_state(self.STATE_KEY) or {}
            if state.get("running"):
                state.update({"running": False, "status": "paused"})
                self.repository.set_state(self.STATE_KEY, state)

    def _default_state(self) -> dict[str, Any]:
        return {
            "status": "paused",
            "running": False,
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
            "status": "paused",
            "running": False,
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
        if running:
            raise ValueError(
                "Automatic synthetic request generation is disabled; publish scenarios explicitly from the console."
            )
        state = self.status()
        now = datetime.now(UTC)
        state.update(
            {
                "running": False,
                "status": "paused",
                "interval_seconds": interval_seconds,
                "next_tick": (now + timedelta(seconds=interval_seconds)).isoformat(),
            }
        )
        state.pop("scenario_count", None)
        state.pop("scenario_types", None)
        self.repository.set_state(self.STATE_KEY, state)
        self.events.publish({"type": "simulation.configured", "running": False})
        return self.status()

    def generate_batch(
        self, *, count: int, scenario_type: str = "all"
    ) -> list[PubSubMessage]:
        messages: list[PubSubMessage] = []
        for _ in range(count):
            message = self.tick(
                force=True,
                scenario_type=scenario_type,
                source="request_generator_console",
            )
            if message:
                messages.append(message)
        return messages

    def publish_request(
        self,
        request: TicketCreate,
        *,
        request_type: str,
        condition_type: str = "normal",
        now: datetime | None = None,
    ) -> PubSubMessage:
        """Publish a receptionist-authored request through the building event boundary."""
        current = now or datetime.now(UTC)
        state = self.status()
        requested_type = request_type
        requested_condition = condition_type
        requested_location = request.location_id
        text = f"{request.subject} {request.description}".lower()
        normalization_notes: list[str] = []
        floor_match = re.search(r"\bfloor\s*(\d{1,2})\b", text)
        location_floor_match = re.search(r"-F(\d{2})(?:-|$)", request.location_id)
        floor = int(floor_match.group(1)) if floor_match else int(location_floor_match.group(1)) if location_floor_match else 1
        apartment_match = re.search(r"\b(?:apartment|apt|flat)\s*(\d{1,2}[a-z])\b", text)
        inferred_location = None
        if apartment_match:
            home = apartment_match.group(1).upper()
            inferred_location = f"BLDG-A-F{int(home[:-1]):02d}-APT-{home}"
        elif "laund" in text:
            inferred_location = f"BLDG-A-F{floor:02d}-LAUNDRY-ROOM"
        elif "sky lounge" in text:
            inferred_location = "BLDG-A-F10-SKY-LOUNGE"
        elif "pool" in text:
            inferred_location = "BLDG-A-F02-INDOOR-POOL"
        elif "fitness" in text or "gym" in text:
            inferred_location = "BLDG-A-F02-FITNESS"
        elif "cafe" in text or "café" in text:
            inferred_location = "BLDG-A-F01-NORTHSTAR-CAFE"
        elif "parcel room" in text or "mailroom" in text:
            inferred_location = "BLDG-A-F01-PARCEL-ROOM"
        elif "lobby" in text:
            inferred_location = "BLDG-A-LOBBY"
        if inferred_location and inferred_location != request.location_id:
            request = request.model_copy(update={"location_id": inferred_location})
            normalization_notes.append(
                f"Explicit request text resolved the location from {requested_location} to {inferred_location}."
            )
        safety_terms = ("burning", "smoke", "fume", "sparking", "trapped", "fire")
        electrical_terms = (
            "circuit",
            "electric",
            "outlet",
            "breaker",
            "wiring",
            "flicker",
            "spark",
        )
        safety_override = next((term for term in safety_terms if term in text), None)
        if safety_override:
            request_type = "incident"
            condition_type = (
                "electrical_overheat"
                if any(term in text for term in electrical_terms)
                else "smoke_or_odor"
            )
            if requested_type != request_type or requested_condition != condition_type:
                normalization_notes.append(
                    f"Safety language '{safety_override}' upgraded the request to an incident and matched {condition_type}."
                )
        request = request.model_copy(update={"kind": request_type})
        event_type = {
            "enquiry": "resident_enquiry",
            "service_request": "resident_service_request",
            "incident": "resident_incident",
        }[request_type]
        ticket_id = f"TKT-{uuid4().hex[:6].upper()}"
        condition_name = condition_type if request_type != "enquiry" else "normal"
        condition = self.building.inject_simulated_condition(
            condition_name,
            request.location_id,
            ticket_id,
        )
        message = self.message_bus.publish(
            topic="building.events",
            message_type="building.request.detected",
            payload={
                "ticket_id": ticket_id,
                "request": request.model_dump(mode="json"),
                "scenario": {
                    "type": event_type,
                    "scenario_type": request_type,
                    "condition": condition,
                    "source": "receptionist_console",
                    "requested_scenario_type": requested_type,
                    "requested_condition_type": requested_condition,
                    "requested_location_id": requested_location,
                    "normalization": " ".join(normalization_notes) or None,
                },
            },
            correlation_id=f"CORR-{ticket_id}",
            idempotency_key=f"BUILDING-EVENT-{ticket_id}",
            message_id=f"MSG-BUILDING-{ticket_id}",
            available_at=current,
        )
        next_state = {
            "status": "online" if state.get("running", self.enabled) else "paused",
            "running": bool(state.get("running", self.enabled)),
            "interval_seconds": float(state["interval_seconds"]),
            "sequence": int(state.get("sequence", 0)),
            "issues_generated": int(state.get("issues_generated", 0)) + 1,
            "duplicates_suppressed": int(state.get("duplicates_suppressed", 0)),
            "last_tick": current.isoformat(),
            "next_tick": state.get("next_tick"),
            "last_event": {
                "type": event_type,
                "message_id": message.message_id,
                "ticket_id": ticket_id,
                "subject": request.subject,
                "location_id": request.location_id,
                "condition": condition,
            },
        }
        self.repository.set_state(self.STATE_KEY, next_state)
        self.events.publish(
            {
                "type": "simulation.request_published",
                "ticket_id": ticket_id,
                "request_type": request_type,
            }
        )
        return message

    def tick(
        self,
        *,
        now: datetime | None = None,
        force: bool = False,
        scenario_type: str = "all",
        source: str | None = None,
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
        ticket_id = f"TKT-{uuid4().hex[:6].upper()}"
        condition = self.building.inject_simulated_condition(
            str(scenario["condition"]),
            str(scenario["location_id"]),
            ticket_id,
        )
        request = TicketCreate(
            subject=str(scenario["subject"]),
            description=str(scenario["description"]),
            requester=str(scenario["requester"]),
            location_id=str(scenario["location_id"]),
            kind=str(scenario["scenario_type"]),
        )
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
                    "source": source or scenario.get("source", "synthetic_resident"),
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
