from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
from typing import Any

from backend.app.domain.models import Ticket, TicketKind
from backend.app.repositories.ports import OperationsRepository


FLOORS: tuple[dict[str, Any], ...] = (
    {"number": 1, "name": "Welcome & Amenities", "occupancy": 41, "capacity": 80},
    {"number": 2, "name": "People & Operations", "occupancy": 31, "capacity": 52},
    {"number": 3, "name": "Sales & Marketing", "occupancy": 42, "capacity": 66},
    {"number": 4, "name": "Client Services", "occupancy": 34, "capacity": 56},
    {"number": 5, "name": "Product & Design", "occupancy": 43, "capacity": 64},
    {"number": 6, "name": "Engineering West", "occupancy": 54, "capacity": 70},
    {"number": 7, "name": "Engineering East", "occupancy": 46, "capacity": 62},
    {"number": 8, "name": "Product Studio", "occupancy": 51, "capacity": 68},
    {"number": 9, "name": "Finance & Legal", "occupancy": 39, "capacity": 58},
    {"number": 10, "name": "Executive & Board", "occupancy": 27, "capacity": 42},
)


def _sensor(
    sensor_id: str,
    floor: dict[str, Any],
    sensor_type: str,
    numeric_value: float,
    unit: str,
    target: str,
) -> dict[str, Any]:
    value = f"{numeric_value:.1f}{unit}" if sensor_type == "Temperature" else f"{numeric_value:.0f} {unit}".strip()
    if sensor_type == "Humidity":
        value = f"{numeric_value:.0f}%"
    return {
        "id": sensor_id,
        "asset_id": sensor_id,
        "name": f"Floor {floor['number']} {sensor_type.lower()} sensor",
        "floor": floor["number"],
        "area": floor["name"],
        "type": sensor_type,
        "numeric_value": numeric_value,
        "unit": unit,
        "value": value,
        "target": target,
        "state": "Normal",
        "status": "operational",
        "seen": "Live",
        "location_id": f"BLDG-A-F{floor['number']:02d}",
        "updated_at": None,
    }


def _sensor_inventory() -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for floor in FLOORS:
        number = int(floor["number"])
        pad = f"{number:02d}"
        records = (
            _sensor(f"TMP-{pad}-01", floor, "Temperature", 72.7 if number == 4 else 69.8 + (number % 4) * 0.7, "°F", "68–75°F"),
            _sensor(f"AIR-{pad}-01", floor, "CO₂", 450 + number * 31, "ppm", "< 1,000 ppm"),
            _sensor(f"HUM-{pad}-01", floor, "Humidity", 39 + (number % 5), "%", "30–60%"),
            _sensor(f"VOC-{pad}-01", floor, "VOC / odor", 16 + number, "ppb", "< 50 ppb"),
            _sensor(f"OCC-{pad}-01", floor, "Occupancy", floor["occupancy"], "people", f"≤ {floor['capacity']}"),
            _sensor(f"PWR-{pad}-01", floor, "Electrical load", 78 + number * 4, "kW", "< 145 kW"),
        )
        for record in records:
            inventory[record["id"]] = record
    panel = inventory.pop("PWR-07-01")
    panel.update(
        {
            "id": "ELEC-7A",
            "asset_id": "ELEC-7A",
            "name": "Floor 7 Lighting Distribution Panel",
            "area": "Floor 7 east panel",
            "type": "Cabinet temperature",
            "numeric_value": 84.2,
            "unit": "°F",
            "value": "84.2°F",
            "target": "< 95°F",
            "location_id": "BLDG-A-F07-EAST",
            "cabinet_temperature_f": 84.2,
            "current_amps": 30.4,
        }
    )
    inventory["ELEC-7A"] = panel
    return inventory


