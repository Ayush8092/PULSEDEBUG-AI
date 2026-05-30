/**
 * PulseDebug AI — Incident Detail Panel
 * File: frontend/src/components/dashboard/IncidentDetail.tsx
 * Purpose:
 *   Full incident detail panel. Upgrade additions:
 *   - AI Confidence Score visualization with animated bar
 *   - AI-generated fix commands with syntax-highlighted code blocks
 *   - Deployment regression detection banner
 *   - Incident Timeline Replay visualization
 *   - Root-cause correlation graph (text-based)
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useEffect } from "react";
import {
  Brain, GitBranch, CheckCircle, AlertTriangle,
  Loader2, ChevronDown, ChevronUp, Terminal,
  Package, Clock, Copy, Check, TrendingUp,
} from "lucide-react";
import {
  getIncident, getIncidentLogs, getTimeline, getCorrelation,
  runAIAnalysis, resolveIncident,
  Incident, LogEvent, AIAnalysis, TimelineEvent, CorrelationGraph, FixCommand,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function localTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  } catch { return iso; }
}

function timeAgo(iso: string): string {
  try {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60)   return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  } catch { return iso; }
}

// ---------------------------------------------------------------------------
// Confidence label → numeric score
// ---------------------------------------------------------------------------

const CONFIDENCE_VALUES: Record<string, number> = {
  "High Likelihood":     85,
  "Moderate Likelihood": 60,
  "Needs Investigation": 35,
  "Not Related":         15,
};

const CONFIDENCE_COLORS: Record<string, string> = {
  "High Likelihood":     "#3fb950",
  "Moderate Likelihood": "#d29922",
  "Needs Investigation": "#a371f7",
  "Not Related":         "#484f58",
};

// ---------------------------------------------------------------------------
// AI Confidence Score Bar
// ---------------------------------------------------------------------------

function ConfidenceBar({
  label,
  score,
}: {
  label: string;
  score: number;
}) {
  const [width, setWidth] = useState(0);
  const color = CONFIDENCE_COLORS[label] || "#a371f7";

  useEffect(() => {
    const t = setTimeout(() => setWidth(score), 200);
    return () => clearTimeout(t);
  }, [score]);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs font-mono">
        <span style={{ color }} className="font-medium">{label}</span>
        <span style={{ color }} className="tabular-nums">{score}%</span>
      </div>
      <div className="h-2 rounded-full bg-[#21262d] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width:      `${width}%`,
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            boxShadow:  `0 0 8px ${color}66`,
          }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fix Commands code block
// ---------------------------------------------------------------------------

function FixCommandBlock({ cmd }: { cmd: FixCommand }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(cmd.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const langColors: Record<string, string> = {
    python:     "#3fb950",
    yaml:       "#00d4ff",
    bash:       "#d29922",
    javascript: "#f0db4f",
  };
  const langColor = langColors[cmd.language.toLowerCase()] || "#8b949e";

  return (
    <div className="rounded-lg border border-[#30363d] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-[#161b22] border-b border-[#30363d]">
        <div className="flex items-center gap-2">
          <span
            className="font-mono text-xs px-1.5 py-0.5 rounded"
            style={{ background: `${langColor}18`, color: langColor }}
          >
            {cmd.language}
          </span>
          <span className="text-xs text-[#8b949e] font-mono">{cmd.title}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs font-mono text-[#484f58] hover:text-[#e6edf3] transition-colors"
        >
          {copied ? (
            <><Check size={11} className="text-[#3fb950]" /><span className="text-[#3fb950]">Copied</span></>
          ) : (
            <><Copy size={11} /><span>Copy</span></>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto bg-[#0d1117] text-xs font-mono text-[#c9d1d9] leading-relaxed">
        <code>{cmd.code}</code>
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Timeline Replay
// ---------------------------------------------------------------------------

function TimelineReplay({ events }: { events: TimelineEvent[] }) {
  if (!events.length) {
    return (
      <p className="text-xs font-mono text-[#484f58]">
        No timeline events yet<span className="animate-blink">_</span>
      </p>
    );
  }

  return (
    <div className="relative space-y-0 pl-6">
      {/* Vertical line */}
      <div className="absolute left-[9px] top-2 bottom-2 w-px bg-[#30363d]" />

      {events.map((ev, i) => {
        const color = ev.color || "#8b949e";
        return (
          <div key={ev.id} className="relative flex items-start gap-3 pb-4 animate-fade-in"
               style={{ animationDelay: `${i * 80}ms` }}>
            {/* Node */}
            <div
              className="absolute left-[-18px] w-4 h-4 rounded-full border-2 flex items-center justify-center bg-[#0d1117] flex-shrink-0 mt-0.5"
              style={{ borderColor: color }}
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium" style={{ color }}>
                  {ev.label || ev.event_type.replace(/_/g, " ")}
                </span>
                <span className="text-xs font-mono text-[#484f58]">
                  {new Date(ev.timestamp).toLocaleTimeString([], {
                    hour: "2-digit", minute: "2-digit", second: "2-digit",
                  })}
                </span>
              </div>
              <p className="text-xs text-[#8b949e] mt-0.5">{ev.title}</p>
              {ev.detail && (
                <p className="text-xs text-[#484f58] mt-0.5 font-mono leading-relaxed">
                  {ev.detail}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root-Cause Correlation Graph (text-based)
// ---------------------------------------------------------------------------

function CorrelationView({ graph }: { graph: CorrelationGraph }) {
  if (!graph.edges.length) {
    return (
      <p className="text-xs font-mono text-[#484f58]">
        No correlated incidents found
      </p>
    );
  }

  const nodeMap = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));

  return (
    <div className="space-y-2">
      {graph.edges.map((edge, i) => {
        const from  = nodeMap[edge.from];
        const to    = nodeMap[edge.to];
        const pct   = Math.round(edge.confidence * 100);

        return (
          <div key={i} className="flex items-center gap-2 text-xs font-mono">
            <div
              className="px-2 py-1 rounded border truncate max-w-[180px]"
              style={{
                borderColor: from?.is_root ? "#a371f7" : "#30363d",
                color:       from?.is_root ? "#a371f7" : "#8b949e",
              }}
            >
              {from?.service || `#${edge.from}`}
            </div>
            <div className="flex flex-col items-center">
              <span className="text-[#484f58]">↓</span>
              <span className="text-[9px] text-[#484f58]">{edge.relation_type}</span>
              <span className="text-[9px]" style={{
                color: pct >= 80 ? "#3fb950" : pct >= 60 ? "#d29922" : "#a371f7"
              }}>{pct}%</span>
            </div>
            <div
              className="px-2 py-1 rounded border truncate max-w-[180px]"
              style={{
                borderColor: to?.is_root ? "#a371f7" : "#30363d",
                color:       to?.is_root ? "#a371f7" : "#8b949e",
              }}
            >
              {to?.service || `#${edge.to}`}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gemini loading skeleton
// ---------------------------------------------------------------------------

const THINKING_MESSAGES = [
  "Thinking through deployment correlations…",
  "Analysing error signature patterns…",
  "Correlating with recent deployments…",
  "Generating root-cause hypothesis…",
  "Preparing debugging recommendations…",
  "Generating fix commands…",
];

function GeminiSkeleton() {
  const [msgIdx, setMsgIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setMsgIdx((i) => (i + 1) % THINKING_MESSAGES.length), 2200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="rounded-lg border border-[#a371f7]/20 bg-[#a371f7]/5 p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Loader2 size={13} className="text-[#a371f7] animate-spin flex-shrink-0" />
        <span className="text-xs font-mono text-[#a371f7]">{THINKING_MESSAGES[msgIdx]}</span>
      </div>
      <div className="space-y-2">
        {[80, 95, 65, 85, 50].map((w, i) => (
          <div key={i} className="h-2.5 rounded animate-pulse"
               style={{ width: `${w}%`, background: "rgba(163,113,247,0.15)", animationDelay: `${i * 120}ms` }} />
        ))}
      </div>
    </div>
  );
}

function ConfidenceLabel({ label }: { label: string }) {
  const color = CONFIDENCE_COLORS[label] || "#8b949e";
  return (
    <span className="inline-flex px-1.5 py-0.5 rounded text-xs font-mono border"
          style={{ color, borderColor: `${color}33`, background: `${color}10` }}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface Props {
  incidentId:    number;
  onResolved:    () => void;
  onAIComplete?: () => void;
}

export default function IncidentDetail({ incidentId, onResolved, onAIComplete }: Props) {
  const [incident,    setIncident]    = useState<Incident | null>(null);
  const [logs,        setLogs]        = useState<LogEvent[]>([]);
  const [analysis,    setAnalysis]    = useState<AIAnalysis | null>(null);
  const [timeline,    setTimeline]    = useState<TimelineEvent[]>([]);
  const [correlation, setCorrelation] = useState<CorrelationGraph | null>(null);
  const [loadingInc,  setLoadingInc]  = useState(true);
  const [loadingAI,   setLoadingAI]   = useState(false);
  const [resolving,   setResolving]   = useState(false);
  const [showLogs,    setShowLogs]    = useState(false);
  const [activeTab,   setActiveTab]   = useState<"diagnosis"|"timeline"|"correlation"|"fixes">("diagnosis");

  useEffect(() => {
    setLoadingInc(true);
    setAnalysis(null);
    setActiveTab("diagnosis");

    Promise.all([
      getIncident(incidentId),
      getIncidentLogs(incidentId, 20),
      getTimeline(incidentId),
      getCorrelation(incidentId),
    ]).then(([inc, logData, timelineData, corrData]) => {
      setIncident(inc);
      setLogs(logData);
      setTimeline(timelineData);
      setCorrelation(corrData);
      if (inc.ai_summary) {
        const fixCommands = inc.ai_fix_commands ? JSON.parse(inc.ai_fix_commands) : [];
        setAnalysis({
          incident_id:      incidentId,
          model_used:       inc.ai_model_used,
          ai_available:     true,
          confidence_score: inc.ai_confidence || undefined,
          fix_commands:     fixCommands,
          analysis: {
            incident_summary:       inc.ai_summary!,
            likely_cause:           inc.ai_root_cause || "",
            recommended_checks:     JSON.parse(inc.ai_checks || "[]"),
            investigation_priority: inc.ai_priority || "Medium",
            confidence_labels: {
              likely_cause:       "High Likelihood",
              deployment_related: "High Likelihood",
            },
            debugging_steps: [],
          },
        });
      }
    }).finally(() => setLoadingInc(false));
  }, [incidentId]);

  // Poll timeline for new events every 10s
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const data = await getTimeline(incidentId);
        setTimeline(data);
      } catch {}
    }, 10_000);
    return () => clearInterval(t);
  }, [incidentId]);

  const handleAnalyse = async () => {
    setLoadingAI(true);
    try {
      const result = await runAIAnalysis(incidentId);
      setAnalysis(result);
      const tl = await getTimeline(incidentId);
      setTimeline(tl);
      if (result.ai_available && onAIComplete) onAIComplete();
    } finally {
      setLoadingAI(false);
    }
  };

  const handleResolve = async () => {
    if (!incident) return;
    setResolving(true);
    try { await resolveIncident(incidentId); onResolved(); }
    finally { setResolving(false); }
  };

  if (loadingInc) {
    return (
      <div className="card p-6 space-y-4">
        {[75, 50, 90, 60].map((w, i) => (
          <div key={i} className="h-6 bg-[#21262d] rounded animate-pulse" style={{ width: `${w}%` }} />
        ))}
      </div>
    );
  }

  if (!incident) {
    return <div className="card p-6 text-center text-[#484f58] text-sm font-mono">Incident not found</div>;
  }

  const accentColor = { critical: "#f85149", warning: "#d29922", investigate: "#a371f7" }[incident.severity] || "#8b949e";
  const fixCommands: FixCommand[] = analysis?.fix_commands || [];
  const confidenceScore = analysis?.confidence_score ? Math.round(analysis.confidence_score * 100) : null;
  const confidenceLabel = analysis?.analysis?.confidence_labels?.likely_cause || "";
  const regression = analysis?.regression_info;

  const tabs = [
    { id: "diagnosis",    label: "AI Diagnosis" },
    { id: "timeline",     label: `Timeline (${timeline.length})` },
    { id: "correlation",  label: "Correlation" },
    ...(fixCommands.length > 0 ? [{ id: "fixes", label: `Fix Commands (${fixCommands.length})` }] : []),
  ];

  return (
    <div className="card flex flex-col gap-0 overflow-hidden animate-slide-up">

      {/* Header */}
      <div className="px-5 py-4 border-b border-[#30363d]"
           style={{ borderLeftColor: accentColor, borderLeftWidth: 3 }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <p className="font-medium text-sm text-[#e6edf3] leading-snug">{incident.title}</p>
              <span className={`text-xs font-mono px-1.5 py-0.5 rounded border ${
                incident.source === "external"
                  ? "text-[#00d4ff] border-[#00d4ff]/25 bg-[#00d4ff]/8"
                  : "text-[#484f58] border-[#30363d]"
              }`}>
                {incident.source}
              </span>
            </div>
            <p className="font-mono text-xs text-[#484f58]">
              #{incident.id} · opened {timeAgo(incident.first_detected)}
            </p>
          </div>
          <button onClick={handleResolve} disabled={resolving}
            className="btn-ghost flex-shrink-0 text-[#3fb950] hover:text-[#3fb950] hover:bg-[#3fb950]/10">
            {resolving ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle size={12} />}
            Resolve
          </button>
        </div>

        {/* Regression banner */}
        {regression?.regression_detected && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-[#f85149]/8 border border-[#f85149]/25 flex items-center gap-2">
            <TrendingUp size={12} className="text-[#f85149] flex-shrink-0" />
            <span className="text-xs font-mono text-[#f85149]">
              Likely deployment regression detected — errors increased {regression.increase_pct}% after {regression.deployment_version}
            </span>
          </div>
        )}
      </div>

      {/* Confidence bar */}
      {confidenceScore !== null && confidenceLabel && (
        <div className="px-5 py-3 border-b border-[#21262d] bg-[#0d1117]/40">
          <p className="text-xs font-mono text-[#484f58] mb-2">AI CONFIDENCE</p>
          <ConfidenceBar label={confidenceLabel} score={confidenceScore} />
        </div>
      )}

      {/* Tab bar */}
      <div className="flex border-b border-[#21262d] px-5 gap-1 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3 py-3 text-xs font-mono whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#00d4ff] text-[#00d4ff]"
                : "border-transparent text-[#484f58] hover:text-[#8b949e]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="overflow-y-auto divide-y divide-[#21262d]">

        {/* ── Diagnosis tab ── */}
        {activeTab === "diagnosis" && (
          <>
            {/* Cluster Summary */}
            <div className="px-5 py-4">
              <p className="section-header">Cluster Summary</p>
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div><span className="text-[#484f58]">Service</span>
                  <p className="text-[#00d4ff] mt-0.5">{incident.service}</p></div>
                <div><span className="text-[#484f58]">Endpoint</span>
                  <p className="text-[#e6edf3] mt-0.5">{incident.endpoint}</p></div>
                <div><span className="text-[#484f58]">Error Signature</span>
                  <p className="text-[#d29922] mt-0.5 break-all">{incident.error_signature}</p></div>
                <div><span className="text-[#484f58]">Occurrences</span>
                  <p className="text-[#e6edf3] mt-0.5">{incident.occurrence_count} events</p></div>
                <div><span className="text-[#484f58]">First Detected</span>
                  <p className="text-[#e6edf3] mt-0.5">{localTs(incident.first_detected)}</p></div>
                <div><span className="text-[#484f58]">Last Seen</span>
                  <p className="text-[#e6edf3] mt-0.5">{localTs(incident.last_seen)}</p></div>
              </div>
            </div>

            {/* Deployment Correlation */}
            {incident.deployment && (
              <div className="px-5 py-4">
                <p className="section-header">Deployment Correlation</p>
                <div className="rounded-lg px-4 py-3 border text-xs font-mono space-y-2"
                     style={{ background: "rgba(210,153,34,0.05)", borderColor: "rgba(210,153,34,0.2)" }}>
                  <div className="flex items-center gap-2">
                    <GitBranch size={12} className="text-[#d29922]" />
                    <span className="text-[#d29922] font-medium">Deployment {incident.deployment.version}</span>
                    <span className="text-[#484f58]">· {timeAgo(incident.deployment.deployed_at)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Package size={12} className="text-[#8b949e]" />
                    <span className="text-[#8b949e]">{incident.deployment.service}</span>
                  </div>
                  {incident.deployment.notes && (
                    <p className="text-[#8b949e] pl-5 border-l border-[#d29922]/20">
                      {incident.deployment.notes}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* AI Diagnosis */}
            <div className="px-5 py-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Brain size={13} className="text-[#a371f7]" />
                  <p className="section-header mb-0">AI Diagnosis</p>
                </div>
                {!analysis && !loadingAI && (
                  <button onClick={handleAnalyse} className="btn-primary text-xs">
                    <Brain size={11} /> Run Analysis
                  </button>
                )}
              </div>

              {loadingAI && <GeminiSkeleton />}

              {!loadingAI && analysis && !analysis.ai_available && (
                <div className="rounded-lg px-4 py-3 bg-[#d29922]/5 border border-[#d29922]/20 text-xs font-mono">
                  <div className="flex items-center gap-2 text-[#d29922]">
                    <AlertTriangle size={12} />
                    <span>{analysis.message}</span>
                  </div>
                </div>
              )}

              {!loadingAI && analysis?.ai_available && analysis.analysis && (
                <div className="space-y-4 animate-fade-in">
                  <div className="flex items-center gap-1.5 text-xs font-mono text-[#484f58]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#a371f7]" />
                    Powered by {analysis.model_used}
                  </div>

                  <div>
                    <p className="text-xs font-mono text-[#484f58] mb-1">INCIDENT SUMMARY</p>
                    <p className="text-sm text-[#c9d1d9] leading-relaxed">{analysis.analysis.incident_summary}</p>
                  </div>

                  <div className="rounded-lg px-4 py-3 bg-[#a371f7]/5 border border-[#a371f7]/20">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-mono text-[#a371f7]">LIKELY CAUSE</p>
                      <ConfidenceLabel label={analysis.analysis.confidence_labels.likely_cause} />
                    </div>
                    <p className="text-sm text-[#c9d1d9]">{analysis.analysis.likely_cause}</p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-[#484f58]">INVESTIGATION PRIORITY</span>
                    <ConfidenceLabel label={analysis.analysis.investigation_priority} />
                  </div>

                  {analysis.analysis.recommended_checks?.length > 0 && (
                    <div>
                      <p className="text-xs font-mono text-[#484f58] mb-2">RECOMMENDED CHECKS</p>
                      <ul className="space-y-1.5">
                        {analysis.analysis.recommended_checks.map((c, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-[#c9d1d9]">
                            <span className="font-mono text-[#00d4ff] flex-shrink-0 text-xs mt-0.5">
                              [{String(i + 1).padStart(2, "0")}]
                            </span>
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {!analysis && !loadingAI && (
                <p className="text-xs text-[#484f58] font-mono">
                  Click "Run Analysis" to get AI-powered debugging guidance
                </p>
              )}
            </div>

            {/* Log Sample */}
            {logs.length > 0 && (
              <div className="px-5 py-4">
                <button onClick={() => setShowLogs((v) => !v)}
                  className="flex items-center gap-2 text-xs font-mono text-[#8b949e] hover:text-[#e6edf3] transition-colors w-full">
                  <Terminal size={11} />
                  <span>Log Sample ({logs.length} events)</span>
                  {showLogs ? <ChevronUp size={11} className="ml-auto" /> : <ChevronDown size={11} className="ml-auto" />}
                </button>

                {showLogs && (
                  <div className="mt-3 overflow-x-auto animate-fade-in">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-[#484f58] border-b border-[#21262d]">
                          {["Time", "Status", "Latency", "Error"].map((h) => (
                            <th key={h} className="text-left py-1.5 pr-4 font-normal">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#21262d]/50">
                        {logs.slice(0, 10).map((log) => (
                          <tr key={log.id} className="hover:bg-[#1c2128] transition-colors">
                            <td className="py-1.5 pr-4 text-[#484f58]">
                              {new Date(log.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                            </td>
                            <td className="py-1.5 pr-4" style={{ color: log.status_code >= 500 ? "#f85149" : log.status_code >= 400 ? "#d29922" : "#3fb950" }}>
                              {log.status_code}
                            </td>
                            <td className="py-1.5 pr-4 text-[#a371f7]">{log.latency_ms}ms</td>
                            <td className="py-1.5 text-[#8b949e] truncate max-w-[160px]">{log.error_type || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ── Timeline tab ── */}
        {activeTab === "timeline" && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-4">
              <Clock size={13} className="text-[#00d4ff]" />
              <p className="section-header mb-0">Incident Timeline Replay</p>
            </div>
            <TimelineReplay events={timeline} />
          </div>
        )}

        {/* ── Correlation tab ── */}
        {activeTab === "correlation" && (
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-4">
              <GitBranch size={13} className="text-[#d29922]" />
              <p className="section-header mb-0">Root-Cause Correlation Graph</p>
            </div>
            {correlation ? (
              <CorrelationView graph={correlation} />
            ) : (
              <p className="text-xs font-mono text-[#484f58]">Loading correlation data…</p>
            )}
          </div>
        )}

        {/* ── Fix Commands tab ── */}
        {activeTab === "fixes" && (
          <div className="px-5 py-4 space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Terminal size={13} className="text-[#3fb950]" />
              <p className="section-header mb-0">AI-Generated Fix Commands</p>
            </div>
            {fixCommands.length > 0 ? (
              fixCommands.map((cmd, i) => (
                <FixCommandBlock key={i} cmd={cmd} />
              ))
            ) : (
              <p className="text-xs font-mono text-[#484f58]">
                Run AI Analysis first to generate fix commands
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}