/**
 * PulseDebug AI — External Incidents Feed Page
 * File: frontend/src/app/incidents/page.tsx
 * Purpose:
 *   Dedicated filtered incidents feed with sliding pill-style toggle
 *   filters replacing the old button rows. Users slide between options
 *   using animated selector pills for Source, Severity, and AI filter.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  ArrowLeft, Zap, Layers, RefreshCw, GitBranch, Brain,
} from "lucide-react";
import { usePolling } from "@/hooks/usePolling";
import { getIncidents, Incident } from "@/lib/api";
import IncidentDetail from "@/components/dashboard/IncidentDetail";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SourceFilter   = "all" | "external" | "demo" | "manual";
type SeverityFilter = "all" | "critical" | "warning" | "investigate";

// ---------------------------------------------------------------------------
// Sliding Toggle Component
// ---------------------------------------------------------------------------

function SlidingToggle<T extends string>({
  label,
  options,
  value,
  onChange,
  colorMap,
}: {
  label:    string;
  options:  { value: T; label: string }[];
  value:    T;
  onChange: (v: T) => void;
  colorMap?: Record<string, string>;
}) {
  const activeIdx  = options.findIndex((o) => o.value === value);
  const activeColor = colorMap?.[value] || "#00d4ff";

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-mono text-[#484f58] uppercase tracking-widest">
        {label}
      </span>
      <div
        className="relative flex rounded-lg p-0.5 gap-0"
        style={{ background: "#0d1117", border: "1px solid #30363d" }}
      >
        {/* Sliding background pill */}
        <div
          className="absolute top-0.5 bottom-0.5 rounded-md transition-all duration-250 ease-out"
          style={{
            width:      `${100 / options.length}%`,
            left:       `calc(${(activeIdx / options.length) * 100}% + 2px)`,
            background: `${activeColor}18`,
            border:     `1px solid ${activeColor}40`,
            boxShadow:  `0 0 8px ${activeColor}20`,
          }}
        />

        {options.map((opt) => {
          const isActive   = opt.value === value;
          const optColor   = colorMap?.[opt.value] || "#8b949e";
          return (
            <button
              key={opt.value}
              onClick={() => onChange(opt.value)}
              className="relative z-10 flex-1 px-3 py-1.5 text-xs font-mono rounded-md transition-colors duration-150 whitespace-nowrap"
              style={{ color: isActive ? optColor : "#484f58" }}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI Toggle (single on/off sliding switch)
// ---------------------------------------------------------------------------

function AIToggle({
  value,
  onChange,
}: {
  value:    boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-mono text-[#484f58] uppercase tracking-widest">
        AI Filter
      </span>
      <button
        onClick={() => onChange(!value)}
        className="relative flex items-center rounded-lg p-0.5 transition-all duration-200"
        style={{
          background:  value ? "rgba(163,113,247,0.10)" : "#0d1117",
          border:      value ? "1px solid rgba(163,113,247,0.35)" : "1px solid #30363d",
          boxShadow:   value ? "0 0 10px rgba(163,113,247,0.15)" : "none",
        }}
      >
        {/* Track */}
        <div className="relative mx-1 w-8 h-4 rounded-full transition-colors duration-200"
             style={{ background: value ? "rgba(163,113,247,0.4)" : "#21262d" }}>
          {/* Knob */}
          <div
            className="absolute top-0.5 w-3 h-3 rounded-full transition-all duration-200"
            style={{
              left:       value ? "calc(100% - 14px)" : "2px",
              background: value ? "#a371f7" : "#484f58",
              boxShadow:  value ? "0 0 6px rgba(163,113,247,0.6)" : "none",
            }}
          />
        </div>
        <span
          className="pr-2 pl-1 text-xs font-mono transition-colors duration-150"
          style={{ color: value ? "#a371f7" : "#484f58" }}
        >
          AI Analyzed Only
        </span>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Relative time hook
// ---------------------------------------------------------------------------

function timeAgo(isoString: string): string {
  try {
    const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diff < 60)    return `${diff}s ago`;
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch { return ""; }
}

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------

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
  const styles: Record<string, { color: string; bg: string; border: string }> = {
    external: { color: "#00d4ff", bg: "rgba(0,212,255,0.08)",   border: "rgba(0,212,255,0.25)" },
    demo:     { color: "#a371f7", bg: "rgba(163,113,247,0.08)", border: "rgba(163,113,247,0.25)" },
    manual:   { color: "#d29922", bg: "rgba(210,153,34,0.08)",  border: "rgba(210,153,34,0.25)" },
  };
  const s = styles[source] || styles.demo;
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono border"
      style={{ color: s.color, background: s.bg, borderColor: s.border }}
    >
      {source}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Incident card
// ---------------------------------------------------------------------------

function IncidentCard({
  inc,
  selected,
  onSelect,
}: {
  inc:      Incident;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className="w-full text-left p-4 rounded-lg border transition-all duration-150 hover:bg-[#1c2128]"
      style={{
        background:  selected ? "#1c2128"  : "#161b22",
        borderColor: selected ? "#00d4ff"  : "#30363d",
        boxShadow:   selected ? "0 0 12px rgba(0,212,255,0.08)" : "none",
      }}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityBadge severity={inc.severity} />
          <SourceBadge source={inc.source} />
          {inc.ai_summary && (
            <span className="flex items-center gap-1 text-xs font-mono text-[#a371f7] border border-[#a371f7]/25 bg-[#a371f7]/8 px-1.5 py-0.5 rounded">
              <Brain size={9} /> AI
            </span>
          )}
        </div>
        <span className="font-mono text-xs text-[#484f58] flex-shrink-0 mt-0.5">
          {timeAgo(inc.first_detected)}
        </span>
      </div>

      {/* Title */}
      <p className="text-sm font-medium text-[#e6edf3] leading-snug mb-2">
        {inc.title}
      </p>

      {/* Meta row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="code text-xs">{inc.service}</span>
        <span className="font-mono text-xs text-[#484f58] truncate max-w-[160px]">
          {inc.endpoint}
        </span>
        <div className="ml-auto flex items-center gap-3">
          <span className="font-mono text-xs text-[#8b949e]">
            {inc.occurrence_count} events
          </span>
          {inc.deployment_related === 1 && (
            <span className="flex items-center gap-1 text-xs font-mono text-[#d29922]">
              <GitBranch size={9} /> deploy
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function IncidentsFeedPage() {
  const [source,     setSource]     = useState<SourceFilter>("all");
  const [severity,   setSeverity]   = useState<SeverityFilter>("all");
  const [aiAnalyzed, setAiAnalyzed] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const fetchFn = useCallback(
    () => getIncidents("open", source, severity, aiAnalyzed, 100),
    [source, severity, aiAnalyzed]
  );

  const { data: incidents, loading, refetch } = usePolling(fetchFn, 5000, []);

  const handleResolved = () => {
    setSelectedId(null);
    refetch();
  };

  const externalCount = incidents.filter((i) => i.source === "external").length;
  const criticalCount = incidents.filter((i) => i.severity === "critical").length;
  const aiCount       = incidents.filter((i) => !!i.ai_summary).length;

  // ---------------------------------------------------------------------------
  // Color maps for sliding toggles
  // ---------------------------------------------------------------------------

  const sourceColors: Record<string, string> = {
    all:      "#00d4ff",
    external: "#00d4ff",
    demo:     "#a371f7",
    manual:   "#d29922",
  };

  const severityColors: Record<string, string> = {
    all:         "#00d4ff",
    critical:    "#f85149",
    warning:     "#d29922",
    investigate: "#a371f7",
  };

  return (
    <div className="min-h-screen bg-[#0d1117]">

      {/* Header */}
      <header className="border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-[#8b949e] hover:text-[#e6edf3] transition-colors"
            >
              <ArrowLeft size={14} />
              <span className="text-sm font-mono">Dashboard</span>
            </Link>
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-[#00d4ff]" />
              <span className="font-display font-bold text-[#e6edf3]">
                PulseDebug
              </span>
              <span className="font-display font-bold text-[#00d4ff]">AI</span>
              <span className="font-mono text-xs text-[#484f58] ml-1">
                Incident Feed
              </span>
            </div>
          </div>
          <button
            onClick={refetch}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={11} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6 space-y-5">

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Total Open",  value: incidents.length, color: "#00d4ff" },
            { label: "External",    value: externalCount,    color: "#00d4ff" },
            { label: "Critical",    value: criticalCount,    color: "#f85149" },
            { label: "AI Analyzed", value: aiCount,          color: "#a371f7" },
          ].map((s) => (
            <div
              key={s.label}
              className="card p-4"
              style={{ borderColor: `${s.color}22` }}
            >
              <p className="metric-label">{s.label}</p>
              <p
                className="font-display font-bold text-2xl tabular-nums"
                style={{ color: s.color }}
              >
                {s.value}
              </p>
            </div>
          ))}
        </div>

        {/* ── Sliding filter panel ── */}
        <div className="card p-5 space-y-4">
          <p className="text-xs font-mono text-[#484f58] uppercase tracking-widest">
            Filter Incidents
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 items-end">

            {/* Source toggle */}
            <SlidingToggle
              label="Source"
              options={[
                { value: "all",      label: "All"      },
                { value: "external", label: "External" },
                { value: "demo",     label: "Demo"     },
                { value: "manual",   label: "Manual"   },
              ]}
              value={source}
              onChange={setSource}
              colorMap={sourceColors}
            />

            {/* Severity toggle */}
            <SlidingToggle
              label="Severity"
              options={[
                { value: "all",         label: "All"     },
                { value: "critical",    label: "Crit"    },
                { value: "warning",     label: "Warn"    },
                { value: "investigate", label: "Invest"  },
              ]}
              value={severity}
              onChange={setSeverity}
              colorMap={severityColors}
            />

            {/* AI analyzed toggle switch */}
            <AIToggle value={aiAnalyzed} onChange={setAiAnalyzed} />
          </div>

          {/* Active filters summary */}
          {(source !== "all" || severity !== "all" || aiAnalyzed) && (
            <div className="flex items-center gap-2 flex-wrap pt-1">
              <span className="text-xs font-mono text-[#484f58]">Active:</span>
              {source !== "all" && (
                <span
                  className="text-xs font-mono px-2 py-0.5 rounded border"
                  style={{ color: sourceColors[source], borderColor: `${sourceColors[source]}30`, background: `${sourceColors[source]}10` }}
                >
                  source: {source}
                </span>
              )}
              {severity !== "all" && (
                <span
                  className="text-xs font-mono px-2 py-0.5 rounded border"
                  style={{ color: severityColors[severity], borderColor: `${severityColors[severity]}30`, background: `${severityColors[severity]}10` }}
                >
                  severity: {severity}
                </span>
              )}
              {aiAnalyzed && (
                <span className="text-xs font-mono px-2 py-0.5 rounded border text-[#a371f7] border-[#a371f7]/30 bg-[#a371f7]/10">
                  AI analyzed
                </span>
              )}
              <button
                onClick={() => { setSource("all"); setSeverity("all"); setAiAnalyzed(false); }}
                className="text-xs font-mono text-[#484f58] hover:text-[#e6edf3] transition-colors ml-1 underline"
              >
                Clear all
              </button>
            </div>
          )}
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">

          {/* Incident list */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 mb-3">
              <Layers size={14} className="text-[#00d4ff]" />
              <span className="text-sm font-medium text-[#e6edf3]">
                Incidents
              </span>
              <span className="font-mono text-xs text-[#484f58] ml-auto">
                {loading ? "loading…" : `${incidents.length} result${incidents.length !== 1 ? "s" : ""}`}
              </span>
            </div>

            {/* Skeleton loader */}
            {loading && incidents.length === 0 && (
              <div className="space-y-2">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="card p-4 space-y-2">
                    <div className="h-3 w-40 bg-[#21262d] rounded animate-pulse" />
                    <div className="h-3 w-64 bg-[#21262d] rounded animate-pulse" />
                    <div className="h-3 w-32 bg-[#21262d] rounded animate-pulse" />
                  </div>
                ))}
              </div>
            )}

            {/* Empty state */}
            {!loading && incidents.length === 0 && (
              <div className="card p-8 text-center">
                <div className="text-[#3fb950] text-2xl mb-2">✓</div>
                <p className="text-sm text-[#8b949e]">
                  No incidents match the current filters
                </p>
                <button
                  onClick={() => { setSource("all"); setSeverity("all"); setAiAnalyzed(false); }}
                  className="btn-ghost text-xs mt-3 mx-auto"
                >
                  Clear filters
                </button>
              </div>
            )}

            {/* Incident cards */}
            <div className="space-y-2">
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
          </div>

          {/* Detail panel */}
          <div className="xl:sticky xl:top-20 xl:self-start">
            {selectedId ? (
              <IncidentDetail
                incidentId={selectedId}
                onResolved={handleResolved}
              />
            ) : (
              <div className="card p-10 text-center">
                <Layers size={32} className="text-[#21262d] mx-auto mb-4" />
                <p className="text-sm text-[#8b949e]">
                  Select an incident to view details
                </p>
                <p className="text-xs text-[#484f58] mt-1.5 font-mono leading-relaxed">
                  Timeline replay · Correlation graph<br />
                  AI diagnosis · Fix commands
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}