/**
 * PulseDebug AI — Custom React Hooks
 * File: frontend/src/hooks/usePolling.ts
 * Purpose:
 *   Polling hooks plus new SSE hook for real-time streaming.
 *   useSSE — connects to /api/logs/stream and receives pushed events.
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

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Generic polling hook
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

// Specialised hooks
export const useStatus = () =>
  usePolling<SystemStatus | null>(getSystemStatus, 3000, null);

export function useIncidents(
  status   = "open",
  source   = "all",
  severity = "all",
) {
  const fn = useCallback(
    () => getIncidents(status, source, severity, false, 50),
    [status, source, severity]
  );
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

// SSE hook — true real-time streaming via Server-Sent Events
export function useSSELogs(maxItems = 60, source?: string): LogEvent[] {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = `${BASE_URL}/api/logs/stream${source ? `?source=${source}` : ""}`;

    const connect = () => {
      const es = new EventSource(url);
      esRef.current = es;

      es.onmessage = (e) => {
        try {
          const log = JSON.parse(e.data) as LogEvent;
          setLogs((prev) => [log, ...prev].slice(0, maxItems));
        } catch {}
      };

      es.onerror = () => {
        es.close();
        // Reconnect after 3 seconds
        setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      esRef.current?.close();
    };
  }, [source, maxItems]);

  return logs;
}