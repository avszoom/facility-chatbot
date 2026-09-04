import type { CustomRequestInput, LiveOperations, Metrics, PublishedRequest, Ticket, TicketDetail } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export const api = {
  tickets: () => request<Ticket[]>("/api/tickets"),
  ticket: (id: string) => request<TicketDetail>(`/api/tickets/${id}`),
  metrics: () => request<Metrics>("/api/metrics"),
  live: () => request<LiveOperations>("/api/operations/live"),
  simulationPulse: () => request<{ message_id: string }>("/api/simulation/pulse", { method: "POST" }),
  generateRequests: (payload: { count: number; scenario_type: "all" | "enquiry" | "service_request" | "incident" }) =>
    request<Array<{ message_id: string }>>("/api/simulation/generate", { method: "POST", body: JSON.stringify(payload) }),
  publishRequest: (payload: CustomRequestInput) =>
    request<PublishedRequest>("/api/simulation/request", { method: "POST", body: JSON.stringify(payload) }),
  configureSimulation: (payload: { running: boolean; interval_seconds: number }) =>
    request<LiveOperations["simulation"]>("/api/simulation/control", { method: "POST", body: JSON.stringify(payload) }),
  loadSampleRequests: () => request<Ticket[]>("/api/workspace/sample-requests", { method: "POST" }),
  create: (payload: { subject: string; description: string; requester: string; location_id: string }) =>
    request<Ticket>("/api/tickets", { method: "POST", body: JSON.stringify(payload) }),
  approve: (id: string, approved: boolean) =>
    request<Ticket>(`/api/tickets/${id}/approval`, {
      method: "POST",
      body: JSON.stringify({ approved, reason: approved ? "Approved in operations console" : "Operator declined dispatch" }),
    }),
  respond: (id: string, response: string) =>
    request<Ticket>(`/api/tickets/${id}/staff-response`, {
      method: "POST",
      body: JSON.stringify({ response, actor: "Maya Roberts" }),
    }),
  processScheduled: (seconds = 60) => request<{ processed: number }>(`/api/workspace/process-scheduled?seconds=${seconds}`, { method: "POST" }),
  failVerification: (id: string) => request(`/api/workspace/verification-failure/${id}?enabled=true`, { method: "POST" }),
  system: () => request<{ environment: string; providers: Record<string, string> }>("/api/system"),
};

export const apiBase = BASE;
