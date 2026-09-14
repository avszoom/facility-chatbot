from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.agents.ports import AgentRuntime
from backend.app.domain.models import (
    ActionRecord,
    AgentDecision,
    CoordinatorDirective,
    MessageDelivery,
    RiskTier,
    Ticket,
    TicketEvent,
    TicketKind,
    TicketStatus,
    SpecialistReport,
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
        existing = self.repository.get_workflow_state(ticket.ticket_id)
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
        current_step = str(ticket.status)
        if existing and status == "running" and existing.current_step.startswith(("coordinator", "specialist")):
            current_step = existing.current_step
        checkpoint = dict(existing.checkpoint) if existing else {}
        checkpoint.update(
            {
                "ticket_status": str(ticket.status),
                "ticket_version": ticket.version,
                "message_attempt": job.attempts,
                "waiting_reason": ticket.waiting_reason,
                "wake_at": ticket.wake_at.isoformat() if ticket.wake_at else None,
            }
        )
        self.repository.save_workflow_state(
            WorkflowState(
                workflow_id=f"WF-{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                current_step=current_step,
                status=status,
                checkpoint=checkpoint,
                version=ticket.version,
                updated_at=datetime.now(UTC),
            )
        )

    def _save_loop_state(
        self,
        ticket: Ticket,
        *,
        current_step: str,
        iteration: int,
        phase: str,
        reports: list[SpecialistReport],
        active_agent: str,
        objective: str,
        next_job: str | None,
    ) -> None:
        self.repository.save_workflow_state(
            WorkflowState(
                workflow_id=f"WF-{ticket.ticket_id}",
                ticket_id=ticket.ticket_id,
                current_step=current_step,
                status="running",
                checkpoint={
                    "ticket_status": str(ticket.status),
                    "ticket_version": ticket.version,
                    "loop_iteration": iteration,
                    "phase": phase,
                    "active_agent": active_agent,
                    "objective": objective,
                    "completed_specialists": [report.role for report in reports],
                    "evidence_sensor_ids": list(dict.fromkeys(
                        sensor_id for report in reports for sensor_id in report.evidence_sensor_ids
                    )),
                    "next_job": next_job,
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
        elif job.job_type in {"agent_decide", "coordinator_step"}:
            self._coordinate(ticket, job)
        elif job.job_type == "specialist_step":
            self._run_specialist(ticket, job)
        elif job.job_type == "execute_decision":
            self._execute_decision(ticket, job)
        elif job.job_type == "dispatch_incident":
            self._dispatch_incident(ticket)
        elif job.job_type == "technician_complete":
            self._complete_technician(ticket)
        elif job.job_type == "verify":  # legacy jobs from an earlier local build
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
            waiting="The Operations Coordinator is reviewing the request and choosing the first specialist.",
            wake_at=wake,
            persist=False,
        )
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=f"JOB-{ticket.ticket_id}-COORDINATOR-1",
                ticket_id=ticket.ticket_id,
                job_type="coordinator_step",
                payload={"iteration": 1, "phase": "investigation", "reports": []},
                available_at=wake,
            ),
        )
        self._event(
            ticket,
            "coordinator.started",
            "The Operations Coordinator accepted the ticket and will select one bounded next step at a time.",
            actor=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            payload={"runtime": self.agent.name, "stage": "coordination", "iteration": 1},
            key="AGENT-START",
        )

    def _context(self, ticket: Ticket, phase: str) -> dict[str, Any]:
        knowledge_result = self.knowledge.search(f"{ticket.subject} {ticket.description}")
        building_facts = self.building.investigation_context(ticket)
        context: dict[str, Any] = {
            "phase": phase,
            "eligible_actions": ["answer_enquiry", "inspect_temperature", "investigate_incident", "escalate"],
            "known_locations": [f"BLDG-A-F{floor:02d}" for floor in range(1, 11)],
            "knowledge_result": knowledge_result,
            "building_facts": building_facts,
        }
        if phase == "verification":
            context["expected_outcome"] = "Fresh evidence must confirm the requested outcome before closure."
            context["verification_result"] = self.building.verify(ticket)
        if phase == "knowledge_delivery":
            context["phase_outcome"] = {
                "authoritative_source": knowledge_result.get("source") if knowledge_result else None,
                "answer_delivered": any(
                    event.event_type == "message.sent" and event.event_id.endswith("MESSAGE-ANSWER")
                    for event in self.repository.list_events(ticket.ticket_id)
                ),
            }
        return context

    def _correlate_once(self, ticket: Ticket, building_facts: dict[str, Any]) -> None:
        primary = building_facts.get("primary_sensor")
        if primary:
            maintenance = building_facts.get("maintenance_history", [])
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

    @staticmethod
    def _reports(job: WorkflowJob) -> list[SpecialistReport]:
        return [SpecialistReport.model_validate(item) for item in job.payload.get("reports", [])]

    def _coordinate(self, ticket: Ticket, job: WorkflowJob) -> None:
        if ticket.status not in {TicketStatus.TRIAGING, TicketStatus.WORKING, TicketStatus.WAITING_VERIFICATION}:
            return
        phase = str(job.payload.get("phase", "investigation"))
        iteration = int(job.payload.get("iteration", 1))
        reports = self._reports(job)
        context = self._context(ticket, phase)
        if phase == "investigation":
            self._correlate_once(ticket, context["building_facts"])
        directive = self.agent.coordinate(ticket, context, reports, iteration)
        if directive.action == "delegate" and directive.specialist_role:
            self._delegate_specialist(ticket, reports, directive, phase)
            return
        if directive.action == "execute" and directive.decision:
            self._accept_decision(ticket, directive.decision, context.get("knowledge_result"), iteration)
            return
        if directive.action == "verify" and phase == "verification":
            self._event(
                ticket,
                "coordinator.verification_requested",
                directive.rationale,
                actor=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
                payload=directive.model_dump(mode="json"),
                key=f"COORDINATOR-{iteration}-VERIFY",
            )
            self._verify(ticket)
            return
        if directive.action == "complete" and phase == "knowledge_delivery":
            outcome = context.get("phase_outcome") or {}
            if not outcome.get("authoritative_source") or not outcome.get("answer_delivered"):
                raise RuntimeError("Knowledge completion requires an authoritative source and delivered answer")
            self._event(
                ticket,
                "coordinator.completion_requested",
                directive.rationale,
                actor=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
                payload=directive.model_dump(mode="json"),
                key=f"COORDINATOR-{iteration}-COMPLETE",
            )
            self._transition(ticket, TicketStatus.RESOLVED)
            self._event(
                ticket,
                "ticket.resolved",
                "The authoritative response was delivered and the domain completion check passed.",
                payload={"source": outcome["authoritative_source"], "autonomous": True},
                key="RESOLVED",
            )
            return
        self._transition(ticket, TicketStatus.ESCALATED)
        self._event(
            ticket,
            "ticket.escalated",
            directive.rationale,
            actor=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            payload=directive.model_dump(mode="json"),
            key=f"COORDINATOR-{iteration}-ESCALATED",
        )

    def _delegate_specialist(
        self,
        ticket: Ticket,
        reports: list[SpecialistReport],
        directive: CoordinatorDirective,
        phase: str,
    ) -> None:
        role = str(directive.specialist_role)
        role_slug = role.upper().replace(" & ", "-").replace(" ", "-")
        next_job_id = f"JOB-{ticket.ticket_id}-SPECIALIST-{directive.iteration}-{role_slug}"
        self._event(
            ticket,
            "coordinator.delegated",
            directive.rationale,
            actor=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            payload=directive.model_dump(mode="json"),
            key=f"COORDINATOR-{directive.iteration}-DELEGATE",
        )
        ticket.waiting_reason = f"{role} is working on: {directive.objective}"
        ticket.updated_at = datetime.now(UTC)
        ticket.version += 1
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=next_job_id,
                ticket_id=ticket.ticket_id,
                job_type="specialist_step",
                payload={
                    "iteration": directive.iteration,
                    "phase": phase,
                    "role": role,
                    "objective": directive.objective,
                    "reports": [report.model_dump(mode="json") for report in reports],
                },
                available_at=datetime.now(UTC),
            ),
        )
        self._save_loop_state(
            ticket,
            current_step=f"specialist:{role}",
            iteration=directive.iteration,
            phase=phase,
            reports=reports,
            active_agent=role,
            objective=directive.objective,
            next_job=next_job_id,
        )

    def _run_specialist(self, ticket: Ticket, job: WorkflowJob) -> None:
        if ticket.status not in {TicketStatus.TRIAGING, TicketStatus.WORKING, TicketStatus.WAITING_VERIFICATION}:
            return
        phase = str(job.payload.get("phase", "investigation"))
        iteration = int(job.payload.get("iteration", 1))
        role = str(job.payload["role"])
        reports = self._reports(job)
        if role in {report.role for report in reports}:
            raise RuntimeError(f"Coordinator attempted to repeat completed specialist {role}")
        context = self._context(ticket, phase)
        report = self.agent.run_specialist(role, ticket, context)
        reports.append(report)
        findings = "; ".join(report.findings[:2]) if report.findings else report.summary
        self._event(
            ticket,
            "specialist.completed",
            findings,
            actor=report.role,
            payload={**report.model_dump(mode="json"), "iteration": iteration, "phase": phase},
            key=f"SPECIALIST-{iteration}-{role.upper().replace(' & ', '-').replace(' ', '-')}",
        )
        next_iteration = iteration + 1
        next_job_id = f"JOB-{ticket.ticket_id}-COORDINATOR-{phase.upper()}-{next_iteration}"
        ticket.waiting_reason = f"The Operations Coordinator is reviewing {role}'s evidence."
        ticket.updated_at = datetime.now(UTC)
        ticket.version += 1
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=next_job_id,
                ticket_id=ticket.ticket_id,
                job_type="coordinator_step",
                payload={
                    "iteration": next_iteration,
                    "phase": phase,
                    "reports": [item.model_dump(mode="json") for item in reports],
                },
                available_at=datetime.now(UTC),
            ),
        )
        self._save_loop_state(
            ticket,
            current_step="coordinator:review",
            iteration=next_iteration,
            phase=phase,
            reports=reports,
            active_agent=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            objective=f"Review {role}'s report and select the next durable step.",
            next_job=next_job_id,
        )

    def _accept_decision(
        self,
        ticket: Ticket,
        decision: AgentDecision,
        knowledge_result: dict[str, Any] | None,
        iteration: int,
    ) -> None:
        ticket.kind = decision.kind
        ticket.priority = decision.priority
        ticket.safety_flags = decision.safety_flags
        ticket.confidence = decision.confidence
        self._event(
            ticket,
            "agent.decision",
            decision.rationale,
            actor=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            payload={**decision.model_dump(mode="json"), "runtime": self.agent.name},
            key=f"COORDINATOR-{iteration}-DECISION",
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
                "maintenance_summary": " ".join(report.summary for report in decision.specialist_reports if report.role == "Maintenance Intelligence Agent"),
                "diagnosis": decision.diagnosis,
                "coordinator_role": getattr(self.agent, "coordinator_role", "Operations Coordinator"),
                "specialist_roles": [report.role for report in decision.specialist_reports],
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
                    "loop_iteration": iteration,
                },
                available_at=wake,
            ),
        )
        self._send_update(ticket, decision.user_update, key="TRIAGE")
        self._save_loop_state(
            ticket,
            current_step=f"action:{decision.selected_action}",
            iteration=iteration,
            phase="execution",
            reports=decision.specialist_reports,
            active_agent=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            objective=decision.objective,
            next_job=f"JOB-{ticket.ticket_id}-EXECUTE-DECISION",
        )

    def _execute_decision(self, ticket: Ticket, job: WorkflowJob) -> None:
        if ticket.status != TicketStatus.WORKING:
            return
        decision = AgentDecision.model_validate(job.payload.get("decision", {}))
        selected_action = decision.selected_action
        if selected_action == "answer_enquiry":
            self._answer_enquiry(
                ticket,
                job.payload.get("knowledge_result"),
                int(job.payload.get("loop_iteration", 1)),
                decision.specialist_reports,
            )
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

    def _stored_reports(self, ticket: Ticket) -> list[SpecialistReport]:
        decision_event = next(
            (
                event
                for event in reversed(self.repository.list_events(ticket.ticket_id))
                if event.event_type == "agent.decision"
            ),
            None,
        )
        if not decision_event:
            return []
        return [
            SpecialistReport.model_validate(item)
            for item in decision_event.payload.get("specialist_reports", [])
        ]

    def _next_iteration(self, ticket: Ticket) -> int:
        state = self.repository.get_workflow_state(ticket.ticket_id)
        current = int(state.checkpoint.get("loop_iteration", 0)) if state else 0
        return min(12, current + 1)

    def _schedule_coordinator(
        self,
        ticket: Ticket,
        *,
        phase: str,
        iteration: int,
        reports: list[SpecialistReport],
        available_at: datetime,
        objective: str,
    ) -> None:
        job_id = f"JOB-{ticket.ticket_id}-COORDINATOR-{phase.upper()}-{iteration}"
        self.repository.save_ticket_and_job(
            ticket,
            WorkflowJob(
                job_id=job_id,
                ticket_id=ticket.ticket_id,
                job_type="coordinator_step",
                payload={
                    "iteration": iteration,
                    "phase": phase,
                    "reports": [report.model_dump(mode="json") for report in reports],
                },
                available_at=available_at,
            ),
        )
        self._save_loop_state(
            ticket,
            current_step=f"coordinator:{phase}",
            iteration=iteration,
            phase=phase,
            reports=reports,
            active_agent=getattr(self.agent, "coordinator_role", "Operations Coordinator"),
            objective=objective,
            next_job=job_id,
        )

    def _answer_enquiry(
        self,
        ticket: Ticket,
        result: dict[str, str] | None,
        iteration: int,
        reports: list[SpecialistReport],
    ) -> None:
        if not result:
            self._transition(ticket, TicketStatus.ESCALATED)
            self._event(ticket, "ticket.escalated", "No authoritative building information matched the request.", key="NO-KNOWLEDGE")
            return
        message = f"{result['answer']} Source: {result['source']}."
        self._send_update(ticket, message, key="ANSWER")
        ticket.waiting_reason = "The Operations Coordinator is confirming delivery before closure."
        ticket.updated_at = datetime.now(UTC)
        ticket.version += 1
        self._schedule_coordinator(
            ticket,
            phase="knowledge_delivery",
            iteration=iteration + 1,
            reports=reports,
            available_at=datetime.now(UTC),
            objective="Confirm the grounded answer was delivered before closing the ticket.",
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
        self._schedule_coordinator(
            ticket,
            phase="verification",
            iteration=self._next_iteration(ticket),
            reports=decision.specialist_reports,
            available_at=wake,
            objective="Select independent post-action verification before closure.",
        )
        self._send_update(ticket, "I made a policy-safe temperature adjustment and am verifying the room response before closing the ticket.", key="VERIFY-WAIT")

    def _investigate_incident(self, ticket: Ticket, decision: AgentDecision) -> None:
        correlated = self.building.condition_for_ticket(ticket.ticket_id)
        cited_evidence: list[dict[str, object]] = []
        for sensor_id in decision.evidence_sensor_ids:
            try:
                cited_evidence.append(self.building.telemetry(sensor_id))
            except KeyError:
                continue
        text = f"{ticket.subject} {ticket.description}".lower()
        electrical_report = any(
            term in text
            for term in (
                "circuit",
                "electric",
                "outlet",
                "breaker",
                "wiring",
                "flicker",
                "spark",
                "hot plastic",
            )
        )
        preferred_types = (
            {"Electrical load", "Cabinet temperature"}
            if electrical_report
            else {"VOC / odor", "CO₂", "Humidity"}
        )
        context = self.building.investigation_context(ticket)
        candidates = [
            item
            for item in [
                *cited_evidence,
                *(([correlated["sensor"]]) if correlated else []),
                *context.get("nearby_sensors", []),
            ]
            if item.get("type") in preferred_types
        ]
        asset = next(
            (item for item in candidates if item.get("state") in {"Warning", "Critical"}),
            candidates[0] if candidates else (correlated["sensor"] if correlated else None),
        )
        if not asset:
            self._transition(ticket, TicketStatus.ESCALATED)
            self._event(ticket, "ticket.escalated", "No correlated building sensor or candidate asset was found.", key="NO-BUILDING-ASSET")
            return
        telemetry = self.building.telemetry(asset["asset_id"])
        history = self.building.history(asset["asset_id"])
        is_air_quality = not electrical_report
        trade = "indoor_air_quality" if is_air_quality else "electrical"
        action_type = "dispatch_safety_technician" if is_air_quality else "dispatch_electrical_technician"
        procedure = (
            f"Inspect {ticket.location_id}, test air quality at the reported source, isolate the odor source, ventilate if safe, and document clearance readings."
            if is_air_quality
            else f"Inspect {ticket.location_id} for a localized overheated appliance, outlet, branch circuit, or connection; thermal-scan the area, perform only an SOP-approved like-for-like repair, and document the exact cause and clearance readings."
        )
        observations = ", ".join(
            f"{item.get('id')} {item.get('value')} ({str(item.get('state', 'unknown')).lower()})"
            for item in cited_evidence[:4]
        )
        corroborated = telemetry.get("state") in {"Warning", "Critical"}
        evidence_summary = (
            f"{telemetry.get('id', telemetry.get('asset_id'))} at {telemetry.get('area', ticket.location_id)} is {telemetry.get('value', 'in alarm')} and reporting {str(telemetry.get('state', 'unknown')).lower()}. Working diagnosis: {decision.diagnosis}"
            if corroborated
            else f"No building-level alarm corroborated the localized report; checked {observations or f'{telemetry.get("id")} {telemetry.get("value")}'}. A fault at an appliance, outlet, or room-level source can sit outside central sensor coverage. Working diagnosis: {decision.diagnosis}"
        )
        self._event(
            ticket,
            "evidence.collected",
            evidence_summary,
            payload={"asset": asset, "telemetry": telemetry, "history": history},
            key="INCIDENT-EVIDENCE",
        )
        shared_infrastructure = asset.get("asset_id") == "ELEC-7A"
        policy_parameters = {
            "priority": str(ticket.priority),
            "qualified_personnel": True,
            "scope": "shared_infrastructure" if shared_infrastructure else "localized",
            "service_disruption": shared_infrastructure,
        }
        policy = self.policy.evaluate(action_type, policy_parameters)
        action = ActionRecord(
            action_id=f"ACT-{ticket.ticket_id}-DISPATCH",
            ticket_id=ticket.ticket_id,
            action_type=action_type,
            risk_tier=policy.tier,
            policy_rule=policy.rule,
            status="approved" if policy.tier == RiskTier.AUTONOMOUS else "proposed",
            before_state=telemetry,
            requested={
                "asset_id": asset["asset_id"],
                "trade": trade,
                "priority": str(ticket.priority),
                "procedure": procedure,
                "diagnosis": decision.diagnosis,
                "evidence_sensor_ids": decision.evidence_sensor_ids,
                "maintenance_summary": " ".join(report.summary for report in decision.specialist_reports if report.role == "Maintenance Intelligence Agent"),
                "scope": policy_parameters["scope"],
            },
            rationale=f"{policy.reason}. {decision.diagnosis}",
            idempotency_key=f"DISPATCH-{ticket.ticket_id}",
            created_at=datetime.now(UTC),
        )
        self.repository.save_action(action)
        if policy.tier == RiskTier.AUTONOMOUS:
            self._event(
                ticket,
                "action.authorized",
                f"Policy {policy.rule} authorized a qualified {trade.replace('_', ' ')} technician for localized inspection; no safety-critical control was operated.",
                payload={
                    "action": action.model_dump(mode="json"),
                    "policy_parameters": policy_parameters,
                },
                key="DISPATCH-AUTHORIZED",
            )
            self._dispatch_incident(ticket)
            return
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
        technician_delay = self._technician_delay_for_ticket(ticket)
        due = datetime.now(UTC) + timedelta(seconds=technician_delay)
        action = self.repository.get_action(f"ACT-{ticket.ticket_id}-DISPATCH")
        requested = action.requested if action else {}
        brief = (
            f"Resident report: {ticket.description}\n"
            f"Location: {ticket.location_id}\n"
            f"Working diagnosis (requires on-site confirmation): {requested.get('diagnosis', 'Not established')}\n"
            f"Evidence sensor IDs: {', '.join(requested.get('evidence_sensor_ids', [])) or 'Not available'}\n"
            f"Maintenance context: {requested.get('maintenance_summary') or 'No matching history recorded'}\n"
            f"Procedure: {requested.get('procedure', 'Inspect the affected system and document safe restoration.')}"
        )
        order = self.work_orders.create(
            ticket,
            asset_id=str(requested.get("asset_id", "ELEC-PNL-7A")),
            trade=str(requested.get("trade", "electrical")),
            procedure=brief,
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
            f"Created {order.work_order_id} and assigned {order.technician}; scheduled completion is in {technician_delay:g} seconds.",
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

    def _technician_delay_for_ticket(self, ticket: Ticket) -> float:
        created = next(
            (
                event
                for event in self.repository.list_events(ticket.ticket_id)
                if event.event_type == "ticket.created"
            ),
            None,
        )
        configured = (
            created.payload.get("intake", {}).get("technician_delay_seconds")
            if created
            else None
        )
        try:
            return min(300.0, max(0.0, float(configured)))
        except (TypeError, ValueError):
            return self.technician_delay_seconds

    def _complete_technician(self, ticket: Ticket) -> None:
        if ticket.status != TicketStatus.WAITING_TECHNICIAN:
            return
        existing_order = self.repository.get_work_order_for_ticket(ticket.ticket_id)
        if not existing_order:
            raise RuntimeError(f"No work order exists for {ticket.ticket_id}")
        repair = self.building.complete_incident_repair(existing_order.asset_id, ticket.ticket_id)
        completion_notes = str(
            repair.get("completion_notes")
            or repair.get("repair_performed")
            or "The technician repaired the affected component and documented stable clearance readings."
        )
        order = self.work_orders.complete(ticket.ticket_id, completion_notes)
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
        self._schedule_coordinator(
            ticket,
            phase="verification",
            iteration=self._next_iteration(ticket),
            reports=self._stored_reports(ticket),
            available_at=wake,
            objective="Review the technician outcome and select independent verification.",
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
