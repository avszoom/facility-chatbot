from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class TicketKind(StrEnum):
    UNKNOWN = "unknown"
    ENQUIRY = "enquiry"
    SERVICE_REQUEST = "service_request"
    INCIDENT = "incident"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"


class TicketStatus(StrEnum):
    NEW = "new"
    TRIAGING = "triaging"
    WORKING = "working"
    NEEDS_APPROVAL = "needs_approval"
    WAITING_TECHNICIAN = "waiting_technician"
    WAITING_VERIFICATION = "waiting_verification"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class RiskTier(StrEnum):
    AUTONOMOUS = "autonomous"
    APPROVAL_REQUIRED = "approval_required"
    FORBIDDEN = "forbidden"


class TicketCreate(Model):
    subject: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=3, max_length=2000)
    requester: str = Field(default="Resident", min_length=2, max_length=80)
    location_id: str = Field(default="BLDG-A", min_length=2, max_length=80)
    kind: TicketKind | None = None


class Ticket(Model):
    ticket_id: str
    subject: str
    description: str
    requester: str
    location_id: str
    kind: TicketKind = TicketKind.UNKNOWN
    priority: TicketPriority = TicketPriority.NORMAL
    status: TicketStatus = TicketStatus.NEW
    safety_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    assigned_owner: str = "BuildingOps Autopilot"
    sla_due_at: datetime
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    waiting_reason: str | None = None
    wake_at: datetime | None = None
    version: int = 1


class TicketEvent(Model):
    event_id: str
    ticket_id: str
    actor: str
    event_type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    created_at: datetime


class WorkflowJob(Model):
    job_id: str
    ticket_id: str
    job_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    available_at: datetime
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    attempts: int = 0
    lease_until: datetime | None = None
    last_error: str | None = None


class PubSubMessage(Model):
    message_id: str
    topic: str
    message_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    idempotency_key: str
    published_at: datetime
    available_at: datetime


class MessageDelivery(Model):
    subscription: str
    message: PubSubMessage
    status: Literal["pending", "processing", "completed", "dead_letter"] = "pending"
    attempts: int = 0
    lease_until: datetime | None = None
    next_attempt_at: datetime
    last_error: str | None = None


class WorkflowState(Model):
    workflow_id: str
    ticket_id: str
    current_step: str
    status: Literal["running", "waiting", "completed", "failed"]
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    version: int
    updated_at: datetime


class ActionRecord(Model):
    action_id: str
    ticket_id: str
    action_type: str
    risk_tier: RiskTier
    policy_rule: str
    status: Literal["proposed", "approved", "denied", "completed", "blocked", "failed"]
    before_state: dict[str, Any] = Field(default_factory=dict)
    requested: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    idempotency_key: str
    created_at: datetime
    completed_at: datetime | None = None


class WorkOrder(Model):
    work_order_id: str
    ticket_id: str
    asset_id: str
    location_id: str
    trade: str
    priority: TicketPriority
    procedure: str
    technician: str
    status: Literal["requested", "in_progress", "completed", "failed"]
    requested_at: datetime
    due_at: datetime
    completed_at: datetime | None = None
    completion_notes: str | None = None


class AgentDecision(Model):
    kind: TicketKind
    priority: TicketPriority
    safety_flags: list[str] = Field(default_factory=list)
    objective: str
    selected_action: Literal[
        "answer_enquiry",
        "inspect_temperature",
        "investigate_incident",
        "escalate",
    ]
    confidence: float = Field(ge=0, le=1)
    rationale: str
    user_update: str
    evidence_sensor_ids: list[str] = Field(default_factory=list)
    diagnosis: str = ""
    tool_calls: list[str] = Field(default_factory=list)
    model_provider: str | None = None
    model_id: str | None = None


class ApprovalRequest(Model):
    approved: bool
    reason: str = Field(default="", max_length=500)


class StaffResponseRequest(Model):
    response: str = Field(min_length=3, max_length=2000)
    actor: str = Field(default="Maya Roberts", min_length=2, max_length=80)


class SimulationControl(Model):
    running: bool
    interval_seconds: float = Field(ge=5, le=3600)


class SimulationGenerateRequest(Model):
    count: int = Field(ge=1, le=20)
    scenario_type: Literal["all", "enquiry", "service_request", "incident"] = "all"


class SimulationCustomRequest(Model):
    request_type: Literal["enquiry", "service_request", "incident"]
    condition_type: Literal[
        "normal",
        "temperature_high",
        "temperature_low",
        "air_quality",
        "smoke_or_odor",
        "electrical_overheat",
    ] = "normal"
    subject: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=3, max_length=2000)
    requester: str = Field(default="Building Resident", min_length=2, max_length=80)
    location_id: str = Field(default="BLDG-A", min_length=2, max_length=80)
    technician_delay_seconds: float = Field(default=30, ge=5, le=300)


class TicketDetail(Model):
    ticket: Ticket
    events: list[TicketEvent]
    actions: list[ActionRecord]
    work_order: WorkOrder | None = None
    workflow: WorkflowState | None = None


class DashboardMetrics(Model):
    received: int
    active: int
    resolved: int
    autonomous_resolutions: int
    needs_approval: int
    escalated: int
    human_touches_saved: int
    verified_closures: int
