/**
 * PulseDebug AI — API Client
 * File: frontend/src/lib/api.ts
 * Purpose:
 *   Typed helper functions for every backend endpoint.
 *   All functions are async and throw on HTTP errors.
 *   Base URL is read from NEXT_PUBLIC_API_URL env var.
 *
 * Author: PulseDebug AI Hackathon Team
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────

export interface SystemStatus {
  total_requests:     number;
  failed_requests:    number;
  avg_latency_ms:     number;
  active_incidents:   number;
  critical_incidents: number;
  error_rate:         number;
  ai: {
    available:          boolean;
    active_model:       string | null;
    primary_exhausted:  boolean;
    fallback_exhausted: boolean;
    message:            string;
  };
}

export interface LogEvent {
  id:          number;
  timestamp:   string;
  service:     string;
  endpoint:    string;
  method:      string;
  status_code: number;
  latency_ms:  number;
  error_type:  string | null;
  error_msg:   string | null;
  is_anomaly:  number;
  scenario:    string | null;
  created_at:  string;
}

export interface Incident {
  id:                number;
  title:             string;
  service:           string;
  endpoint:          string;
  error_signature:   string;
  severity:          "critical" | "warning" | "investigate";
  status:            "open" | "resolved";
  occurrence_count:  number;
  first_detected:    string;
  last_seen:         string;
  deployment_id:     number | null;
  deployment_related:number;
  deployment:        Deployment | null;
  ai_summary:        string | null;
  ai_root_cause:     string | null;
  ai_checks:         string | null;
  ai_priority:       string | null;
  ai_model_used:     string | null;
  created_at:        string;
  updated_at:        string;
}

export interface Deployment {
  id:                    number;
  version:               string;
  service:               string;
  deployed_at:           string;
  status:                string;
  notes:                 string | null;
  linked_incident_count?: number;
}

export interface TimeseriesPoint {
  minute:      string;
  total:       number;
  errors:      number;
  avg_latency: number;
}

export interface AIAnalysis {
  incident_id:  number;
  model_used:   string | null;
  ai_available: boolean;
  message?:     string;
  analysis?: {
    incident_summary:       string;
    likely_cause:           string;
    recommended_checks:     string[];
    investigation_priority: string;
    confidence_labels: {
      likely_cause:       string;
      deployment_related: string;
    };
    debugging_steps: string[];
  };
  statistical_summary?: {
    total_events:   number;
    anomaly_count:  number;
    avg_latency_ms: number;
    max_latency_ms: number;
    error_rate:     number;
  };
}

// ── Fetch helper ───────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

// ── Endpoints ──────────────────────────────────────────────────────────────

export const getSystemStatus      = () => apiFetch<SystemStatus>("/api/status");
export const getRecentLogs        = (limit = 50) => apiFetch<LogEvent[]>(`/api/logs/recent?limit=${limit}`);
export const getAnomalies         = (limit = 100) => apiFetch<LogEvent[]>(`/api/logs/anomalies?limit=${limit}`);
export const getTimeseries        = (minutes = 10) => apiFetch<TimeseriesPoint[]>(`/api/logs/timeseries?minutes=${minutes}`);
export const getIncidents         = (status = "open", limit = 50) => apiFetch<Incident[]>(`/api/incidents?status=${status}&limit=${limit}`);
export const getIncident          = (id: number) => apiFetch<Incident>(`/api/incidents/${id}`);
export const getIncidentLogs      = (id: number, limit = 30) => apiFetch<LogEvent[]>(`/api/incidents/${id}/logs?limit=${limit}`);
export const resolveIncident      = (id: number) => apiFetch<{ success: boolean }>(`/api/incidents/${id}/resolve`, { method: "POST" });
export const getDeployments       = (limit = 20) => apiFetch<Deployment[]>(`/api/deployments?limit=${limit}`);
export const getRecentDeployments = (limit = 5) => apiFetch<Deployment[]>(`/api/deployments/recent?limit=${limit}`);
export const runAIAnalysis        = (id: number) => apiFetch<AIAnalysis>(`/api/ai/analyse/${id}`, { method: "POST" });
export const getAIStatus          = () => apiFetch<SystemStatus["ai"]>("/api/ai/status");