def _default_building() -> dict[str, Any]:
    inventory = _sensor_inventory()
    return {
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
        "sensors": inventory,
        "sensor_history": {
            sensor_id: [
                {
                    "recorded_at": None,
                    "numeric_value": sensor["numeric_value"],
                    "value": sensor["value"],
                    "state": sensor["state"],
                }
            ]
            for sensor_id, sensor in inventory.items()
        },
        "maintenance_history": [
            {"date": "2026-08-21", "floor": 5, "asset_type": "VOC / odor", "asset_id": "EXH-05-PANTRY", "summary": "Pantry exhaust filter replaced after intermittent cooking-odor reports.", "outcome": "Airflow restored and clearance reading documented."},
            {"date": "2026-08-12", "floor": 4, "asset_type": "Temperature", "asset_id": "AHU-ZONE-4B", "summary": "Conference 4B VAV damper recalibrated after warm-room report.", "outcome": "Damper response returned to specification."},
            {"date": "2026-07-29", "floor": 7, "asset_type": "Cabinet temperature", "asset_id": "ELEC-PNL-7A", "summary": "Annual thermal inspection completed on Floor 7 lighting panel.", "outcome": "No hotspot observed at inspection time."},
            {"date": "2026-07-11", "floor": 6, "asset_type": "VOC / odor", "asset_id": "AHU-06", "summary": "Outside-air damper actuator serviced following elevated CO₂ trend.", "outcome": "Ventilation trend normalized."},
        ],
        "sensor_overrides": {},
        "active_conditions": {},
        "heartbeat_sequence": 0,
        "last_sensor_tick": None,
        "updated_at": None,
    }


