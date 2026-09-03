from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.domain.models import Ticket, TicketCreate
from backend.app.repositories.ports import OperationsRepository
from backend.app.services.events import LocalEventBus
from backend.app.services.tickets import TicketService
from backend.app.tools.ports import BuildingPort


SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "event": "occupant_enquiry",
        "condition": "normal",
        "subject": "What time does the fitness center close?",
        "description": "I would like to use the fitness center after work. What are tonight’s hours?",
        "requester": "Priya Shah",
        "location_id": "BLDG-A-F01-FITNESS",
    },
    {
        "event": "comfort_drift",
        "condition": "comfort_drift",
        "subject": "Conference Room 4B is getting too warm",
        "description": "The room feels hot during our client meeting. Can facilities check the temperature?",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-F04-CONF-4B",
    },
    {
        "event": "occupant_access_request",
        "condition": "normal",
        "subject": "Visitor badge is not activating the lift",
        "description": "My guest badge will not select Floor 8. Please help us reach the meeting.",
        "requester": "Building Occupant",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "sensor_malfunction",
        "condition": "electrical_overheat",
        "subject": "Flickering lights and burning smell on Floor 7",
        "description": "Lights are flickering near the east offices and we smell hot plastic.",
        "requester": "Elena Garcia",
        "location_id": "BLDG-A-F07-EAST",
    },
    {
        "event": "delivery_enquiry",
        "condition": "normal",
        "subject": "Where should today’s catering delivery arrive?",
        "description": "The catering team is downstairs and needs the approved delivery entrance.",
        "requester": "Marcus Lee",
        "location_id": "BLDG-A-LOBBY",
    },
    {
        "event": "equipment_report",
        "condition": "normal",
        "subject": "Conference room display is offline",
        "description": "The wall display in Conference Room 4B is blank before a client meeting.",
        "requester": "Building Occupant",
        "location_id": "BLDG-A-F04-CONF-4B",
    },
)


class BuildingSimulationService:
    """Independent world engine that emits durable demand into the ticket boundary."""

    STATE_KEY = "building_simulation"

    def __init__(
        self,
        repository: OperationsRepository,
        tickets: TicketService,
        building: BuildingPort,
        events: LocalEventBus,
        *,
        enabled: bool = True,
        interval_seconds: float = 45.0,
    ):
        self.repository = repository
        self.tickets = tickets
        self.building = building
        self.events = events
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        if self.repository.get_state(self.STATE_KEY) is None:
            self.repository.set_state(self.STATE_KEY, self._default_state())

    def _default_state(self) -> dict[str, Any]:
        return {
            "status": "online" if self.enabled else "paused",
            "sequence": 0,
            "issues_generated": 0,
            "last_tick": None,
            "next_tick": (datetime.now(UTC) + timedelta(seconds=4)).isoformat(),
            "last_event": None,
        }

    def status(self) -> dict[str, Any]:
        state = self.repository.get_state(self.STATE_KEY)
        if state is None:
            state = self._default_state()
            self.repository.set_state(self.STATE_KEY, state)
        return {**state, "status": "online" if self.enabled else "paused", "interval_seconds": self.interval_seconds}

    def tick(self, *, now: datetime | None = None, force: bool = False) -> Ticket | None:
        current = now or datetime.now(UTC)
        state = self.status()
        if not self.enabled and not force:
            return None
        next_tick = datetime.fromisoformat(state["next_tick"]) if state.get("next_tick") else current
        if not force and next_tick > current:
            return None
        scenario = SCENARIOS[int(state.get("sequence", 0)) % len(SCENARIOS)]
        condition = self.building.inject_simulated_condition(str(scenario["condition"]))
        ticket = self.tickets.create(
            TicketCreate(
                subject=str(scenario["subject"]),
                description=str(scenario["description"]),
                requester=str(scenario["requester"]),
                location_id=str(scenario["location_id"]),
            )
        )
        next_at = current + timedelta(seconds=self.interval_seconds)
        next_state = {
            "status": "online" if self.enabled else "paused",
            "sequence": int(state.get("sequence", 0)) + 1,
            "issues_generated": int(state.get("issues_generated", 0)) + 1,
            "last_tick": current.isoformat(),
            "next_tick": next_at.isoformat(),
            "last_event": {
                "type": scenario["event"],
                "ticket_id": ticket.ticket_id,
                "subject": ticket.subject,
                "location_id": ticket.location_id,
                "condition": condition,
            },
        }
        self.repository.set_state(self.STATE_KEY, next_state)
        self.events.publish({"type": "simulation.generated", "ticket_id": ticket.ticket_id})
        return ticket
