/**
 * PulseDebug AI — System Health Cards
 * File: frontend/src/components/dashboard/HealthCards.tsx
 * Purpose:
 *   Four KPI cards: Total Requests, Failed Requests, Avg Latency, Active Incidents.
 *   Cards colour-shift based on health state (green → yellow → red).
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { TrendingUp, TrendingDown, AlertCircle, Clock, Activity } from "lucide-react";
import { SystemStatus } from "@/lib/api";

interface CardProps {
  label:  string;
  value:  string | number;
  sub?:   string;
  icon:   React.ReactNode;
  accent: string;
  trend?: "up" | "down";
}

function MetricCard({ label, value, sub, icon, accent, trend }: CardProps) {
  return (
    <div className="card p-5 flex flex-col gap-3 relative overflow-hidden" style={{ borderColor: `${accent}33` }}>
      <div className="absolute top-0 right-0 w-20 h-20 rounded-full blur-2xl opacity-10 pointer-events-none"
           style={{ background: accent, transform: "translate(40%,-40%)" }} />
      <div className="flex items-center justify-between">
        <span className="metric-label">{label}</span>
        <div className="p-1.5 rounded-md" style={{ background: `${accent}15`, color: accent }}>{icon}</div>
      </div>
      <div className="flex items-end gap-2">
        <span className="metric-value" style={{ color: accent }}>{value}</span>
        {trend === "up"   && <TrendingUp   size={14} className="text-[#f85149] mb-0.5" />}
        {trend === "down" && <TrendingDown size={14} className="text-[#3fb950] mb-0.5" />}
      </div>
      {sub && <span className="text-xs text-[#8b949e] font-mono">{sub}</span>}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="card p-5 flex flex-col gap-3">
      <div className="h-3 w-24 bg-[#21262d] rounded animate-pulse" />
      <div className="h-8 w-20 bg-[#21262d] rounded animate-pulse" />
      <div className="h-3 w-32 bg-[#21262d] rounded animate-pulse" />
    </div>
  );
}

export default function HealthCards({ status, loading }: { status: SystemStatus | null; loading: boolean }) {
  if (loading || !status) {
    return <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{[...Array(4)].map((_,i) => <SkeletonCard key={i} />)}</div>;
  }

  const errorRate  = (status.error_rate * 100).toFixed(1);
  const isCritical = status.critical_incidents > 0;
  const isWarning  = status.active_incidents > 0 && !isCritical;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in">
      <MetricCard label="Total Requests" value={status.total_requests.toLocaleString()}
        sub="since process start" icon={<Activity size={14} />} accent="#00d4ff" />
      <MetricCard label="Failed Requests" value={status.failed_requests.toLocaleString()}
        sub={`${errorRate}% error rate`} icon={<AlertCircle size={14} />}
        accent={status.failed_requests === 0 ? "#3fb950" : parseFloat(errorRate) > 10 ? "#f85149" : "#d29922"}
        trend={status.failed_requests > 0 ? "up" : undefined} />
      <MetricCard label="Avg Latency" value={`${Math.round(status.avg_latency_ms)}ms`}
        sub={status.avg_latency_ms > 1000 ? "⚠ above threshold" : "within normal range"}
        icon={<Clock size={14} />}
        accent={status.avg_latency_ms < 300 ? "#3fb950" : status.avg_latency_ms < 800 ? "#d29922" : "#f85149"} />
      <MetricCard label="Active Incidents" value={status.active_incidents}
        sub={isCritical ? `${status.critical_incidents} critical` : isWarning ? "attention needed" : "all systems normal"}
        icon={<AlertCircle size={14} />}
        accent={isCritical ? "#f85149" : isWarning ? "#d29922" : "#3fb950"}
        trend={isCritical ? "up" : undefined} />
    </div>
  );
}