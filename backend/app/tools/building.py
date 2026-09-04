from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
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
    "sensor_overrides": {},
    "active_conditions": {},
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
        state = self.repository.get_state(self.STATE_KEY) or deepcopy(DEFAULT_BUILDING)
        state.setdefault("sensor_overrides", {})
        state.setdefault("active_conditions", {})
        return state

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._state())

    @staticmethod
    def _floor_number(location_id: str) -> int:
        match = re.search(r"-F(\d{2})(?:-|$)", location_id)
        return int(match.group(1)) if match else 1

    @staticmethod
    def _area_name(location_id: str) -> str:
        match = re.search(r"-F\d{2}-(.+)$", location_id)
        segment = match.group(1) if match else location_id.split("-")[-1]
        replacements = {
            "CONF-4B": "Conference 4B",
            "EAST": "East office zone",
            "FITNESS": "Fitness center",
        }
        return replacements.get(segment, segment.replace("_", " ").replace("-", " ").title())

    def condition_for_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        state = self._state()
        condition = state["active_conditions"].get(ticket_id)
        if not condition:
            return None
        sensor = state["sensor_overrides"].get(condition["sensor_id"], {})
        return {**deepcopy(condition), "sensor": deepcopy(sensor)}

    def asset_at(self, location_id: str, asset_type: str | None = None) -> dict[str, Any] | None:
        state = self._state()
        if asset_type == "hvac_zone":
            condition = next(
                (
                    item for item in state["active_conditions"].values()
                    if item["location_id"] == location_id
                    and item["condition"] in {"temperature_high", "temperature_low"}
                ),
                None,
            )
            if condition:
                return deepcopy(state["sensor_overrides"][condition["sensor_id"]])
        assets = state["assets"].values()
        exact = [asset for asset in assets if asset["location_id"] == location_id]
        candidates = exact or list(assets)
        if asset_type:
            candidates = [asset for asset in candidates if asset["type"] == asset_type]
        return deepcopy(candidates[0]) if candidates else None

    def telemetry(self, asset_id: str) -> dict[str, Any]:
        state = self._state()
        asset = state["assets"].get(asset_id) or state["sensor_overrides"].get(asset_id)
        if not asset:
            raise KeyError(f"Unknown asset {asset_id}")
        return deepcopy(asset)

    def history(self, asset_id: str) -> list[dict[str, Any]]:
        state = self._state()
        history = state["history"].get(asset_id)
        if history is not None:
            return deepcopy(history)
        sensor = state["sensor_overrides"].get(asset_id)
        return [deepcopy(sensor)] if sensor else []

    def set_temperature_setpoint(self, asset_id: str, value: float) -> dict[str, Any]:
        state = self._state()
        asset = state["assets"].get(asset_id)
        if not asset and asset_id in state["sensor_overrides"]:
            sensor = state["sensor_overrides"][asset_id]
            before = deepcopy(sensor)
            sensor.update(
                {
                    "value": f"{float(value) + 0.7:.1f}°F",
                    "temperature_f": float(value) + 0.7,
                    "setpoint_f": float(value),
                    "state": "Normal",
                    "status": "operational",
                    "seen": "Live",
                }
            )
            state["updated_at"] = datetime.now(UTC).isoformat()
            self.repository.set_state(self.STATE_KEY, state)
            return {"before": before, "after": deepcopy(sensor), "command": "set_temperature_setpoint"}
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
        if asset_id in state["sensor_overrides"]:
            sensor = state["sensor_overrides"][asset_id]
            before = deepcopy(sensor)
            if sensor.get("type") == "VOC / odor":
                sensor.update({"value": "18 ppb", "voc_ppb": 18.0})
            elif sensor.get("type") == "Cabinet temperature":
                sensor.update({"value": "84.2°F", "cabinet_temperature_f": 84.2, "current_amps": 30.4})
            sensor.update({"state": "Normal", "status": "operational", "seen": "Live"})
            if asset:
                asset.update({"cabinet_temperature_f": 84.2, "current_amps": 30.4, "status": "operational"})
                asset.pop("fault", None)
            state["updated_at"] = datetime.now(UTC).isoformat()
            self.repository.set_state(self.STATE_KEY, state)
            return {"before": before, "after": deepcopy(sensor), "repair": "affected zone inspected and restored"}
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
        active_condition = self.condition_for_ticket(ticket.ticket_id)
        if active_condition:
            sensor = active_condition["sensor"]
            passed = sensor.get("state") == "Normal"
            return {
                "passed": passed,
                "summary": f"{sensor.get('type', 'Sensor')} at {sensor.get('area', ticket.location_id)} is {sensor.get('value', 'stable')} and reporting {sensor.get('state', 'Normal').lower()}.",
                "readings": sensor,
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

    def inject_simulated_condition(
        self,
        condition: str,
        location_id: str = "BLDG-A",
        ticket_id: str | None = None,
    ) -> dict[str, Any]:
        """Advance the local building world; AWS replaces this with real IoT telemetry."""
        state = self._state()
        floor = self._floor_number(location_id)
        area = self._area_name(location_id)
        normalized = "temperature_high" if condition == "comfort_drift" else condition
        sensor: dict[str, Any] | None = None
        if normalized in {"temperature_high", "temperature_low"}:
            value = 77.2 if normalized == "temperature_high" else 61.5
            sensor_id = f"TMP-{floor:02d}-01"
            sensor = {
                "id": sensor_id,
                "asset_id": sensor_id,
                "name": f"Floor {floor} {area} temperature sensor",
                "floor": floor,
                "area": area,
                "type": "Temperature",
                "value": f"{value:.1f}°F",
                "target": "68–75°F",
                "state": "Warning",
                "status": "fault",
                "seen": "Live",
                "temperature_f": value,
                "setpoint_f": 72.0,
                "location_id": location_id,
            }
        elif normalized in {"air_quality", "smoke_or_odor"}:
            value = 165.0 if normalized == "air_quality" else 320.0
            sensor_id = f"VOC-{floor:02d}-01"
            sensor = {
                "id": sensor_id,
                "asset_id": sensor_id,
                "name": f"Floor {floor} {area} air quality sensor",
                "floor": floor,
                "area": area,
                "type": "VOC / odor",
                "value": f"{value:.0f} ppb",
                "target": "< 50 ppb",
                "state": "Critical" if normalized == "smoke_or_odor" else "Warning",
                "status": "fault",
                "seen": "Live",
                "voc_ppb": value,
                "location_id": location_id,
            }
        elif normalized == "electrical_overheat":
            sensor_id = "ELEC-7A" if floor == 7 else f"PWR-{floor:02d}-01"
            sensor = {
                "id": sensor_id,
                "asset_id": sensor_id,
                "name": f"Floor {floor} {area} electrical sensor",
                "floor": floor,
                "area": area,
                "type": "Cabinet temperature",
                "value": "126.4°F",
                "target": "< 95°F",
                "state": "Critical",
                "status": "fault",
                "seen": "Live",
                "cabinet_temperature_f": 126.4,
                "current_amps": 58.1,
                "location_id": location_id,
            }
        if sensor:
            state["sensor_overrides"][sensor["id"]] = sensor
            if ticket_id:
                state["active_conditions"][ticket_id] = {
                    "ticket_id": ticket_id,
                    "sensor_id": sensor["id"],
                    "condition": normalized,
                    "location_id": location_id,
                }
        if normalized == "temperature_high" and floor == 4:
            asset = state["assets"]["AHU-ZONE-4B"]
            asset.update({"temperature_f": 77.2, "setpoint_f": 72.0, "status": "operational"})
            state["history"]["AHU-ZONE-4B"].append(
                {"minutes_ago": 0, "temperature_f": 77.2, "setpoint_f": 72.0}
            )
        elif normalized == "electrical_overheat" and floor == 7:
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
        return {
            "condition": normalized,
            "sensor_id": sensor["id"] if sensor else None,
            "location_id": location_id,
            "updated_at": state["updated_at"],
        }
