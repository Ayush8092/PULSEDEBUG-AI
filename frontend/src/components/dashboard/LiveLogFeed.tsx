/**
 * PulseDebug AI — Live Log Feed
 * File: frontend/src/components/dashboard/LiveLogFeed.tsx
 * Purpose:
 *   Terminal-style scrolling log feed. Production polish:
 *   - Browser-local time for all timestamps
 *   - Anomalous events highlighted with red left border
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useEffect, useRef } from "react";
import { LogEvent } from "@/lib/api";

const statusColor  = (c: number) =>
  c >= 500 ? "#f85149" : c >= 400 ? "#d29922" : "#3fb950";
const latencyColor = (ms: number) =>
  ms > 3000 ? "#f85149" : ms > 800 ? "#d29922" : "#8b949e";

function localTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour:   "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "--:--:--";
  }
}

export default function LiveLogFeed({ logs }: { logs: LogEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="card flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#30363d]">
        <div className="flex items-center gap-2">
          <span className="live-dot" />
          <span className="font-mono text-xs text-[#3fb950]">LIVE</span>
          <span className="font-mono text-xs text-[#484f58] ml-1">
            API Event Stream
          </span>
        </div>
        <span className="font-mono text-xs text-[#484f58]">
          {logs.length} events
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-0.5 bg-[#0d1117]">
        {logs.length === 0 && (
          <div className="text-[#484f58] py-4 text-center">
            Waiting for events
            <span className="animate-blink">_</span>
          </div>
        )}

        {[...logs].reverse().map((log) => (
          <div
            key={log.id}
            className={`flex items-start gap-2 py-0.5 px-1 rounded ${
              log.is_anomaly
                ? "bg-[#f85149]/5 border-l-2 border-[#f85149]/40 pl-2"
                : ""
            }`}
          >
            <span className="text-[#484f58] flex-shrink-0 w-[58px]">
              {localTime(log.timestamp)}
            </span>
            <span className="text-[#00d4ff] flex-shrink-0 w-[120px] truncate">
              {log.service}
            </span>
            <span className="text-[#8b949e] flex-shrink-0 w-[160px] truncate">
              {log.endpoint}
            </span>
            <span
              className="flex-shrink-0 w-[36px] font-bold"
              style={{ color: statusColor(log.status_code) }}
            >
              {log.status_code}
            </span>
            <span
              className="flex-shrink-0 w-[56px] text-right"
              style={{ color: latencyColor(log.latency_ms) }}
            >
              {log.latency_ms}ms
            </span>
            {log.error_type && (
              <span className="text-[#f85149] truncate flex-1">
                ⚠ {log.error_type}
              </span>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}