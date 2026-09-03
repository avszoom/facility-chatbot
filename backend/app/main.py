from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
import json

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.app.domain.models import ApprovalRequest, Ticket, TicketCreate, TicketDetail
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
        runtime.workflow.process_due()
        return runtime.repository.get_ticket(ticket.ticket_id)

    @api.post("/api/tickets/{ticket_id}/approval", response_model=Ticket)
    def approve(ticket_id: str, request: ApprovalRequest):
        try:
            ticket = runtime.tickets.decide_approval(ticket_id, request)
        except KeyError:
            raise missing(ticket_id) from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        runtime.workflow.process_due()
        return runtime.repository.get_ticket(ticket.ticket_id)

    @api.post("/api/demo/seed", response_model=list[Ticket])
    def seed_demo():
        tickets = runtime.tickets.seed_demo()
        runtime.workflow.process_due(limit=10)
        return [runtime.repository.get_ticket(ticket.ticket_id) for ticket in tickets]

    @api.post("/api/demo/advance")
    def advance_demo(seconds: float = Query(default=60, ge=0, le=3600)) -> dict:
        processed = runtime.workflow.process_due(now=datetime.now(UTC) + timedelta(seconds=seconds), limit=100)
        return {"processed": processed, "tickets": runtime.tickets.list()}

    @api.post("/api/demo/failure/{ticket_id}")
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
