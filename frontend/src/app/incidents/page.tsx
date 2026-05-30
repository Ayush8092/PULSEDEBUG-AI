/**
 * PulseDebug AI — External Incidents Feed Page
 * File: frontend/src/app/incidents/page.tsx
 * Purpose:
 *   Dedicated filtered incidents feed for external SDK telemetry.
 *   Completely separate from the main dashboard incident feed.
 *   Supports filtering by: all / external / critical / AI analyzed.
 *   Source badges distinguish demo vs external vs manual incidents.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { ArrowLeft, Zap, Layers, Filter, RefreshCw, GitBranch } from "lucide-react";
import { usePolling } from "@/hooks/usePolling";
import { getIncidents, Incident } from "@/lib/api";
import IncidentDetail from "@/components/dashboard/IncidentDetail";

type FilterState = {
  source:     "all" | "external" | "demo" | "manual";
  severity:   "all" | "critical" | "warning" | "investigate";
  aiAnalyzed: boolean;
};

function useRelativeTime(isoString: string): string {
  const [label, setLabel] = useState(() => {
    try {
      const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
      if (diff < 60)    return `${diff}s ago`;
      if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
      return `${Math.floor(diff / 3600)}h ago`;
    } catch { return ""; }
  });
  return label;
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    critical:    "badge-critical",
    warning:     "badge-warning",
    investigate: "badge-investigate",
  };
  return (
    <span className={cls[severity] || "badge-investigate"}>
      {severity.toUpperCase()}
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  const colors: Record<string, { color: string; bg: string; border: string }> = {
    external: { color: "#00d4ff", bg: "rgba(0,212,255,0.08)",   border: "rgba(0,212,255,0.25)" },
    demo:     { color: "#a371f7", bg: "rgba(163,113,247,0.08)", border: "rgba(163,113,247,0.25)" },
    manual:   { color: "#d29922", bg: "rgba(210,153,34,0.08)",  border: "rgba(210,153,34,0.25)" },
  };
  const style = colors[source] || colors.demo;
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono border"
      style={{ color: style.color, background: style.bg, borderColor: style.border }}
    >
      {source}
    </span>
  );
}

function IncidentCard({
  inc,
  selected,
  onSelect,
}: {
  inc: Incident;
  selected: boolean;
  onSelect: () => void;
}) {
  const timeLabel = useRelativeTime(inc.first_detected);

  return (
    <button
      onClick={onSelect}
      className="w-full text-left p-4 card-hover transition-all duration-200"
      style={{
        borderColor: selected ? "#00d4ff" : undefined,
        background:  selected ? "#1c2128" : undefined,
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityBadge severity={inc.severity} />
          <SourceBadge source={inc.source} />
          {inc.ai_summary && (
            <span className="text-xs font-mono text-[#a371f7] border border-[#a371f7]/25 bg-[#a371f7]/8 px-1.5 py-0.5 rounded">
              AI
            </span>
          )}
        </div>
        <span className="font-mono text-xs text-[#484f58] flex-shrink-0">{timeLabel}</span>
      </div>

      <p className="text-sm font-medium text-[#e6edf3] leading-snug mb-2">{inc.title}</p>

      <div className="flex items-center gap-3 flex-wrap">
        <span className="code text-xs">{inc.service}</span>
        <span className="font-mono text-xs text-[#484f58]">{inc.endpoint}</span>
        <span className="font-mono text-xs text-[#8b949e] ml-auto">
          {inc.occurrence_count} events
        </span>
        {inc.deployment_related === 1 && (
          <span className="flex items-center gap-1 text-xs font-mono text-[#d29922]">
            <GitBranch size={10} /> deploy-related
          </span>
        )}
      </div>
    </button>
  );
}

export default function IncidentsFeedPage() {
  const [filters, setFilters] = useState<FilterState>({
    source:     "all",
    severity:   "all",
    aiAnalyzed: false,
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const fetchFn = useCallback(
    () => getIncidents("open", filters.source, filters.severity, filters.aiAnalyzed, 100),
    [filters.source, filters.severity, filters.aiAnalyzed]
  );

  const { data: incidents, loading, refetch } = usePolling(fetchFn, 5000, []);

  const handleResolved = () => {
    setSelectedId(null);
    refetch();
  };

  const externalCount  = incidents.filter((i) => i.source === "external").length;
  const criticalCount  = incidents.filter((i) => i.severity === "critical").length;
  const aiCount        = incidents.filter((i) => i.ai_summary).length;

  return (
    <div className="min-h-screen bg-[#0d1117]">
      <header className="border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2 text-[#8b949e] hover:text-[#e6edf3] transition-colors">
              <ArrowLeft size={14} />
              <span className="text-sm font-mono">Dashboard</span>
            </Link>
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-[#00d4ff]" />
              <span className="font-display font-bold text-[#e6edf3]">PulseDebug</span>
              <span className="font-display font-bold text-[#00d4ff]">AI</span>
              <span className="font-mono text-xs text-[#484f58] ml-1">Incident Feed</span>
            </div>
          </div>
          <button onClick={refetch} className="btn-ghost text-xs flex items-center gap-1.5">
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6 space-y-5">

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Total Open",     value: incidents.length, color: "#00d4ff" },
            { label: "External",       value: externalCount,    color: "#00d4ff" },
            { label: "Critical",       value: criticalCount,    color: "#f85149" },
            { label: "AI Analyzed",    value: aiCount,          color: "#a371f7" },
          ].map((s) => (
            <div key={s.label} className="card p-4" style={{ borderColor: `${s.color}22` }}>
              <p className="metric-label">{s.label}</p>
              <p className="font-display font-bold text-2xl tabular-nums" style={{ color: s.color }}>
                {s.value}
              </p>
            </div>
          ))}
        </div>

        {/* Filter bar */}
        <div className="card p-4 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter size={12} className="text-[#484f58]" />
            <span className="text-xs font-mono text-[#484f58]">Filters</span>
          </div>

          {/* Source filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs font-mono text-[#484f58] mr-1">Source:</span>
            {(["all", "external", "demo", "manual"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilters((f) => ({ ...f, source: s }))}
                className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                  filters.source === s
                    ? "bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/30"
                    : "text-[#484f58] hover:text-[#8b949e] border border-transparent"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Severity filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs font-mono text-[#484f58] mr-1">Severity:</span>
            {(["all", "critical", "warning", "investigate"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setFilters((f) => ({ ...f, severity: s }))}
                className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                  filters.severity === s
                    ? "bg-[#a371f7]/10 text-[#a371f7] border border-[#a371f7]/30"
                    : "text-[#484f58] hover:text-[#8b949e] border border-transparent"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {/* AI analyzed toggle */}
          <button
            onClick={() => setFilters((f) => ({ ...f, aiAnalyzed: !f.aiAnalyzed }))}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono border transition-all ${
              filters.aiAnalyzed
                ? "bg-[#a371f7]/10 text-[#a371f7] border-[#a371f7]/30"
                : "text-[#484f58] border-transparent hover:text-[#8b949e]"
            }`}
          >
            AI Analyzed Only
          </button>
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">

          {/* Incident list */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 mb-3">
              <Layers size={14} className="text-[#00d4ff]" />
              <span className="text-sm font-medium text-[#e6edf3]">
                Incidents
              </span>
              <span className="font-mono text-xs text-[#484f58] ml-auto">
                {incidents.length} results
              </span>
            </div>

            {loading && incidents.length === 0 && (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="card p-4 space-y-2">
                    <div className="h-3 w-40 bg-[#21262d] rounded animate-pulse" />
                    <div className="h-3 w-64 bg-[#21262d] rounded animate-pulse" />
                  </div>
                ))}
              </div>
            )}

            {!loading && incidents.length === 0 && (
              <div className="card p-8 text-center">
                <div className="text-[#3fb950] text-2xl mb-2">✓</div>
                <p className="text-sm text-[#8b949e]">No incidents match the current filters</p>
              </div>
            )}

            {incidents.map((inc) => (
              <IncidentCard
                key={inc.id}
                inc={inc}
                selected={selectedId === inc.id}
                onSelect={() =>
                  setSelectedId(inc.id === selectedId ? null : inc.id)
                }
              />
            ))}
          </div>

          {/* Detail panel */}
          <div className="xl:sticky xl:top-20 xl:self-start">
            {selectedId ? (
              <IncidentDetail
                incidentId={selectedId}
                onResolved={handleResolved}
              />
            ) : (
              <div className="card p-8 text-center">
                <Layers size={28} className="text-[#30363d] mx-auto mb-3" />
                <p className="text-sm text-[#8b949e]">Select an incident to view details</p>
                <p className="text-xs text-[#484f58] mt-1 font-mono">
                  Timeline, correlation graph, and AI diagnosis
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}