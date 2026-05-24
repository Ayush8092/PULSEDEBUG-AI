/**
 * PulseDebug AI — Custom React Hooks
 * File: frontend/src/hooks/usePolling.ts
 * Purpose:
 *   Reusable hooks wrapping the API client with periodic polling.
 *   Dashboard components always show fresh data without complex state.
 *
 *   useStatus      — system health cards (polls every 3s)
 *   useIncidents   — incident list (polls every 5s)
 *   useTimeseries  — chart data (polls every 4s)
 *   useDeployments — deployment timeline (polls every 10s)
 *   useRecentLogs  — live log feed (polls every 2s)
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  getSystemStatus, getIncidents, getTimeseries,
  getRecentDeployments, getRecentLogs,
  SystemStatus, Incident, TimeseriesPoint, Deployment, LogEvent,
} from "@/lib/api";

// ── Generic polling hook ───────────────────────────────────────────────────

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number,
  initialValue: T,
): { data: T; loading: boolean; error: string | null; refetch: () => void } {
  const [data,    setData]    = useState<T>(initialValue);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const fetch = useCallback(async () => {
    try {
      setData(await fetchFn());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    fetch();
    timerRef.current = setInterval(fetch, intervalMs);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [fetch, intervalMs]);

  return { data, loading, error, refetch: fetch };
}

// ── Specialised hooks ──────────────────────────────────────────────────────

export const useStatus = () =>
  usePolling<SystemStatus | null>(getSystemStatus, 3000, null);

export function useIncidents(status = "open") {
  const fn = useCallback(() => getIncidents(status, 50), [status]);
  return usePolling<Incident[]>(fn, 5000, []);
}

export function useTimeseries(minutes = 10) {
  const fn = useCallback(() => getTimeseries(minutes), [minutes]);
  return usePolling<TimeseriesPoint[]>(fn, 4000, []);
}

export const useDeployments = () =>
  usePolling<Deployment[]>(() => getRecentDeployments(8), 10000, []);

export function useRecentLogs(limit = 40) {
  const fn = useCallback(() => getRecentLogs(limit), [limit]);
  return usePolling<LogEvent[]>(fn, 2000, []);
}