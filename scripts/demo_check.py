from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.config import Settings
from backend.app.domain.models import ApprovalRequest, TicketStatus
from backend.app.system import build_system


def exercise(case: str, *, restart: bool = False) -> None:
    with TemporaryDirectory() as directory:
        settings = Settings(
            database_path=Path(directory) / "demo.db",
            intake_delay_seconds=0,
            agent_analysis_seconds=0,
            action_delay_seconds=0,
            technician_delay_seconds=0,
            verification_delay_seconds=0,
        )
        system = build_system(settings)
        system.tickets.seed_demo()
        for _ in range(3):
            system.workflow.process_due(limit=10)
        ids = {"enquiry": "TKT-1001", "service_request": "TKT-1002", "incident": "TKT-1003"}
        ticket_id = ids[case]
        if case == "incident":
            system.tickets.decide_approval(
                ticket_id,
                request=ApprovalRequest(approved=True, reason="Operations approval"),
            )
        if restart:
            system = build_system(settings)
        for _ in range(6):
            system.workflow.process_due(now=datetime.now(UTC) + timedelta(hours=1), limit=100)
        detail = system.tickets.detail(ticket_id)
        assert detail.ticket.status == TicketStatus.RESOLVED, detail.ticket
        if case == "enquiry":
            assert any("Source:" in event.summary for event in detail.events)
        if case == "service_request":
            assert len(detail.actions) == 1 and detail.actions[0].status == "completed"
        if case == "incident":
            assert detail.work_order and detail.work_order.status == "completed"
        print(f"PASS {case}: {ticket_id} resolved with {len(detail.events)} audit events")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    requested = os.getenv("DEMO_CASE", "all")
    cases = [requested] if requested != "all" else ["enquiry", "service_request", "incident"]
    restart = os.getenv("DEMO_RESTART", "0") == "1"
    for _ in range(args.runs):
        for case in cases:
            exercise(case, restart=restart and case == "incident")


if __name__ == "__main__":
    main()
