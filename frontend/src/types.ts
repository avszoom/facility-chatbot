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
  wake_at: string | null;
  updated_at: string;
  version: number;
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
  ticket_id: string;
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
  requested_at: string;
  due_at: string;
  completed_at: string | null;
  completion_notes: string | null;
}

export interface TicketDetail {
  ticket: Ticket;
  events: TicketEvent[];
  actions: ActionRecord[];
  work_order: WorkOrder | null;
  workflow: {
    workflow_id: string;
    current_step: string;
    status: "running" | "waiting" | "completed" | "failed";
    checkpoint: Record<string, unknown>;
    version: number;
    updated_at: string;
  } | null;
}

export interface LiveOperations {
  simulation: {
    status: "online" | "paused";
    running: boolean;
    sequence: number;
    issues_generated: number;
    last_tick: string | null;
    next_tick: string;
    interval_seconds: number;
    scenario_count: number;
    scenario_types: {
      enquiry: number;
      service_request: number;
      incident: number;
    };
    last_event: {
      type: string;
      ticket_id: string;
      subject: string;
      location_id: string;
      condition: { condition: string; updated_at: string };
    } | null;
  };
  building: {
    sensors: Record<string, {
      id: string;
      asset_id: string;
      name: string;
      floor: number;
      area: string;
      type: string;
      numeric_value: number;
      unit: string;
      value: string;
      target: string;
      state: "Normal" | "Warning" | "Critical";
      status: string;
      seen: string;
      location_id: string;
      updated_at: string | null;
    }>;
    sensor_history: Record<string, Array<{
      recorded_at: string | null;
      numeric_value: number;
      value: string;
      state: "Normal" | "Warning" | "Critical";
    }>>;
    maintenance_history: Array<{
      date: string;
      floor: number;
      asset_type: string;
      asset_id: string;
      summary: string;
      outcome: string;
    }>;
    health: {
      total: number;
      normal: number;
      warning: number;
      critical: number;
      monitoring: "autonomous";
    };
    assets: Record<string, {
      asset_id: string;
      name: string;
      type: string;
      location_id: string;
      status: string;
      temperature_f?: number;
      setpoint_f?: number;
      target_temperature_f?: number;
      cabinet_temperature_f?: number;
      current_amps?: number;
      fault?: string;
    }>;
    history: Record<string, Array<Record<string, number>>>;
    sensor_overrides: Record<string, {
      id: string;
      asset_id: string;
      floor: number;
      area: string;
      type: string;
      value: string;
      target: string;
      state: "Normal" | "Warning" | "Critical";
      seen: string;
      location_id: string;
    }>;
    active_conditions: Record<string, {
      ticket_id: string;
      sensor_id: string;
      condition: string;
      location_id: string;
    }>;
    updated_at: string | null;
    last_sensor_tick: string | null;
  };
  agent: {
    status: string;
    runtime: string;
    provider: string;
    model: string;
    real_model: boolean;
    coordinator_role: string;
    specialist_roles: string[];
    worker_count: number;
    active_executions: number;
    deliveries?: Array<{ticket_id: string; status: string; attempts: number; step: string; role: string | null; error: string | null}>;
    ticket_progress?: Record<string, {latest_event: TicketEvent | null; contributions: {agent_actions: number; human_actions: number; agent_percent: number | null}}>;
    queued_tasks: number;
    active_tickets: Ticket[];
    workflow_states: Record<string, {
      workflow_id: string;
      current_step: string;
      status: "running" | "waiting" | "completed" | "failed";
      checkpoint: Record<string, unknown>;
      version: number;
      updated_at: string;
    }>;
  };
  messaging: {
    broker: string;
    topics: number;
    pending: number;
    processing: number;
    completed: number;
    retrying: number;
    dead_letters: number;
    delivery: "at_least_once";
    idempotent_consumers: boolean;
  };
  recent_events: TicketEvent[];
  impact: {
    actions_performed: number;
    contributions?: { agent_actions: number; human_actions: number; technician_completions: number; agent_percent: number | null; human_percent: number | null };
    issues_resolved: number;
    resolved_autonomously: number;
    needs_user: number;
    human_touches_saved: number;
    autonomy_rate: number;
    verified_resolutions: number;
    waiting_external: number;
  };
}

export type RequestType = "enquiry" | "service_request" | "incident";

export interface CustomRequestInput {
  request_type: RequestType;
  condition_type: "normal" | "temperature_high" | "temperature_low" | "air_quality" | "smoke_or_odor" | "electrical_overheat";
  subject: string;
  description: string;
  requester: string;
  location_id: string;
  technician_delay_seconds: number;
}

export interface PublishedRequest {
  message_id: string;
  topic: string;
  correlation_id: string;
  payload: {
    ticket_id: string;
    request: Omit<CustomRequestInput, "request_type" | "condition_type" | "technician_delay_seconds"> & { kind: RequestType };
    scenario: {
      type: string;
      scenario_type: RequestType;
      source: string;
      condition: {
        condition: CustomRequestInput["condition_type"];
        sensor_id: string | null;
        sensor_ids?: string[];
        observable_signal_count?: number;
        location_id: string;
        updated_at: string;
      };
      requested_scenario_type?: RequestType;
      requested_condition_type?: CustomRequestInput["condition_type"];
      requested_location_id?: string;
      technician_delay_seconds?: number;
      normalization?: string | null;
    };
  };
}
