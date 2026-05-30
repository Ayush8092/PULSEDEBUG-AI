/**
 * PulseDebug AI — API Client
 * File: frontend/src/lib/api.ts
 * Purpose:
 *   Typed API client. Upgrade additions:
 *   - source filtering on incidents and logs
 *   - timeline endpoint
 *   - correlation graph endpoint
 *   - fix commands on AIAnalysis type
 *   - confidence_score on analysis response
 *
 * Author: PulseDebug AI Hackathon Team
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SystemStatus {
  total_requests:     number;
  failed_requests:    number;
  avg_latency_ms:     number;
  active_incidents:   number;
  critical_incidents: number;
  external_incidents: number;
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
  source:      string;
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
  source:            string;
  deployment:        Deployment | null;
  ai_summary:        string | null;
  ai_root_cause:     string | null;
  ai_checks:         string | null;
  ai_priority:       string | null;
  ai_model_used:     string | null;
  ai_confidence:     number | null;
  ai_fix_commands:   string | null;
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

export interface TimelineEvent {
  id:         number;
  incident_id:number;
  timestamp:  string;
  event_type: string;
  title:      string;
  detail:     string | null;
  icon?:      string;
  color?:     string;
  label?:     string;
}

export interface CorrelationGraph {
  nodes: Array<{
    id:           number;
    title:        string;
    service:      string;
    severity:     string;
    error_signature: string;
    status:       string;
    is_root:      boolean;
  }>;
  edges: Array<{
    from:          number;
    to:            number;
    relation_type: string;
    confidence:    number;
  }>;
}

export interface FixCommand {
  language: string;
  title:    string;
  code:     string;
}

export interface AIAnalysis {
  incident_id:      number;
  model_used:       string | null;
  ai_available:     boolean;
  message?:         string;
  confidence_score?: number;
  fix_commands?:    FixCommand[];
  regression_info?: {
    regression_detected: boolean;
    errors_before:       number;
    errors_after:        number;
    increase_pct:        number;
    deployment_version:  string;
    deployed_at:         string;
  };
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

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

// Health
export const getSystemStatus = () => apiFetch<SystemStatus>("/api/status");

// Logs
export const getRecentLogs   = (limit = 50, source?: string) =>
  apiFetch<LogEvent[]>(`/api/logs/recent?limit=${limit}${source ? `&source=${source}` : ""}`);
export const getTimeseries   = (minutes = 10) =>
  apiFetch<TimeseriesPoint[]>(`/api/logs/timeseries?minutes=${minutes}`);

// Incidents — with filter support
export const getIncidents = (
  status   = "open",
  source   = "all",
  severity = "all",
  aiAnalyzed = false,
  limit    = 50,
) =>
  apiFetch<Incident[]>(
    `/api/incidents?status=${status}&source=${source}&severity=${severity}&ai_analyzed=${aiAnalyzed}&limit=${limit}`
  );

export const getIncident      = (id: number) => apiFetch<Incident>(`/api/incidents/${id}`);
export const getIncidentLogs  = (id: number, limit = 30) =>
  apiFetch<LogEvent[]>(`/api/incidents/${id}/logs?limit=${limit}`);
export const getTimeline      = (id: number) =>
  apiFetch<TimelineEvent[]>(`/api/incidents/${id}/timeline`);
export const getCorrelation   = (id: number) =>
  apiFetch<CorrelationGraph>(`/api/incidents/${id}/correlation`);
export const resolveIncident  = (id: number) =>
  apiFetch<{ success: boolean }>(`/api/incidents/${id}/resolve`, { method: "POST" });

// Deployments
export const getDeployments       = (limit = 20) => apiFetch<Deployment[]>(`/api/deployments?limit=${limit}`);
export const getRecentDeployments = (limit = 5)  => apiFetch<Deployment[]>(`/api/deployments/recent?limit=${limit}`);

// AI
export const runAIAnalysis = (id: number) =>
  apiFetch<AIAnalysis>(`/api/ai/analyse/${id}`, { method: "POST" });
export const getAIStatus   = () => apiFetch<SystemStatus["ai"]>("/api/ai/status");