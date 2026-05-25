/**
 * PulseDebug AI — System Health Cards
 * File: frontend/src/components/dashboard/HealthCards.tsx
 * Purpose:
 *   Four KPI cards with production polish:
 *   - Dynamic intelligent latency subtitle
 *   - Micro-animation on value change (border flash + glow pulse)
 *   - Replaced weak static subtitle with context-sensitive states
 *   - AnimatedValue component for count tween effect
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { TrendingUp, AlertCircle, Clock, Activity } from "lucide-react";
import { SystemStatus } from "@/lib/api";

function latencyLabel(ms: number): string {
  if (ms === 0)     return "Awaiting data";
  if (ms < 150)     return "P95 healthy";
  if (ms < 300)     return "Operational baseline stable";
  if (ms < 600)     return "No anomaly detected";
  if (ms < 1000)    return "Elevated but stable";
  if (ms < 2000)    return "High latency — monitor closely";
  return "Critical latency threshold exceeded";
}

function AnimatedValue({ value }: { value: string | number }) {
  const [display, setDisplay] = useState(value);
  const [flash,   setFlash]   = useState(false);
  const prev = useRef(value);

  useEffect(() => {
    if (prev.current !== value) {
      setFlash(true);
      setDisplay(value);
      prev.current = value;
      const t = setTimeout(() => setFlash(false), 600);
      return () => clearTimeout(t);
    }
  }, [value]);

  return (
    <span
      className="metric-value"
      style={{
        filter: flash ? "brightness(1.5)" : "brightness(1)",
        transition: "filter 0.4s ease",
      }}
    >
      {display}
    </span>
  );
}

interface CardProps {
  label:  string;
  value:  string | number;
  sub:    string;
  icon:   React.ReactNode;
  accent: string;
  trend?: "up" | "down";
}

function MetricCard({ label, value, sub, icon, accent, trend }: CardProps) {
  const [pulse, setPulse] = useState(false);
  const prev = useRef(value);

  useEffect(() => {
    if (prev.current !== value) {
      setPulse(true);
      prev.current = value;
      const t = setTimeout(() => setPulse(false), 800);
      return () => clearTimeout(t);
    }
  }, [value]);

  return (
    <div
      className="card p-5 flex flex-col gap-3 relative overflow-hidden transition-all duration-300"
      style={{
        borderColor: pulse ? accent : `${accent}33`,
        boxShadow:   pulse ? `0 0 18px ${accent}25` : "none",
      }}
    >
      <div
        className="absolute top-0 right-0 w-20 h-20 rounded-full blur-2xl pointer-events-none transition-opacity duration-300"
        style={{
          background: accent,
          transform:  "translate(40%,-40%)",
          opacity:    pulse ? 0.22 : 0.08,
        }}
      />

      <div className="flex items-center justify-between">
        <span className="metric-label">{label}</span>
        <div
          className="p-1.5 rounded-md"
          style={{ background: `${accent}15`, color: accent }}
        >
          {icon}
        </div>
      </div>

      <div className="flex items-end gap-2">
        <span style={{ color: accent }}>
          <AnimatedValue value={value} />
        </span>
        {trend === "up" && (
          <TrendingUp size={14} className="text-[#f85149] mb-0.5" />
        )}
      </div>

      <span className="text-xs text-[#8b949e] font-mono">{sub}</span>
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

export default function HealthCards({
  status,
  loading,
}: {
  status: SystemStatus | null;
  loading: boolean;
}) {
  if (loading || !status) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const errorRate  = (status.error_rate * 100).toFixed(1);
  const isCritical = status.critical_incidents > 0;
  const isWarning  = status.active_incidents > 0 && !isCritical;
  const latMs      = status.avg_latency_ms;

  const incidentSub = isCritical
    ? `${status.critical_incidents} critical`
    : isWarning
    ? "attention needed"
    : "all systems nominal";

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in">
      <MetricCard
        label="Total Requests"
        value={status.total_requests.toLocaleString()}
        sub="since process start"
        icon={<Activity size={14} />}
        accent="#00d4ff"
      />
      <MetricCard
        label="Failed Requests"
        value={status.failed_requests.toLocaleString()}
        sub={`${errorRate}% error rate`}
        icon={<AlertCircle size={14} />}
        accent={
          status.failed_requests === 0
            ? "#3fb950"
            : parseFloat(errorRate) > 10
            ? "#f85149"
            : "#d29922"
        }
        trend={status.failed_requests > 0 ? "up" : undefined}
      />
      <MetricCard
        label="Avg Latency"
        value={`${Math.round(latMs)}ms`}
        sub={latencyLabel(latMs)}
        icon={<Clock size={14} />}
        accent={
          latMs < 300
            ? "#3fb950"
            : latMs < 800
            ? "#d29922"
            : "#f85149"
        }
      />
      <MetricCard
        label="Active Incidents"
        value={status.active_incidents}
        sub={incidentSub}
        icon={<AlertCircle size={14} />}
        accent={
          isCritical ? "#f85149" : isWarning ? "#d29922" : "#3fb950"
        }
        trend={isCritical ? "up" : undefined}
      />
    </div>
  );
}