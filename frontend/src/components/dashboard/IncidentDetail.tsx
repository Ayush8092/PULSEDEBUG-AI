/**
 * PulseDebug AI — Incident Detail Panel
 * File: frontend/src/components/dashboard/IncidentDetail.tsx
 * Purpose:
 *   Full-detail panel shown when an incident is selected from the feed.
 *   Sections:
 *     1. Header         — title, severity accent, resolve button
 *     2. Cluster info   — endpoint, occurrences, error signature, timestamps
 *     3. Deployment     — linked deploy info + notes (if correlated)
 *     4. AI Diagnosis   — Gemini analysis or graceful quota fallback message
 *     5. Log sample     — collapsible raw event table
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useEffect } from "react";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import {
  Brain, GitBranch, CheckCircle, AlertTriangle,
  Loader2, ChevronDown, ChevronUp, Terminal, Package,
} from "lucide-react";
import {
  getIncident, getIncidentLogs, runAIAnalysis, resolveIncident,
  Incident, LogEvent, AIAnalysis,
} from "@/lib/api";

const ts     = (iso: string) => { try { return format(parseISO(iso), "HH:mm:ss dd MMM"); } catch { return iso; } };
const timeAgo = (iso: string) => { try { return formatDistanceToNow(parseISO(iso), { addSuffix: true }); } catch { return iso; } };

function ConfidenceLabel({ label }: { label: string }) {
  const map: Record<string, string> = {
    "High Likelihood":     "text-[#3fb950] bg-[#3fb950]/10 border-[#3fb950]/20",
    "Moderate Likelihood": "text-[#d29922] bg-[#d29922]/10 border-[#d29922]/20",
    "Needs Investigation": "text-[#a371f7] bg-[#a371f7]/10 border-[#a371f7]/20",
    "Not Related":         "text-[#8b949e] bg-[#8b949e]/10 border-[#8b949e]/20",
  };
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-xs font-mono border ${map[label] || map["Not Related"]}`}>
      {label}
    </span>
  );
}

export default function IncidentDetail({
  incidentId, onResolved,
}: { incidentId: number; onResolved: () => void }) {
  const [incident,  setIncident]  = useState<Incident | null>(null);
  const [logs,      setLogs]      = useState<LogEvent[]>([]);
  const [analysis,  setAnalysis]  = useState<AIAnalysis | null>(null);
  const [loadingInc,setLoadingInc]= useState(true);
  const [loadingAI, setLoadingAI] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [showLogs,  setShowLogs]  = useState(false);

  useEffect(() => {
    setLoadingInc(true); setAnalysis(null); setShowLogs(false);
    Promise.all([getIncident(incidentId), getIncidentLogs(incidentId, 20)])
      .then(([inc, logData]) => {
        setIncident(inc); setLogs(logData);
        if (inc.ai_summary) {
          setAnalysis({
            incident_id: incidentId, model_used: inc.ai_model_used, ai_available: true,
            analysis: {
              incident_summary:       inc.ai_summary!,
              likely_cause:           inc.ai_root_cause || "",
              recommended_checks:     JSON.parse(inc.ai_checks || "[]"),
              investigation_priority: inc.ai_priority || "Medium",
              confidence_labels: { likely_cause: "High Likelihood", deployment_related: "High Likelihood" },
              debugging_steps: [],
            },
          });
        }
      })
      .finally(() => setLoadingInc(false));
  }, [incidentId]);

  const handleAnalyse = async () => {
    setLoadingAI(true);
    try { setAnalysis(await runAIAnalysis(incidentId)); }
    finally { setLoadingAI(false); }
  };

  const handleResolve = async () => {
    if (!incident) return;
    setResolving(true);
    try { await resolveIncident(incidentId); onResolved(); }
    finally { setResolving(false); }
  };

  if (loadingInc) {
    return (
      <div className="card p-6 space-y-4 animate-pulse">
        {[...Array(4)].map((_, i) => <div key={i} className="h-6 bg-[#21262d] rounded" />)}
      </div>
    );
  }
  if (!incident) return <div className="card p-6 text-center text-[#484f58] text-sm font-mono">Incident not found</div>;

  const accentColor = { critical: "#f85149", warning: "#d29922", investigate: "#a371f7" }[incident.severity] || "#8b949e";

  return (
    <div className="card flex flex-col gap-0 overflow-hidden animate-slide-up">

      {/* ── Header ── */}
      <div className="px-5 py-4 border-b border-[#30363d]" style={{ borderLeftColor: accentColor, borderLeftWidth: 3 }}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-medium text-sm text-[#e6edf3] leading-snug">{incident.title}</p>
            <p className="font-mono text-xs text-[#484f58] mt-1">#{incident.id} · opened {timeAgo(incident.first_detected)}</p>
          </div>
          <button onClick={handleResolve} disabled={resolving}
            className="btn-ghost flex-shrink-0 text-[#3fb950] hover:text-[#3fb950] hover:bg-[#3fb950]/10">
            {resolving ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle size={12} />}
            Resolve
          </button>
        </div>
      </div>

      <div className="overflow-y-auto divide-y divide-[#21262d]">

        {/* ── Cluster Summary ── */}
        <div className="px-5 py-4">
          <p className="section-header">Cluster Summary</p>
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            {[
              ["Service",         <span className="text-[#00d4ff]">{incident.service}</span>],
              ["Endpoint",        incident.endpoint],
              ["Error Signature", <span className="text-[#d29922]">{incident.error_signature}</span>],
              ["Occurrences",     `${incident.occurrence_count} events`],
              ["First Detected",  ts(incident.first_detected)],
              ["Last Seen",       ts(incident.last_seen)],
            ].map(([k, v], i) => (
              <div key={i}>
                <span className="text-[#484f58]">{k}</span>
                <p className="text-[#e6edf3] mt-0.5">{v}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Deployment Correlation ── */}
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
                <p className="text-[#8b949e] pl-5 border-l border-[#d29922]/20">{incident.deployment.notes}</p>
              )}
            </div>
          </div>
        )}

        {/* ── AI Diagnosis Panel ── */}
        <div className="px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain size={13} className="text-[#a371f7]" />
              <p className="section-header mb-0">AI Diagnosis</p>
            </div>
            {!analysis && (
              <button onClick={handleAnalyse} disabled={loadingAI} className="btn-primary text-xs">
                {loadingAI ? <Loader2 size={11} className="animate-spin" /> : <Brain size={11} />}
                {loadingAI ? "Analysing…" : "Run Analysis"}
              </button>
            )}
          </div>

          {/* Quota fallback */}
          {analysis && !analysis.ai_available && (
            <div className="rounded-lg px-4 py-3 bg-[#d29922]/5 border border-[#d29922]/20 text-xs font-mono space-y-2">
              <div className="flex items-center gap-2 text-[#d29922]">
                <AlertTriangle size={12} /><span>{analysis.message}</span>
              </div>
              {analysis.statistical_summary && (
                <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-[#d29922]/20 text-[#8b949e]">
                  <span>Total events: {analysis.statistical_summary.total_events}</span>
                  <span>Anomalies: {analysis.statistical_summary.anomaly_count}</span>
                  <span>Avg latency: {analysis.statistical_summary.avg_latency_ms}ms</span>
                  <span>Error rate: {(analysis.statistical_summary.error_rate * 100).toFixed(1)}%</span>
                </div>
              )}
            </div>
          )}

          {/* AI result */}
          {analysis?.ai_available && analysis.analysis && (
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
                        <span className="font-mono text-[#00d4ff] flex-shrink-0 text-xs mt-0.5">[{String(i+1).padStart(2,"0")}]</span>
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.analysis.debugging_steps?.length > 0 && (
                <div>
                  <p className="text-xs font-mono text-[#484f58] mb-2">DEBUGGING STEPS</p>
                  <ul className="space-y-1.5">
                    {analysis.analysis.debugging_steps.map((s, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-[#c9d1d9]">
                        <span className="font-mono text-[#3fb950] flex-shrink-0 text-xs mt-0.5">→</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {!analysis && !loadingAI && (
            <p className="text-xs text-[#484f58] font-mono">Click "Run Analysis" to get AI-powered debugging guidance</p>
          )}
        </div>

        {/* ── Log Sample ── */}
        {logs.length > 0 && (
          <div className="px-5 py-4">
            <button onClick={() => setShowLogs(v => !v)}
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
                      {["Time","Status","Latency","Error"].map(h => (
                        <th key={h} className="text-left py-1.5 pr-4 font-normal">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#21262d]/50">
                    {logs.slice(0, 10).map(log => (
                      <tr key={log.id} className="hover:bg-[#1c2128] transition-colors">
                        <td className="py-1.5 pr-4 text-[#484f58]">
                          {format(parseISO(log.timestamp), "HH:mm:ss")}
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
      </div>
    </div>
  );
}