from __future__ import annotations

from typing import Any

from backend.app.domain.models import SpecialistReport, Ticket


SPECIALIST_ROLES = (
    "Intake & Safety Agent",
    "Building Context Agent",
    "Sensor Intelligence Agent",
    "Maintenance Intelligence Agent",
    "Resident Knowledge Agent",
    "Verification Agent",
)
COORDINATOR_ROLE = "Operations Coordinator"


def roles_for(ticket: Ticket, context: dict[str, Any]) -> list[str]:
    text = f"{ticket.subject} {ticket.description}".lower()
    sensors = context.get("building_facts", {}).get("nearby_sensors", [])
    operational = any(sensor.get("state") in {"Warning", "Critical"} for sensor in sensors) or any(
        term in text
        for term in (
            "hot", "warm", "cold", "temperature", "smell", "odor", "smoke",
            "fume", "flicker", "electric", "spark", "stuffy", "air quality",
        )
    )
    roles = ["Intake & Safety Agent", "Building Context Agent"]
    if operational:
        roles.extend(["Sensor Intelligence Agent", "Maintenance Intelligence Agent"])
    if context.get("knowledge_result") and not operational:
        roles.append("Resident Knowledge Agent")
    return roles


def scoped_context(role: str, ticket: Ticket, context: dict[str, Any]) -> dict[str, Any]:
    facts = context.get("building_facts", {})
    if role == "Intake & Safety Agent":
        return {
            "ticket": ticket.model_dump(mode="json"),
            "eligible_actions": context.get("eligible_actions", []),
        }
    if role == "Building Context Agent":
        return {
            "location_id": ticket.location_id,
            "floor": facts.get("floor"),
            "correlation": facts.get("correlation"),
            "sensor_inventory": [
                {key: sensor.get(key) for key in ("id", "name", "type", "area", "location_id")}
                for sensor in facts.get("nearby_sensors", [])
            ],
            "sources": facts.get("sources", []),
        }
    if role == "Sensor Intelligence Agent":
        return {
            "primary_sensor": facts.get("primary_sensor"),
            "live_sensors": facts.get("nearby_sensors", []),
            "sensor_histories": facts.get("sensor_histories", {}),
        }
    if role == "Maintenance Intelligence Agent":
        return {"maintenance_history": facts.get("maintenance_history", [])}
    if role == "Verification Agent":
        return {
            "ticket_id": ticket.ticket_id,
            "expected_outcome": context.get("expected_outcome"),
            "verification_result": context.get("verification_result"),
            "live_sensors": facts.get("nearby_sensors", []),
            "sensor_histories": facts.get("sensor_histories", {}),
        }
    return {"knowledge_result": context.get("knowledge_result")}


def deterministic_report(role: str, ticket: Ticket, context: dict[str, Any]) -> SpecialistReport:
    facts = context.get("building_facts", {})
    sensors = facts.get("nearby_sensors", [])
    abnormal = [sensor for sensor in sensors if sensor.get("state") in {"Warning", "Critical"}]
    primary = facts.get("primary_sensor") or (abnormal[0] if abnormal else None)
    maintenance = facts.get("maintenance_history", [])
    knowledge = context.get("knowledge_result")
    text = f"{ticket.subject} {ticket.description}".lower()
    safety_terms = [term for term in ("burning", "smoke", "fume", "spark", "trapped", "fire") if term in text]
    if role == "Intake & Safety Agent":
        summary = (
            f"Safety language detected ({', '.join(safety_terms)}); qualified handling is required."
            if safety_terms
            else "No explicit life-safety phrase was found in the resident message."
        )
        findings = safety_terms or ["no explicit life-safety phrase"]
        evidence_ids: list[str] = []
        confidence = 0.98
    elif role == "Building Context Agent":
        summary = f"Resolved {ticket.location_id} to Floor {facts.get('floor', 'unknown')} with {len(sensors)} registered sensors."
        findings = [str(facts.get("correlation", "location match")), f"{len(sensors)} sensors in scope"]
        evidence_ids = []
        confidence = 0.99 if sensors else 0.55
    elif role == "Sensor Intelligence Agent":
        evidence_ids = []
        if primary and primary.get("id"):
            evidence_ids.append(str(primary["id"]))
        evidence_ids.extend(
            str(sensor["id"])
            for sensor in abnormal
            if sensor.get("id") and str(sensor["id"]) not in evidence_ids
        )
        summary = (
            "Correlated " + ", ".join(f"{sensor['id']} {sensor.get('value')} ({str(sensor.get('state')).lower()})" for sensor in abnormal)
            if abnormal
            else f"No alarm is active; {primary.get('id') if primary else 'the location sensors'} provides the nearest available evidence."
        )
        findings = [summary]
        confidence = 0.98 if abnormal else 0.72
    elif role == "Maintenance Intelligence Agent":
        summary = f"Found {len(maintenance)} relevant maintenance record{'s' if len(maintenance) != 1 else ''} for this floor and sensor domain."
        findings = [str(item.get("summary")) for item in maintenance] or ["no matching maintenance record"]
        evidence_ids = []
        confidence = 0.9 if maintenance else 0.65
    elif role == "Verification Agent":
        verification = context.get("verification_result") or {}
        raw_readings = verification.get("readings") or []
        readings = [raw_readings] if isinstance(raw_readings, dict) else raw_readings
        evidence_ids = [str(item["sensor_id"]) for item in readings if item.get("sensor_id")]
        evidence_ids.extend(
            str(item["id"])
            for item in readings
            if item.get("id") and str(item["id"]) not in evidence_ids
        )
        passed = bool(verification.get("passed"))
        summary = str(verification.get("summary") or "No verification result was available.")
        findings = [summary, f"Outcome {'passed' if passed else 'requires escalation'}"]
        confidence = 0.99 if verification else 0.4
    else:
        summary = (
            f"Authoritative building knowledge matched {knowledge.get('source')}."
            if knowledge
            else "No authoritative knowledge record matched the request."
        )
        findings = [str(knowledge.get("answer"))] if knowledge else ["no knowledge match"]
        evidence_ids = []
        confidence = 0.98 if knowledge else 0.4
    return SpecialistReport(
        role=role,
        objective=f"Provide bounded evidence to the {COORDINATOR_ROLE}.",
        summary=summary,
        findings=findings,
        evidence_sensor_ids=evidence_ids,
        confidence=confidence,
        tool_calls=[f"{role.lower().replace(' & ', '_and_').replace(' ', '_')}.read_context"],
        model_provider="fixture",
        model_id="rules-v1",
    )


def deterministic_reports(ticket: Ticket, context: dict[str, Any]) -> list[SpecialistReport]:
    return [deterministic_report(role, ticket, context) for role in roles_for(ticket, context)]
