from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.agents.ports import AgentRuntime
from backend.app.domain.models import (
    ActionRecord,
    AgentDecision,
    MessageDelivery,
    RiskTier,
    Ticket,
    TicketEvent,
    TicketKind,
    TicketStatus,
    WorkflowJob,
    WorkflowState,
)
from backend.app.messaging.ports import MessageBusPort
from backend.app.domain.policies import ActionPolicy
from backend.app.domain.state_machine import assert_transition
from backend.app.repositories.ports import OperationsRepository
from backend.app.services.action_gateway import ActionGateway
from backend.app.services.events import LocalEventBus
from backend.app.tools.ports import BuildingPort, KnowledgePort, NotificationPort, WorkOrderPort


class WorkflowService:
    """Executes one durable ticket step; portable to SQS/Lambda or EventBridge delivery."""

    def __init__(
        self,
        repository: OperationsRepository,
        agent: AgentRuntime,
        knowledge: KnowledgePort,
        building: BuildingPort,
        notifications: NotificationPort,
        work_orders: WorkOrderPort,
        events: LocalEventBus,
        message_bus: MessageBusPort,
        *,
        agent_analysis_seconds: float = 2.2,
        action_delay_seconds: float = 1.6,
        technician_delay_seconds: float = 12,
        verification_delay_seconds: float = 3,
    ):
        self.repository = repository
        self.agent = agent
        self.knowledge = knowledge
        self.building = building
        self.notifications = notifications
        self.work_orders = work_orders
        self.events = events
        self.message_bus = message_bus
        self.policy = ActionPolicy()
        self.actions = ActionGateway(repository, self.policy)
        self.agent_analysis_seconds = agent_analysis_seconds
        self.action_delay_seconds = action_delay_seconds
        self.technician_delay_seconds = technician_delay_seconds
        self.verification_delay_seconds = verification_delay_seconds

    def _transition(
        self,
        ticket: Ticket,
        target: TicketStatus,
        *,
        waiting: str | None = None,
        wake_at=None,
        persist: bool = True,
    ) -> Ticket:
        assert_transition(ticket.status, target)
        now = datetime.now(UTC)
        ticket.status = target
        ticket.waiting_reason = waiting
        ticket.wake_at = wake_at
        ticket.updated_at = now
        ticket.version += 1
        if target == TicketStatus.RESOLVED:
            ticket.resolved_at = now
        if persist:
            self.repository.save_ticket(ticket)
        return ticket

    def _event(
        self,
        ticket: Ticket,
        event_type: str,
        summary: str,
        *,
        actor: str = "BuildingOps Autopilot",
        payload: dict[str, Any] | None = None,
        key: str,
    ) -> None:
        event = TicketEvent(
            event_id=f"EVT-{ticket.ticket_id}-{key}",
            ticket_id=ticket.ticket_id,
            actor=actor,
            event_type=event_type,
            summary=summary,
            payload=payload or {},
            correlation_id=f"CORR-{ticket.ticket_id}",
            created_at=datetime.now(UTC),
        )
        if self.repository.append_event(event):
            self.events.publish({"type": "ticket.updated", "ticket_id": ticket.ticket_id})

    def process_due(self, *, now: datetime | None = None, limit: int = 10) -> int:
        current = now or datetime.now(UTC)
        self._publish_due_commands(current, limit)
        deliveries = self.message_bus.pull(
            "operations.workflow", now=current, limit=limit
        )
        processed = 0
        for delivery in deliveries:
            job: WorkflowJob | None = None
            try:
                job = WorkflowJob.model_validate(delivery.message.payload["job"])
                job.attempts = delivery.attempts
                self._dispatch(job)
                self._checkpoint(job)
                self.message_bus.acknowledge(delivery)
                processed += 1
            except Exception as exc:
                if self.message_bus.reject(delivery, exc, now=current) and job:
                    self._dead_letter(delivery, job, exc)
        return processed

    def _publish_due_commands(self, current: datetime, limit: int) -> None:
        jobs = self.repository.claim_due_jobs(current, limit)
        for job in jobs:
            try:
                self.message_bus.publish(
                    topic="workflow.commands",
                    message_type=job.job_type,
                    payload={"job": job.model_dump(mode="json")},
                    correlation_id=f"CORR-{job.ticket_id}",
                    idempotency_key=job.job_id,
                    message_id=f"MSG-{job.job_id}",
                    available_at=current,
                )
                self.repository.complete_job(job.job_id)
            except Exception as exc:
                if job.attempts >= 3:
                    self.repository.complete_job(job.job_id)
                else:
                    delay = min(30, 2 ** job.attempts)
                    self.repository.retry_job(
                        job.job_id, str(exc), datetime.now(UTC) + timedelta(seconds=delay)
                    )

    def _checkpoint(self, job: WorkflowJob) -> None:
        ticket = self.repository.get_ticket(job.ticket_id)
        if not ticket:
            return
        if ticket.status == TicketStatus.RESOLVED:
            status = "completed"
        elif ticket.status == TicketStatus.ESCALATED:
            status = "failed"
        elif ticket.status in {
            TicketStatus.NEEDS_APPROVAL,
            TicketStatus.WAITING_TECHNICIAN,
            TicketStatus.WAITING_VERIFICATION,
        }:
            status = "waiting"
        else:
            status = "running"
        self.repository.save_workflow_state(
            WorkflowState(
                workflow_id=f"WF-{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                current_step=str(ticket.status),
                status=status,
                checkpoint={
                    "ticket_status": str(ticket.status),
                    "ticket_version": ticket.version,
                    "message_attempt": job.attempts,
                    "waiting_reason": ticket.waiting_reason,
                    "wake_at": ticket.wake_at.isoformat() if ticket.wake_at else None,
                },
                version=ticket.version,
                updated_at=datetime.now(UTC),
            )
        )

    def _dead_letter(
        self, delivery: MessageDelivery, job: WorkflowJob, error: Exception
    ) -> None:
        ticket = self.repository.get_ticket(job.ticket_id)
        if not ticket or ticket.status in {TicketStatus.RESOLVED, TicketStatus.ESCALATED}:
            return
        if ticket.status == TicketStatus.NEW:
            self._transition(ticket, TicketStatus.TRIAGING)
        self._transition(ticket, TicketStatus.ESCALATED)
        self._event(
            ticket,
            "workflow.dead_lettered",
            f"The workflow stopped safely after {delivery.attempts} delivery attempts: {error}",
            payload={
                "message_id": delivery.message.message_id,
                "job_id": job.job_id,
                "subscription": delivery.subscription,
                "error": str(error),
            },
            key=f"{job.job_id}-DEAD-LETTER",
        )
        self._checkpoint(job)

    def _dispatch(self, job: WorkflowJob) -> None:
        ticket = self.repository.get_ticket(job.ticket_id)
        if not ticket:
            return
        if job.job_type == "advance":
            self._start_triage(ticket)
        elif job.job_type == "agent_decide":
            self._decide(ticket)
        elif job.job_type == "execute_decision":
            self._execute_decision(ticket, job)
        elif job.job_type == "dispatch_incident":
            self._dispatch_incident(ticket)
        elif job.job_type == "technician_complete":
            self._complete_technician(ticket)
        elif job.job_type == "verify":
            self._verify(ticket)
        else:
            raise ValueError(f"Unsupported job type {job.job_type}")

    def _start_triage(self, ticket: Ticket) -> None:
        if ticket.status != TicketStatus.NEW:
            return
        wake = datetime.now(UTC) + timedelta(seconds=self.agent_analysis_seconds)
        self._transition(
            ticket,
            TicketStatus.TRIAGING,
            waiting="The agent is reading the request and checking operational context.",
            wake_at=wake,
            persist=False,
        )
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-AGENT-DECIDE",
                ticket_id=ticket.ticket_id,
                job_type="agent_decide",
                available_at=wake,
            ),
        )
        self._event(
            ticket,
            "agent.started",
            "The agent began triage and is reviewing the request, location, policy, and available operational context.",
            payload={"runtime": self.agent.name, "stage": "analysis"},
            key="AGENT-START",
        )

    def _decide(self, ticket: Ticket) -> None:
        if ticket.status != TicketStatus.TRIAGING:
            return
        knowledge_result = self.knowledge.search(f"{ticket.subject} {ticket.description}")
        building_facts = self.building.investigation_context(ticket)
        primary = building_facts.get("primary_sensor")
        maintenance = building_facts.get("maintenance_history", [])
        if primary:
            maintenance_note = (
                f" {len(maintenance)} relevant maintenance record{'s' if len(maintenance) != 1 else ''} matched."
                if maintenance else " No directly matching maintenance record was found."
            )
            self._event(
                ticket,
                "evidence.correlated",
                f"Correlated the request with {primary['id']} at {primary['value']} ({primary['state']}) and {len(building_facts.get('nearby_sensors', [])) - 1} nearby sensors.{maintenance_note}",
                payload=building_facts,
                key="CONTEXT-CORRELATED",
            )
        context = {
            "eligible_actions": ["answer_enquiry", "inspect_temperature", "investigate_incident", "escalate"],
            "known_locations": [f"BLDG-A-F{floor:02d}" for floor in range(1, 11)],
            "knowledge_result": knowledge_result,
            "building_facts": building_facts,
        }
        decision = self.agent.decide(ticket, context)
        ticket.kind = decision.kind
        ticket.priority = decision.priority
        ticket.safety_flags = decision.safety_flags
        ticket.confidence = decision.confidence
        self._event(
            ticket,
            "agent.decision",
            decision.rationale,
            payload={**decision.model_dump(mode="json"), "runtime": self.agent.name},
            key="AGENT-DECISION",
        )
        self._event(
            ticket,
            "agent.tools_completed",
            (
                f"{self.agent.name} used {len(decision.tool_calls)} trusted tool call"
                f"{'s' if len(decision.tool_calls) != 1 else ''} and cited "
                f"{', '.join(decision.evidence_sensor_ids) if decision.evidence_sensor_ids else 'the building knowledge base'}."
            ),
            payload={
                "runtime": self.agent.name,
                "provider": decision.model_provider,
                "model": decision.model_id,
                "tools": decision.tool_calls,
                "evidence_sensor_ids": decision.evidence_sensor_ids,
                "diagnosis": decision.diagnosis,
            },
            key="AGENT-TOOLS",
        )
        wake = datetime.now(UTC) + timedelta(seconds=self.action_delay_seconds)
        self._transition(
            ticket,
            TicketStatus.WORKING,
            waiting=f"The agent selected {decision.selected_action.replace('_', ' ')} and is preparing the next step.",
            wake_at=wake,
            persist=False,
        )
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-EXECUTE-DECISION",
                ticket_id=ticket.ticket_id,
                job_type="execute_decision",
                payload={
                    "decision": decision.model_dump(mode="json"),
                    "knowledge_result": knowledge_result,
                },
                available_at=wake,
            ),
        )
        self._send_update(ticket, decision.user_update, key="TRIAGE")

    def _execute_decision(self, ticket: Ticket, job: WorkflowJob) -> None:
        if ticket.status != TicketStatus.WORKING:
            return
        decision = AgentDecision.model_validate(job.payload.get("decision", {}))
        selected_action = decision.selected_action
        if selected_action == "answer_enquiry":
            self._answer_enquiry(ticket, job.payload.get("knowledge_result"))
        elif selected_action == "inspect_temperature":
            self._handle_temperature(ticket, decision)
        elif selected_action == "investigate_incident":
            self._investigate_incident(ticket, decision)
        else:
            self._transition(ticket, TicketStatus.ESCALATED)
            rationale = job.payload.get("decision", {}).get("rationale", "No eligible autonomous action was found.")
            self._event(ticket, "ticket.escalated", rationale, key="UNSUPPORTED")

    def _send_update(self, ticket: Ticket, message: str, *, key: str) -> None:
        result = self.notifications.send(ticket, message, "requester", f"MSG-{ticket.ticket_id}-{key}")
        self._event(
            ticket,
            "message.sent",
            message,
            payload=result,
            key=f"MESSAGE-{key}",
        )

    def _answer_enquiry(self, ticket: Ticket, result: dict[str, str] | None) -> None:
        if not result:
            self._transition(ticket, TicketStatus.ESCALATED)
            self._event(ticket, "ticket.escalated", "No authoritative building information matched the request.", key="NO-KNOWLEDGE")
            return
        message = f"{result['answer']} Source: {result['source']}."
        self._send_update(ticket, message, key="ANSWER")
        self._transition(ticket, TicketStatus.RESOLVED)
        self._event(
            ticket,
            "ticket.resolved",
            "The enquiry was answered from an authoritative building source and closed automatically.",
            payload={"source": result["source"], "autonomous": True},
            key="RESOLVED",
        )

    def _handle_temperature(self, ticket: Ticket, decision: AgentDecision) -> None:
        asset = None
        for sensor_id in decision.evidence_sensor_ids:
            candidate = self.building.telemetry(sensor_id)
            if candidate.get("type") == "Temperature":
                asset = candidate
                break
        asset = asset or self.building.asset_at(ticket.location_id, "hvac_zone")
        if not asset:
            self._transition(ticket, TicketStatus.ESCALATED)
            self._event(ticket, "ticket.escalated", "No controllable HVAC zone was found.", key="NO-ASSET")
            return
        before = self.building.telemetry(asset["asset_id"])
        temperature = float(before.get("temperature_f", before.get("numeric_value", 0)))
        setpoint = float(before.get("setpoint_f", 72.0))
        self._event(
            ticket,
            "evidence.collected",
            f"{asset['name']} is {temperature:.1f}°F against a {setpoint:.1f}°F setpoint.",
            payload={"asset": asset, "telemetry": before},
            key="TEMP-EVIDENCE",
        )
        target = 70.0
        policy = self.policy.evaluate("set_temperature_setpoint", {"value": target})
        action = self.actions.execute(
            ticket,
            action_type="set_temperature_setpoint",
            parameters={"asset_id": asset["asset_id"], "value": target},
            before_state=before,
            rationale=policy.reason,
            idempotency_key="SETPOINT",
            operation=lambda: self.building.set_temperature_setpoint(asset["asset_id"], target),
        )
        self._event(
            ticket,
            "action.completed",
            f"Adjusted the approved setpoint from {setpoint:.1f}°F to {target:.1f}°F under policy {policy.rule}.",
            payload=action.model_dump(mode="json"),
            key="SETPOINT-COMPLETE",
        )
        wake = datetime.now(UTC) + timedelta(seconds=self.verification_delay_seconds)
        self._transition(
            ticket,
            TicketStatus.WAITING_VERIFICATION,
            waiting="Watching room temperature stabilize.",
            wake_at=wake,
            persist=False,
        )
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-VERIFY",
                ticket_id=ticket.ticket_id,
                job_type="verify",
                available_at=wake,
            )
        )
        self._send_update(ticket, "I made a policy-safe temperature adjustment and am verifying the room response before closing the ticket.", key="VERIFY-WAIT")

    def _investigate_incident(self, ticket: Ticket, decision: AgentDecision) -> None:
        correlated = self.building.condition_for_ticket(ticket.ticket_id)
        asset = correlated["sensor"] if correlated else None
        if not asset and decision.evidence_sensor_ids:
            evidence = [self.building.telemetry(sensor_id) for sensor_id in decision.evidence_sensor_ids]
            asset = next((item for item in evidence if item.get("state") in {"Warning", "Critical"}), evidence[0])
        asset = asset or self.building.asset_at(ticket.location_id, "electrical_panel")
        if not asset:
            self._transition(ticket, TicketStatus.ESCALATED)
            self._event(ticket, "ticket.escalated", "No correlated building sensor or candidate asset was found.", key="NO-BUILDING-ASSET")
            return
        telemetry = self.building.telemetry(asset["asset_id"])
        history = self.building.history(asset["asset_id"])
        is_air_quality = telemetry.get("type") in {"VOC / odor", "CO₂", "Humidity"}
        trade = "indoor_air_quality" if is_air_quality else "electrical"
        action_type = "dispatch_safety_technician" if is_air_quality else "dispatch_electrical_technician"
        procedure = (
            "Inspect the reported odor zone, test air quality, isolate the source, ventilate if safe, and document clearance readings."
            if is_air_quality
            else "Inspect and repair the suspected overheated electrical connection; complete a thermal safety check."
        )
        evidence_summary = (
            f"The correlated {telemetry.get('type', 'air quality')} sensor at {telemetry.get('area', ticket.location_id)} reached {telemetry.get('value', 'an alarm state')}."
            if is_air_quality
            else f"The correlated electrical sensor reached {telemetry.get('cabinet_temperature_f', 126.4):.1f}°F and {telemetry.get('current_amps', 58.1):.1f} A while reporting a fault."
        )
        self._event(
            ticket,
            "evidence.collected",
            evidence_summary,
            payload={"asset": asset, "telemetry": telemetry, "history": history},
            key="INCIDENT-EVIDENCE",
        )
        policy = self.policy.evaluate(action_type, {"priority": "high"})
        action = ActionRecord(
            action_id=f"ACT-{ticket.ticket_id}-DISPATCH",
            ticket_id=ticket.ticket_id,
            action_type=action_type,
            risk_tier=policy.tier,
            policy_rule=policy.rule,
            status="proposed",
            before_state=telemetry,
            requested={"asset_id": asset["asset_id"], "trade": trade, "priority": "high", "procedure": procedure},
            rationale="Correlated occupant and sensor evidence supports qualified inspection; the agent will not perform hazardous physical work.",
            idempotency_key=f"DISPATCH-{ticket.ticket_id}",
            created_at=datetime.now(UTC),
        )
        self.repository.save_action(action)
        self._transition(ticket, TicketStatus.NEEDS_APPROVAL, waiting="Facility manager approval is required for urgent technician dispatch.")
        self._event(
            ticket,
            "approval.requested",
            f"Approve urgent {trade.replace('_', ' ')} technician dispatch. The agent will not perform hazardous physical work.",
            payload=action.model_dump(mode="json"),
            key="APPROVAL-REQUEST",
        )

    def _dispatch_incident(self, ticket: Ticket) -> None:
        if ticket.status != TicketStatus.WORKING:
            return
        due = datetime.now(UTC) + timedelta(seconds=self.technician_delay_seconds)
        action = self.repository.get_action(f"ACT-{ticket.ticket_id}-DISPATCH")
        requested = action.requested if action else {}
        order = self.work_orders.create(
            ticket,
            asset_id=str(requested.get("asset_id", "ELEC-PNL-7A")),
            trade=str(requested.get("trade", "electrical")),
            procedure=str(requested.get("procedure", "Inspect the affected system and document safe restoration.")),
            due_at=due,
            idempotency_key=f"WO-{ticket.ticket_id}",
        )
        if action:
            action.status = "completed"
            action.after_state = {"work_order": order.model_dump(mode="json")}
            action.completed_at = datetime.now(UTC)
            self.repository.save_action(action)
        self._event(
            ticket,
            "work_order.created",
            f"Created {order.work_order_id} and assigned {order.technician}; scheduled completion is in {self.technician_delay_seconds:g} seconds.",
            payload=order.model_dump(mode="json"),
            key="WORK-ORDER",
        )
        self._send_update(ticket, f"A qualified {order.trade.replace('_', ' ')} technician has been dispatched under {order.work_order_id}. I’ll keep this ticket updated while the work is underway.", key="DISPATCHED")
        self._transition(
            ticket,
            TicketStatus.WAITING_TECHNICIAN,
            waiting=f"{order.technician} is completing {order.work_order_id}.",
            wake_at=due,
            persist=False,
        )
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-TECHNICIAN",
                ticket_id=ticket.ticket_id,
                job_type="technician_complete",
                available_at=due,
            )
        )

    def _complete_technician(self, ticket: Ticket) -> None:
        if ticket.status != TicketStatus.WAITING_TECHNICIAN:
            return
        existing_order = self.repository.get_work_order_for_ticket(ticket.ticket_id)
        trade_label = existing_order.trade.replace("_", " ") if existing_order else "facilities"
        order = self.work_orders.complete(
            ticket.ticket_id,
            f"Inspected the affected zone, corrected the {trade_label} condition, and documented stable clearance readings.",
        )
        repair = self.building.complete_incident_repair(order.asset_id)
        self._event(
            ticket,
            "work_order.completed",
            f"{order.technician} completed {order.work_order_id}: {order.completion_notes}",
            actor=order.technician,
            payload={"work_order": order.model_dump(mode="json"), "repair": repair},
            key="TECHNICIAN-COMPLETE",
        )
        wake = datetime.now(UTC) + timedelta(seconds=self.verification_delay_seconds)
        self._transition(
            ticket,
            TicketStatus.WAITING_VERIFICATION,
            waiting="Independently verifying the correlated building readings after repair.",
            wake_at=wake,
            persist=False,
        )
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-VERIFY",
                ticket_id=ticket.ticket_id,
                job_type="verify",
                available_at=wake,
            )
        )
        self._send_update(ticket, "The technician completed the repair. I’m checking the live readings before I close the incident.", key="REPAIR-DONE")

    def _verify(self, ticket: Ticket) -> None:
        if ticket.status != TicketStatus.WAITING_VERIFICATION:
            return
        result = self.building.verify(ticket)
        if result["passed"]:
            self._event(ticket, "verification.passed", result["summary"], payload=result, key="VERIFIED")
            self._transition(ticket, TicketStatus.RESOLVED)
            self._send_update(ticket, "The outcome is stable and independently verified. I’ve closed the ticket.", key="CLOSED")
            self._event(ticket, "ticket.resolved", "Closed only after independent outcome verification.", payload={"verified": True}, key="RESOLVED")
        else:
            self._event(ticket, "verification.failed", result["summary"], payload=result, key="VERIFY-FAILED")
            self._transition(ticket, TicketStatus.ESCALATED)
            self._send_update(ticket, "The issue did not remain stable after the attempted resolution, so I escalated it instead of closing it.", key="ESCALATED")