DEFAULT_BUILDING = _default_building()


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
        state.setdefault("sensors", deepcopy(DEFAULT_BUILDING["sensors"]))
        state.setdefault("sensor_history", deepcopy(DEFAULT_BUILDING["sensor_history"]))
        state.setdefault("maintenance_history", deepcopy(DEFAULT_BUILDING["maintenance_history"]))
        state.setdefault("heartbeat_sequence", 0)
        state.setdefault("last_sensor_tick", None)
        for sensor_id, sensor in DEFAULT_BUILDING["sensors"].items():
            state["sensors"].setdefault(sensor_id, deepcopy(sensor))
            state["sensor_history"].setdefault(sensor_id, deepcopy(DEFAULT_BUILDING["sensor_history"][sensor_id]))
        for sensor_id, override in state["sensor_overrides"].items():
            state["sensors"][sensor_id] = {**state["sensors"].get(sensor_id, {}), **override}
        return state

    def snapshot(self) -> dict[str, Any]:
        state = self._state()
        values = list(state["sensors"].values())
        state["health"] = {
            "total": len(values),
            "normal": sum(sensor.get("state") == "Normal" for sensor in values),
            "warning": sum(sensor.get("state") == "Warning" for sensor in values),
            "critical": sum(sensor.get("state") == "Critical" for sensor in values),
            "monitoring": "autonomous",
        }
        return deepcopy(state)

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
        sensor = state["sensors"].get(condition["sensor_id"], {})
        return {**deepcopy(condition), "sensor": deepcopy(sensor)}

    def investigation_context(self, ticket: Ticket) -> dict[str, Any]:
        """Fuse live telemetry, trends and maintenance history for one ticket."""
        state = self._state()
        floor = self._floor_number(ticket.location_id)
        correlated = self.condition_for_ticket(ticket.ticket_id)
        floor_sensors = [
            deepcopy(sensor)
            for sensor in state["sensors"].values()
            if sensor.get("floor") == floor
        ]
        primary = correlated["sensor"] if correlated else next(
            (sensor for sensor in floor_sensors if sensor.get("state") != "Normal"),
            None,
        )
        text = f"{ticket.subject} {ticket.description}".lower()
        if primary is None:
            preferred = "Temperature" if any(word in text for word in ("warm", "hot", "cold", "temperature")) else None
            primary = next((sensor for sensor in floor_sensors if sensor.get("type") == preferred), None)
        history = state["sensor_history"].get(primary["id"], [])[-12:] if primary else []
        maintenance = [
            deepcopy(item)
            for item in state["maintenance_history"]
            if item.get("floor") == floor
            and (not primary or item.get("asset_type") == primary.get("type"))
        ]
        return {
            "location_id": ticket.location_id,
            "floor": floor,
            "correlation": "ticket-linked condition" if correlated else "location and symptom match",
            "primary_sensor": deepcopy(primary),
            "nearby_sensors": floor_sensors,
            "trend": deepcopy(history),
            "maintenance_history": maintenance,
            "sources": ["occupant request", "live BMS telemetry", "rolling sensor history", "maintenance records"],
        }

    def advance_sensors(self, now: datetime | None = None) -> dict[str, Any]:
        """Advance every healthy device while retaining a bounded rolling history."""
        current = now or datetime.now(UTC)
        state = self._state()
        last = datetime.fromisoformat(state["last_sensor_tick"]) if state.get("last_sensor_tick") else None
        if last and (current - last).total_seconds() < 2:
            return self.snapshot()["health"]
        sequence = int(state.get("heartbeat_sequence", 0)) + 1
        active_ids = {condition["sensor_id"] for condition in state["active_conditions"].values()}
        for sensor_id, sensor in state["sensors"].items():
            if sensor_id in active_ids or sensor.get("state") != "Normal":
                continue
            base = float(DEFAULT_BUILDING["sensors"].get(sensor_id, sensor).get("numeric_value", sensor.get("numeric_value", 0)))
            drift = (((sequence + int(sensor.get("floor", 0)) * 3) % 7) - 3) / 10
            sensor_type = sensor.get("type")
            scale = 1.0 if sensor_type in {"Temperature", "Humidity", "Cabinet temperature"} else 4.0
            if sensor_type == "Occupancy":
                scale = 2.0
            numeric = max(0, base + drift * scale)
            sensor["numeric_value"] = round(numeric, 1)
            sensor["value"] = self._format_sensor_value(sensor)
            sensor["seen"] = "Live"
            sensor["updated_at"] = current.isoformat()
            history = state["sensor_history"].setdefault(sensor_id, [])
            history.append({"recorded_at": current.isoformat(), "numeric_value": sensor["numeric_value"], "value": sensor["value"], "state": sensor["state"]})
            del history[:-24]
        state["heartbeat_sequence"] = sequence
        state["last_sensor_tick"] = current.isoformat()
        state["updated_at"] = current.isoformat()
        self.repository.set_state(self.STATE_KEY, state)
        return self.snapshot()["health"]

    @staticmethod
    def _format_sensor_value(sensor: dict[str, Any]) -> str:
        value = float(sensor.get("numeric_value", 0))
        sensor_type = sensor.get("type")
        if sensor_type in {"Temperature", "Cabinet temperature"}:
            return f"{value:.1f}°F"
        if sensor_type == "Humidity":
            return f"{value:.0f}%"
        return f"{value:.0f} {sensor.get('unit', '')}".strip()

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
        asset = state["assets"].get(asset_id) or state["sensors"].get(asset_id)
        if not asset:
            raise KeyError(f"Unknown asset {asset_id}")
        return deepcopy(asset)

    def history(self, asset_id: str) -> list[dict[str, Any]]:
        state = self._state()
        history = state["history"].get(asset_id)
        if history is not None:
            return deepcopy(history)
        sensor_history = state["sensor_history"].get(asset_id)
        if sensor_history is not None:
            return deepcopy(sensor_history)
        sensor = state["sensors"].get(asset_id)
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
                    "numeric_value": float(value) + 0.7,
                }
            )
            state["sensors"][asset_id] = deepcopy(sensor)
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
            sensor["numeric_value"] = float(sensor.get("voc_ppb", sensor.get("cabinet_temperature_f", 0)))
            state["sensors"][asset_id] = deepcopy(sensor)
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
                "numeric_value": value,
                "unit": "°F",
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
                "numeric_value": value,
                "unit": "ppb",
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
                "numeric_value": 126.4,
                "unit": "°F",
                "cabinet_temperature_f": 126.4,
                "current_amps": 58.1,
                "location_id": location_id,
            }
        if sensor:
            state["sensor_overrides"][sensor["id"]] = sensor
            state["sensors"][sensor["id"]] = deepcopy(sensor)
            state["sensor_history"].setdefault(sensor["id"], []).append(
                {"recorded_at": datetime.now(UTC).isoformat(), "numeric_value": sensor.get("numeric_value", sensor.get("temperature_f", sensor.get("voc_ppb", sensor.get("cabinet_temperature_f", 0)))), "value": sensor["value"], "state": sensor["state"]}
            )
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
