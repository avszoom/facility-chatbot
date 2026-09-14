from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from backend.app.domain.models import (
    ActionRecord,
    DashboardMetrics,
    MessageDelivery,
    PubSubMessage,
    Ticket,
    TicketEvent,
    TicketStatus,
    WorkflowJob,
    WorkflowState,
    WorkOrder,
)


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    kind TEXT NOT NULL,
    priority TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_events (
    event_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    body TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflow_jobs (
    job_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    available_at TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until TEXT,
    last_error TEXT,
    FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jobs_due
ON workflow_jobs(status, available_at);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    status TEXT NOT NULL,
    body TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS work_orders (
    work_order_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    body TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pubsub_messages (
    message_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    message_type TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    published_at TEXT NOT NULL,
    available_at TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pubsub_deliveries (
    message_id TEXT NOT NULL,
    subscription TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until TEXT,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT,
    completed_at TEXT,
    PRIMARY KEY(message_id, subscription),
    FOREIGN KEY(message_id) REFERENCES pubsub_messages(message_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pubsub_due
ON pubsub_deliveries(subscription, status, next_attempt_at);

CREATE TABLE IF NOT EXISTS workflow_states (
    ticket_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL UNIQUE,
    current_step TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    body TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id) ON DELETE CASCADE
);
"""


def _dump(model_or_value: Any) -> str:
    if hasattr(model_or_value, "model_dump"):
        model_or_value = model_or_value.model_dump(mode="json")
    return json.dumps(model_or_value, separators=(",", ":"), sort_keys=True)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class SQLiteOperationsRepository:
    """SQLite adapter; all business code depends on OperationsRepository instead."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    def reset(self) -> None:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for table in (
                "pubsub_deliveries",
                "pubsub_messages",
                "ticket_events",
                "workflow_jobs",
                "actions",
                "work_orders",
                "workflow_states",
                "tickets",
                "app_state",
            ):
                connection.execute(f"DELETE FROM {table}")
            connection.commit()

    def create_ticket(self, ticket: Ticket) -> Ticket:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO tickets(ticket_id,status,kind,priority,updated_at,body) VALUES(?,?,?,?,?,?)",
                (
                    ticket.ticket_id,
                    str(ticket.status),
                    str(ticket.kind),
                    str(ticket.priority),
                    ticket.updated_at.isoformat(),
                    _dump(ticket),
                ),
            )
        return ticket

    def create_ticket_and_job(self, ticket: Ticket, job: WorkflowJob) -> Ticket:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO tickets(ticket_id,status,kind,priority,updated_at,body) VALUES(?,?,?,?,?,?)",
                (ticket.ticket_id, str(ticket.status), str(ticket.kind), str(ticket.priority), ticket.updated_at.isoformat(), _dump(ticket)),
            )
            connection.execute(
                """INSERT INTO workflow_jobs
                   (job_id,ticket_id,job_type,payload,available_at,status,attempts,lease_until,last_error)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (job.job_id, job.ticket_id, job.job_type, _dump(job.payload), job.available_at.isoformat(), job.status, job.attempts, None, None),
            )
            connection.commit()
        return ticket

    def save_ticket(self, ticket: Ticket) -> Ticket:
        with self.connection() as connection:
            connection.execute(
                """UPDATE tickets SET status=?,kind=?,priority=?,updated_at=?,body=?
                   WHERE ticket_id=?""",
                (
                    str(ticket.status),
                    str(ticket.kind),
                    str(ticket.priority),
                    ticket.updated_at.isoformat(),
                    _dump(ticket),
                    ticket.ticket_id,
                ),
            )
        return ticket

    def save_ticket_and_job(self, ticket: Ticket, job: WorkflowJob) -> Ticket:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE tickets SET status=?,kind=?,priority=?,updated_at=?,body=?
                   WHERE ticket_id=?""",
                (str(ticket.status), str(ticket.kind), str(ticket.priority), ticket.updated_at.isoformat(), _dump(ticket), ticket.ticket_id),
            )
            connection.execute(
                """INSERT OR IGNORE INTO workflow_jobs
                   (job_id,ticket_id,job_type,payload,available_at,status,attempts,lease_until,last_error)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (job.job_id, job.ticket_id, job.job_type, _dump(job.payload), job.available_at.isoformat(), job.status, job.attempts, None, None),
            )
            connection.commit()
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT body FROM tickets WHERE ticket_id=?", (ticket_id,)
            ).fetchone()
        return Ticket.model_validate_json(row["body"]) if row else None

    def list_tickets(self) -> list[Ticket]:
        rank = "CASE priority WHEN 'emergency' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END"
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT body FROM tickets ORDER BY {rank}, updated_at DESC"
            ).fetchall()
        return [Ticket.model_validate_json(row["body"]) for row in rows]

    def append_event(self, event: TicketEvent) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO ticket_events(event_id,ticket_id,created_at,body) VALUES(?,?,?,?)",
                (event.event_id, event.ticket_id, event.created_at.isoformat(), _dump(event)),
            )
        return cursor.rowcount == 1

    def list_events(self, ticket_id: str) -> list[TicketEvent]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT body FROM ticket_events WHERE ticket_id=? ORDER BY created_at,event_id",
                (ticket_id,),
            ).fetchall()
        return [TicketEvent.model_validate_json(row["body"]) for row in rows]

    def enqueue_job(self, job: WorkflowJob) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO workflow_jobs
                   (job_id,ticket_id,job_type,payload,available_at,status,attempts,lease_until,last_error)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    job.job_id,
                    job.ticket_id,
                    job.job_type,
                    _dump(job.payload),
                    job.available_at.isoformat(),
                    job.status,
                    job.attempts,
                    job.lease_until.isoformat() if job.lease_until else None,
                    job.last_error,
                ),
            )
        return cursor.rowcount == 1

    def claim_due_jobs(self, now: datetime, limit: int = 10) -> list[WorkflowJob]:
        lease_until = now + timedelta(seconds=30)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE workflow_jobs SET status='pending',lease_until=NULL
                   WHERE status='processing' AND lease_until IS NOT NULL AND lease_until<=?""",
                (now.isoformat(),),
            )
            rows = connection.execute(
                """SELECT * FROM workflow_jobs
                   WHERE status='pending' AND available_at<=?
                   ORDER BY available_at,job_id LIMIT ?""",
                (now.isoformat(), limit),
            ).fetchall()
            claimed: list[WorkflowJob] = []
            for row in rows:
                connection.execute(
                    """UPDATE workflow_jobs SET status='processing',attempts=attempts+1,lease_until=?
                       WHERE job_id=? AND status='pending'""",
                    (lease_until.isoformat(), row["job_id"]),
                )
                claimed.append(
                    WorkflowJob(
                        job_id=row["job_id"],
                        ticket_id=row["ticket_id"],
                        job_type=row["job_type"],
                        payload=json.loads(row["payload"]),
                        available_at=_parse_datetime(row["available_at"]),
                        status="processing",
                        attempts=int(row["attempts"]) + 1,
                        lease_until=lease_until,
                        last_error=row["last_error"],
                    )
                )
            connection.commit()
        return claimed

    def complete_job(self, job_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE workflow_jobs SET status='completed',lease_until=NULL,last_error=NULL WHERE job_id=?",
                (job_id,),
            )

    def retry_job(self, job_id: str, error: str, available_at: datetime) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE workflow_jobs SET status='pending',available_at=?,lease_until=NULL,last_error=?
                   WHERE job_id=?""",
                (available_at.isoformat(), error[:1000], job_id),
            )

    def list_jobs(self, ticket_id: str | None = None) -> list[WorkflowJob]:
        query = "SELECT * FROM workflow_jobs"
        params: tuple[Any, ...] = ()
        if ticket_id:
            query += " WHERE ticket_id=?"
            params = (ticket_id,)
        query += " ORDER BY available_at,job_id"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            WorkflowJob(
                job_id=row["job_id"],
                ticket_id=row["ticket_id"],
                job_type=row["job_type"],
                payload=json.loads(row["payload"]),
                available_at=_parse_datetime(row["available_at"]),
                status=row["status"],
                attempts=row["attempts"],
                lease_until=_parse_datetime(row["lease_until"]),
                last_error=row["last_error"],
            )
            for row in rows
        ]

    def publish_message(self, message: PubSubMessage, subscriptions: list[str]) -> bool:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """INSERT OR IGNORE INTO pubsub_messages
                   (message_id,topic,message_type,correlation_id,idempotency_key,published_at,available_at,body)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    message.message_id,
                    message.topic,
                    message.message_type,
                    message.correlation_id,
                    message.idempotency_key,
                    message.published_at.isoformat(),
                    message.available_at.isoformat(),
                    _dump(message),
                ),
            )
            inserted = cursor.rowcount == 1
            if inserted:
                for subscription in subscriptions:
                    connection.execute(
                        """INSERT INTO pubsub_deliveries
                           (message_id,subscription,status,attempts,lease_until,next_attempt_at,last_error,completed_at)
                           VALUES(?,?,'pending',0,NULL,?,NULL,NULL)""",
                        (message.message_id, subscription, message.available_at.isoformat()),
                    )
            connection.commit()
        return inserted

    def claim_deliveries(
        self,
        subscription: str,
        now: datetime,
        limit: int = 1,
        lease_seconds: float = 30,
    ) -> list[MessageDelivery]:
        lease_until = now + timedelta(seconds=lease_seconds)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE pubsub_deliveries SET status='pending',lease_until=NULL
                   WHERE subscription=? AND status='processing'
                     AND lease_until IS NOT NULL AND lease_until<=?""",
                (subscription, now.isoformat()),
            )
            rows = connection.execute(
                """SELECT d.*,m.body FROM pubsub_deliveries d
                   JOIN pubsub_messages m ON m.message_id=d.message_id
                   WHERE d.subscription=? AND d.status='pending' AND d.next_attempt_at<=?
                   ORDER BY d.next_attempt_at,d.message_id LIMIT ?""",
                (subscription, now.isoformat(), limit),
            ).fetchall()
            claimed: list[MessageDelivery] = []
            for row in rows:
                updated = connection.execute(
                    """UPDATE pubsub_deliveries
                       SET status='processing',attempts=attempts+1,lease_until=?
                       WHERE message_id=? AND subscription=? AND status='pending'""",
                    (lease_until.isoformat(), row["message_id"], subscription),
                )
                if updated.rowcount != 1:
                    continue
                claimed.append(
                    MessageDelivery(
                        subscription=subscription,
                        message=PubSubMessage.model_validate_json(row["body"]),
                        status="processing",
                        attempts=int(row["attempts"]) + 1,
                        lease_until=lease_until,
                        next_attempt_at=_parse_datetime(row["next_attempt_at"]),
                        last_error=row["last_error"],
                    )
                )
            connection.commit()
        return claimed

    def complete_delivery(self, subscription: str, message_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE pubsub_deliveries
                   SET status='completed',lease_until=NULL,last_error=NULL,completed_at=?
                   WHERE message_id=? AND subscription=? AND status!='dead_letter'""",
                (datetime.now(UTC).isoformat(), message_id, subscription),
            )

    def retry_delivery(
        self,
        subscription: str,
        message_id: str,
        error: str,
        available_at: datetime,
        *,
        dead_letter: bool = False,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE pubsub_deliveries
                   SET status=?,next_attempt_at=?,lease_until=NULL,last_error=?
                   WHERE message_id=? AND subscription=?""",
                (
                    "dead_letter" if dead_letter else "pending",
                    available_at.isoformat(),
                    error[:1000],
                    message_id,
                    subscription,
                ),
            )

    def message_stats(self) -> dict[str, int]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT status,COUNT(*) AS count FROM pubsub_deliveries GROUP BY status"
            ).fetchall()
            retrying = connection.execute(
                """SELECT COUNT(*) AS count FROM pubsub_deliveries
                   WHERE status='pending' AND attempts>0"""
            ).fetchone()["count"]
            topics = connection.execute(
                "SELECT COUNT(DISTINCT topic) AS count FROM pubsub_messages"
            ).fetchone()["count"]
        counts = {row["status"]: int(row["count"]) for row in rows}
        return {
            "topics": int(topics),
            "pending": counts.get("pending", 0),
            "processing": counts.get("processing", 0),
            "completed": counts.get("completed", 0),
            "retrying": int(retrying),
            "dead_letters": counts.get("dead_letter", 0),
        }

    def workflow_deliveries(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("""SELECT d.status,d.attempts,d.lease_until,d.last_error,m.body
                FROM pubsub_deliveries d JOIN pubsub_messages m ON m.message_id=d.message_id
                WHERE d.subscription='operations.workflow' AND d.status != 'completed'""").fetchall()
        result = []
        now = datetime.now(UTC).isoformat()
        for row in rows:
            job = json.loads(row["body"]).get("payload", {}).get("job", {})
            state = row["status"]
            if state == "processing" and (not row["lease_until"] or row["lease_until"] <= now):
                state = "lease_expired"
            result.append({"ticket_id": job.get("ticket_id"), "status": state, "attempts": row["attempts"], "step": job.get("job_type"), "role": job.get("payload", {}).get("role"), "error": row["last_error"]})
        return result

    def save_workflow_state(self, state: WorkflowState) -> WorkflowState:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO workflow_states
                   (ticket_id,workflow_id,current_step,status,version,updated_at,body)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(ticket_id) DO UPDATE SET
                     current_step=excluded.current_step,
                     status=excluded.status,
                     version=excluded.version,
                     updated_at=excluded.updated_at,
                     body=excluded.body
                   WHERE excluded.version>=workflow_states.version""",
                (
                    state.ticket_id,
                    state.workflow_id,
                    state.current_step,
                    state.status,
                    state.version,
                    state.updated_at.isoformat(),
                    _dump(state),
                ),
            )
        return state

    def get_workflow_state(self, ticket_id: str) -> WorkflowState | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT body FROM workflow_states WHERE ticket_id=?", (ticket_id,)
            ).fetchone()
        return WorkflowState.model_validate_json(row["body"]) if row else None

    def save_action(self, action: ActionRecord) -> ActionRecord:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO actions(action_id,ticket_id,status,body) VALUES(?,?,?,?)
                   ON CONFLICT(action_id) DO UPDATE SET status=excluded.status,body=excluded.body""",
                (action.action_id, action.ticket_id, action.status, _dump(action)),
            )
        return action

    def get_action(self, action_id: str) -> ActionRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT body FROM actions WHERE action_id=?", (action_id,)
            ).fetchone()
        return ActionRecord.model_validate_json(row["body"]) if row else None

    def list_actions(self, ticket_id: str) -> list[ActionRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT body FROM actions WHERE ticket_id=? ORDER BY action_id", (ticket_id,)
            ).fetchall()
        return [ActionRecord.model_validate_json(row["body"]) for row in rows]

    def save_work_order(self, work_order: WorkOrder) -> WorkOrder:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO work_orders(work_order_id,ticket_id,status,body) VALUES(?,?,?,?)
                   ON CONFLICT(work_order_id) DO UPDATE SET status=excluded.status,body=excluded.body""",
                (
                    work_order.work_order_id,
                    work_order.ticket_id,
                    work_order.status,
                    _dump(work_order),
                ),
            )
        return work_order

    def get_work_order_for_ticket(self, ticket_id: str) -> WorkOrder | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT body FROM work_orders WHERE ticket_id=?", (ticket_id,)
            ).fetchone()
        return WorkOrder.model_validate_json(row["body"]) if row else None

    def get_state(self, key: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT body FROM app_state WHERE key=?", (key,)).fetchone()
        return json.loads(row["body"]) if row else None

    def set_state(self, key: str, value: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO app_state(key,body) VALUES(?,?)
                   ON CONFLICT(key) DO UPDATE SET body=excluded.body""",
                (key, _dump(value)),
            )

    def metrics(self) -> DashboardMetrics:
        tickets = self.list_tickets()
        events = {ticket.ticket_id: self.list_events(ticket.ticket_id) for ticket in tickets}
        resolved = [ticket for ticket in tickets if ticket.status == TicketStatus.RESOLVED]
        autonomous = [
            ticket for ticket in resolved
            if not any(
                event.event_type in {"approval.decided", "staff.response_sent"}
                for event in events[ticket.ticket_id]
            )
        ]
        return DashboardMetrics(
            received=len(tickets),
            active=sum(ticket.status != TicketStatus.RESOLVED for ticket in tickets),
            resolved=len(resolved),
            autonomous_resolutions=len(autonomous),
            needs_approval=sum(ticket.status == TicketStatus.NEEDS_APPROVAL for ticket in tickets),
            escalated=sum(ticket.status == TicketStatus.ESCALATED for ticket in tickets),
            human_touches_saved=sum(
                event.event_type in {"message.sent", "action.completed", "work_order.created", "verification.passed"}
                for ticket_events in events.values() for event in ticket_events
            ),
            verified_closures=sum(
                any(event.event_type == "verification.passed" for event in events[ticket.ticket_id])
                for ticket in resolved
            ),
        )
