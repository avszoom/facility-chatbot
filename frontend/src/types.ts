export type TicketStatus =
  | "new"
  | "triaging"
  | "working"
  | "needs_approval"
  | "waiting_technician"
  | "waiting_verification"
  | "resolved"
  | "escalated";

export interface Ticket {
  ticket_id: string;
  subject: string;
  description: string;
  requester: string;
  location_id: string;
  kind: string;
  priority: string;
  status: TicketStatus;
  safety_flags: string[];
  confidence: number;
  assigned_owner: string;
  waiting_reason: string | null;
  updated_at: string;
}

export interface Metrics {
  received: number;
  active: number;
  resolved: number;
  autonomous_resolutions: number;
  needs_approval: number;
  escalated: number;
  human_touches_saved: number;
  verified_closures: number;
}

export interface TicketEvent {
  event_id: string;
  actor: string;
  event_type: string;
  summary: string;
  payload: Record<string, unknown>;
  correlation_id: string;
  created_at: string;
}

export interface ActionRecord {
  action_id: string;
  action_type: string;
  risk_tier: "autonomous" | "approval_required" | "forbidden";
  policy_rule: string;
  status: string;
  before_state: Record<string, unknown>;
  requested: Record<string, unknown>;
  after_state: Record<string, unknown>;
  rationale: string;
}

export interface WorkOrder {
  work_order_id: string;
  trade: string;
  technician: string;
  status: string;
  procedure: string;
  completion_notes: string | null;
}

export interface TicketDetail {
  ticket: Ticket;
  events: TicketEvent[];
  actions: ActionRecord[];
  work_order: WorkOrder | null;
}
