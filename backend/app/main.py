from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import json

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.app.domain.models import (
    ApprovalRequest,
    PubSubMessage,
    SimulationControl,
    SimulationCustomRequest,
    SimulationGenerateRequest,
    StaffResponseRequest,
    Ticket,
    TicketCreate,
    TicketDetail,
)
from backend.app.system import ApplicationSystem, build_system


def create_app(system: ApplicationSystem | None = None) -> FastAPI:
    runtime = system or build_system()
    api = FastAPI(title="BuildingOps Autopilot API", version="0.1.0")
    api.state.system = runtime
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def missing(ticket_id: str) -> HTTPException:
        return HTTPException(status_code=404, detail=f"Ticket {ticket_id} was not found")

    @api.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "time": datetime.now(UTC), "runtime": runtime.agent.name}

    @api.get("/api/system")
    def system_info() -> dict:
        return {
            "environment": runtime.settings.app_env,
            "providers": runtime.providers(),
            "portable_contracts": True,
        }

    @api.get("/api/metrics")
    def metrics():
        return runtime.repository.metrics()

    @api.get("/api/operations/live")
    def live_operations() -> dict:
        tickets = runtime.tickets.list()
        dashboard = runtime.repository.metrics()
        jobs = runtime.repository.list_jobs()
        messaging = runtime.message_bus.stats()
        all_events = [
            event.model_dump(mode="json")
            for ticket in tickets
            for event in runtime.repository.list_events(ticket.ticket_id)
        ]
        recent_events = sorted(
            all_events,
            key=lambda event: event["created_at"],
            reverse=True,
        )[:30]
        return {
            "simulation": runtime.simulation.status(),
            "building": runtime.building.snapshot(),
            "agent": {
                "status": "online",
                "runtime": runtime.agent.name,
                "provider": runtime.agent.provider,
                "model": runtime.agent.model_id,
                "real_model": runtime.agent.real_model,
                "worker_count": runtime.settings.agent_worker_count,
                "active_executions": messaging["processing"],
                "queued_tasks": sum(job.status == "pending" for job in jobs)
                + messaging["pending"],
                "active_tickets": [
                    ticket.model_dump(mode="json")
                    for ticket in tickets
                    if ticket.status not in {"resolved", "escalated"}
                ],
            },
            "messaging": {
                "broker": runtime.message_bus.name,
                **messaging,
                "delivery": "at_least_once",
                "idempotent_consumers": True,
            },
            "recent_events": recent_events,
            "impact": {
                "actions_performed": sum(
                    event["event_type"]
                    in {
                        "agent.decision",
                        "agent.tools_completed",
                        "evidence.collected",
                        "message.sent",
                        "action.completed",
                        "work_order.created",
                        "verification.passed",
                        "ticket.resolved",
                    }
                    for event in all_events
                ),
                "issues_resolved": dashboard.resolved,
                "resolved_autonomously": dashboard.autonomous_resolutions,
                "needs_user": dashboard.needs_approval + dashboard.escalated,
                "human_touches_saved": dashboard.human_touches_saved,
                "autonomy_rate": round(
                    dashboard.autonomous_resolutions / dashboard.resolved * 100
                )
                if dashboard.resolved
                else 100,
                "verified_resolutions": dashboard.verified_closures,
                "waiting_external": sum(
                    ticket.status == "waiting_technician" for ticket in tickets
                ),
            },
        }

    @api.post("/api/simulation/pulse", response_model=PubSubMessage)
    def simulation_pulse():
        message = runtime.simulation.tick(force=True, source="agent_activity_console")
        if message is None:
            raise HTTPException(status_code=409, detail="Building simulation is paused")
        return message

    @api.post("/api/simulation/control")
    def simulation_control(request: SimulationControl) -> dict:
        try:
            return runtime.simulation.configure(
                running=request.running,
                interval_seconds=request.interval_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/api/simulation/generate", response_model=list[PubSubMessage])
    def simulation_generate(
        request: SimulationGenerateRequest,
    ) -> list[PubSubMessage]:
        return runtime.simulation.generate_batch(
            count=request.count,
            scenario_type=request.scenario_type,
        )

    @api.post("/api/simulation/request", response_model=PubSubMessage, status_code=202)
    def simulation_request(request: SimulationCustomRequest) -> PubSubMessage:
        return runtime.simulation.publish_request(
            TicketCreate(
                subject=request.subject,
                description=request.description,
                requester=request.requester,
                location_id=request.location_id,
                kind=request.request_type,
            ),
            request_type=request.request_type,
            condition_type=request.condition_type,
        )

    @api.get("/api/tickets", response_model=list[Ticket])
    def list_tickets():
        return runtime.tickets.list()

    @api.post("/api/tickets", response_model=Ticket, status_code=201)
    def create_ticket(request: TicketCreate):
        return runtime.tickets.create(request)

    @api.get("/api/tickets/{ticket_id}", response_model=TicketDetail)
    def get_ticket(ticket_id: str):
        try:
            return runtime.tickets.detail(ticket_id)
        except KeyError:
            raise missing(ticket_id) from None

    @api.post("/api/tickets/{ticket_id}/run", response_model=Ticket)
    def run_ticket(ticket_id: str):
        try:
            ticket = runtime.tickets.enqueue_now(ticket_id)
        except KeyError:
            raise missing(ticket_id) from None
        runtime.operations.process_due()
        return runtime.repository.get_ticket(ticket.ticket_id)

    @api.post("/api/tickets/{ticket_id}/approval", response_model=Ticket)
    def approve(ticket_id: str, request: ApprovalRequest):
        try:
            ticket = runtime.tickets.decide_approval(ticket_id, request)
        except KeyError:
            raise missing(ticket_id) from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        runtime.operations.process_due()
        return runtime.repository.get_ticket(ticket.ticket_id)

    @api.post("/api/tickets/{ticket_id}/staff-response", response_model=Ticket)
    def staff_response(ticket_id: str, request: StaffResponseRequest):
        try:
            return runtime.tickets.respond_to_escalation(ticket_id, request)
        except KeyError:
            raise missing(ticket_id) from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/api/workspace/sample-requests", response_model=list[Ticket])
    @api.post("/api/demo/seed", response_model=list[Ticket], include_in_schema=False)
    def load_sample_requests():
        tickets = runtime.tickets.seed_demo()
        return [runtime.repository.get_ticket(ticket.ticket_id) for ticket in tickets]

    @api.post("/api/workspace/process-scheduled")
    @api.post("/api/demo/advance", include_in_schema=False)
    def process_scheduled(seconds: float = Query(default=60, ge=0, le=3600)) -> dict:
        processed = runtime.operations.process_due(
            now=datetime.now(UTC) + timedelta(seconds=seconds), limit=100
        )
        return {"processed": processed, "tickets": runtime.tickets.list()}

    @api.post("/api/workspace/verification-failure/{ticket_id}")
    @api.post("/api/demo/failure/{ticket_id}", include_in_schema=False)
    def verification_failure(ticket_id: str, enabled: bool = True) -> dict:
        if not runtime.repository.get_ticket(ticket_id):
            raise missing(ticket_id)
        runtime.building.set_verification_failure(ticket_id, enabled)
        return {"ticket_id": ticket_id, "verification_failure": enabled}

    @api.get("/api/jobs")
    def list_jobs(ticket_id: str | None = None):
        return runtime.repository.list_jobs(ticket_id)

    async def stream_events(request: Request) -> AsyncIterator[str]:
        async for event in runtime.events.subscribe():
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0)

    @api.get("/api/events")
    def events(request: Request):
        return StreamingResponse(stream_events(request), media_type="text/event-stream")

    return api


app = create_app()
