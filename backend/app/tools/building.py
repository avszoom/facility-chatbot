from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from backend.app.domain.models import Ticket, TicketKind
from backend.app.repositories.ports import OperationsRepository


DEFAULT_BUILDING = {
    "assets": {
        "AHU-ZONE-4B": {
            "asset_id": "AHU-ZONE-4B",
            "name": "Conference Room 4B VAV",
            "type": "hvac_zone",
            "location_id": "BLDG-A-F04-CONF-4B",
            "temperature_f": 72.7,
            "setpoint_f": 72.0,
            "target_temperature_f": 72.5,
            "status": "operational",
        },
        "ELEC-PNL-7A": {
            "asset_id": "ELEC-PNL-7A",
            "name": "Floor 7 Lighting Distribution Panel",
            "type": "electrical_panel",
            "location_id": "BLDG-A-F07-ELEC-7A",
            "cabinet_temperature_f": 84.2,
            "current_amps": 30.4,
            "status": "operational",
        },
    },
    "history": {
        "AHU-ZONE-4B": [
            {"minutes_ago": 30, "temperature_f": 72.4, "setpoint_f": 72.0},
            {"minutes_ago": 15, "temperature_f": 72.6, "setpoint_f": 72.0},
            {"minutes_ago": 0, "temperature_f": 72.7, "setpoint_f": 72.0},
        ],
        "ELEC-PNL-7A": [
            {"minutes_ago": 30, "cabinet_temperature_f": 82.6, "current_amps": 29.8},
            {"minutes_ago": 15, "cabinet_temperature_f": 83.7, "current_amps": 30.1},
            {"minutes_ago": 0, "cabinet_temperature_f": 84.2, "current_amps": 30.4},
        ],
    },
    "updated_at": None,
}


class LocalBuildingProvider:
    """Simulated BMS port. AWS can replace this with IoT SiteWise/TwinMaker adapters."""

    STATE_KEY = "building"

    def __init__(self, repository: OperationsRepository):
        self.repository = repository
        if self.repository.get_state(self.STATE_KEY) is None:
            self.repository.set_state(self.STATE_KEY, deepcopy(DEFAULT_BUILDING))

    def reset(self) -> None:
        self.repository.set_state(self.STATE_KEY, deepcopy(DEFAULT_BUILDING))

    def _state(self) -> dict[str, Any]:
        return self.repository.get_state(self.STATE_KEY) or deepcopy(DEFAULT_BUILDING)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._state())

    def asset_at(self, location_id: str, asset_type: str | None = None) -> dict[str, Any] | None:
        assets = self._state()["assets"].values()
        exact = [asset for asset in assets if asset["location_id"] == location_id]
        candidates = exact or list(assets)
        if asset_type:
            candidates = [asset for asset in candidates if asset["type"] == asset_type]
        return deepcopy(candidates[0]) if candidates else None

    def telemetry(self, asset_id: str) -> dict[str, Any]:
        asset = self._state()["assets"].get(asset_id)
        if not asset:
            raise KeyError(f"Unknown asset {asset_id}")
        return deepcopy(asset)

    def history(self, asset_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._state()["history"].get(asset_id, []))

    def set_temperature_setpoint(self, asset_id: str, value: float) -> dict[str, Any]:
        state = self._state()
        asset = state["assets"].get(asset_id)
        if not asset:
            raise KeyError(f"Unknown asset {asset_id}")
        before = deepcopy(asset)
        asset["setpoint_f"] = float(value)
        asset["temperature_f"] = max(float(value) + 0.4, float(asset["temperature_f"]) - 4.5)
        state["history"].setdefault(asset_id, []).append(
            {"minutes_ago": 0, "temperature_f": asset["temperature_f"], "setpoint_f": value}
        )
        state["updated_at"] = datetime.now(UTC).isoformat()
        self.repository.set_state(self.STATE_KEY, state)
        return {"before": before, "after": deepcopy(asset), "command": "set_temperature_setpoint"}

    def complete_incident_repair(self, asset_id: str) -> dict[str, Any]:
        state = self._state()
        asset = state["assets"].get(asset_id)
        if not asset:
            raise KeyError(f"Unknown asset {asset_id}")
        before = deepcopy(asset)
        asset.update({"cabinet_temperature_f": 84.2, "current_amps": 30.4, "status": "operational"})
        asset.pop("fault", None)
        state["history"].setdefault(asset_id, []).append(
            {"minutes_ago": 0, "cabinet_temperature_f": 84.2, "current_amps": 30.4}
        )
        state["updated_at"] = datetime.now(UTC).isoformat()
        self.repository.set_state(self.STATE_KEY, state)
        return {"before": before, "after": deepcopy(asset), "repair": "feeder connection replaced and torqued"}

    def verify(self, ticket: Ticket) -> dict[str, Any]:
        if self.repository.get_state(f"verification_failure:{ticket.ticket_id}"):
            return {
                "passed": False,
                "summary": "The simulated post-action reading remained outside the stable range.",
                "readings": {},
            }
        if ticket.kind == TicketKind.SERVICE_REQUEST:
            asset = self.telemetry("AHU-ZONE-4B")
            passed = asset["temperature_f"] <= 74.0 and 68 <= asset["setpoint_f"] <= 75
            return {
                "passed": passed,
                "summary": f"Room temperature is {asset['temperature_f']:.1f}°F at a {asset['setpoint_f']:.1f}°F setpoint.",
                "readings": asset,
            }
        if ticket.kind == TicketKind.INCIDENT:
            asset = self.telemetry("ELEC-PNL-7A")
            passed = asset["status"] == "operational" and asset["cabinet_temperature_f"] < 95
            return {
                "passed": passed,
                "summary": f"Panel is {asset['status']} at {asset['cabinet_temperature_f']:.1f}°F and {asset['current_amps']:.1f} A.",
                "readings": asset,
            }
        return {"passed": True, "summary": "The grounded response was delivered.", "readings": {}}

    def set_verification_failure(self, ticket_id: str, enabled: bool) -> None:
        self.repository.set_state(
            f"verification_failure:{ticket_id}",
            {"enabled": True} if enabled else {},
        )

    def inject_simulated_condition(self, condition: str) -> dict[str, Any]:
        """Advance the local building world; AWS replaces this with real IoT telemetry."""
        state = self._state()
        if condition == "comfort_drift":
            asset = state["assets"]["AHU-ZONE-4B"]
            asset.update({"temperature_f": 77.2, "setpoint_f": 72.0, "status": "operational"})
            state["history"]["AHU-ZONE-4B"].append(
                {"minutes_ago": 0, "temperature_f": 77.2, "setpoint_f": 72.0}
            )
        elif condition == "electrical_overheat":
            asset = state["assets"]["ELEC-PNL-7A"]
            asset.update(
                {
                    "cabinet_temperature_f": 126.4,
                    "current_amps": 58.1,
                    "status": "fault",
                    "fault": "heat-damaged feeder connection",
                }
            )
            state["history"]["ELEC-PNL-7A"].append(
                {"minutes_ago": 0, "cabinet_temperature_f": 126.4, "current_amps": 58.1}
            )
        state["updated_at"] = datetime.now(UTC).isoformat()
        self.repository.set_state(self.STATE_KEY, state)
        return {"condition": condition, "updated_at": state["updated_at"]}
