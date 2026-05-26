/**
 * PulseDebug AI — Project Analyzer Page
 * File: frontend/src/app/analyze/page.tsx
 * Purpose:
 *   Upload-based project health analyzer with full AI diagnosis output.
 *
 *   Log file results render:
 *     1. Metric cards (requests, error rate, latency, p95)
 *     2. Incident Summary card (AI executive summary)
 *     3. Impact card
 *     4. Likely Cause card
 *     5. Recommended Actions (numbered steps)
 *     6. Raw Analysis JSON (collapsible accordion)
 *
 *   ZIP file results render:
 *     1. Score cards (resilience score, files, risks, checks passed)
 *     2. Architecture Health Summary card
 *     3. Operational Risk Impact card
 *     4. Architectural Weaknesses card
 *     5. Recommended Improvements (numbered steps)
 *     6. Raw Static Findings JSON (collapsible accordion)
 *
 *   Gemini/Groq failover is completely invisible.
 *   Loading shimmer shown during AI generation.
 *   All sections fade in on completion.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Zap,
  Upload,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
  Brain,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Shield,
  Activity,
  TrendingUp,
  FileText,
} from "lucide-react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobStatus = "queued" | "processing" | "complete" | "error";
type JobType   = "log_analysis" | "zip_inspection";

type RecommendedAction = {
  step:   string;
  title:  string;
  detail: string;
};

type RecommendedImprovement = {
  step:    string;
  title:   string;
  detail:  string;
  library: string;
};

type LogResult = {
  status:               JobStatus;
  type:                 "log_analysis";
  filename:             string;
  metrics:              Record<string, any>;
  incident_summary:     string;
  impact:               string;
  likely_cause:         string;
  recommended_actions:  RecommendedAction[];
  raw_analysis:         Record<string, any>;
  ai_available:         boolean;
  completed_at:         string;
};

type ZipResult = {
  status:                      JobStatus;
  type:                        "zip_inspection";
  filename:                    string;
  resilience_score:            number;
  files_scanned:               number;
  risks_detected:              number;
  checks_passed:               number;
  architecture_health_summary: string;
  operational_risk_impact:     string;
  architectural_weaknesses:    string;
  recommended_improvements:    RecommendedImprovement[];
  raw_findings:                Record<string, any>;
  ai_available:                boolean;
  completed_at:                string;
};

type JobResult =
  | { status: "queued" | "processing" | "error"; error?: string }
  | LogResult
  | ZipResult;

// ---------------------------------------------------------------------------
// Shared components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  color = "#00d4ff",
  sub,
}: {
  label: string;
  value: string | number;
  color?: string;
  sub?: string;
}) {
  return (
    <div
      className="card p-4 flex flex-col gap-1"
      style={{ borderColor: `${color}25` }}
    >
      <p className="metric-label">{label}</p>
      <p
        className="font-display font-bold text-2xl tabular-nums"
        style={{ color }}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-[#484f58] font-mono">{sub}</p>}
    </div>
  );
}

function SectionCard({
  icon,
  label,
  color,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-lg border p-5 space-y-3 animate-fade-in"
      style={{
        background:  `${color}06`,
        borderColor: `${color}28`,
      }}
    >
      <div className="flex items-center gap-2">
        <span style={{ color }}>{icon}</span>
        <p className="text-xs font-mono font-medium uppercase tracking-widest"
           style={{ color }}>
          {label}
        </p>
      </div>
      {children}
    </div>
  );
}

function ActionCard({
  step,
  title,
  detail,
  library,
  color,
}: {
  step: string;
  title: string;
  detail: string;
  library?: string;
  color: string;
}) {
  return (
    <div className="card p-4 space-y-1.5 animate-fade-in">
      <div className="flex items-start gap-3">
        <span
          className="font-mono text-sm font-bold flex-shrink-0 mt-0.5"
          style={{ color }}
        >
          [{step}]
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[#e6edf3]">{title}</p>
          <p className="text-xs text-[#8b949e] mt-1 leading-relaxed">{detail}</p>
          {library && (
            <p className="text-xs font-mono mt-1.5" style={{ color }}>
              → {library}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function RawJsonAccordion({
  label,
  data,
}: {
  label: string;
  data: Record<string, any>;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#1c2128] transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText size={13} className="text-[#484f58]" />
          <span className="text-sm font-mono text-[#8b949e]">{label}</span>
        </div>
        {open ? (
          <ChevronUp size={13} className="text-[#484f58]" />
        ) : (
          <ChevronDown size={13} className="text-[#484f58]" />
        )}
      </button>
      {open && (
        <div className="border-t border-[#21262d] px-5 pb-5 pt-4 animate-fade-in">
          <pre className="text-xs font-mono text-[#8b949e] overflow-x-auto leading-relaxed">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function GeminiShimmer({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-[#a371f7]/20 bg-[#a371f7]/5 p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Loader2 size={13} className="text-[#a371f7] animate-spin" />
        <span className="text-xs font-mono text-[#a371f7]">{label}</span>
      </div>
      <div className="space-y-2">
        {[85, 95, 70, 90, 60].map((w, i) => (
          <div
            key={i}
            className="h-2.5 rounded animate-pulse"
            style={{
              width:            `${w}%`,
              background:       "rgba(163,113,247,0.15)",
              animationDelay:   `${i * 100}ms`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Log analysis results renderer
// ---------------------------------------------------------------------------

function LogResults({ result }: { result: LogResult }) {
  const m          = result.metrics;
  const errorPct   = ((m.error_rate || 0) * 100).toFixed(1);
  const errorColor = (m.error_rate || 0) > 0.1 ? "#f85149" : "#3fb950";

  return (
    <div className="space-y-4 animate-fade-in">

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Total Requests"
          value={(m.total_requests || 0).toLocaleString()}
          color="#00d4ff"
        />
        <StatCard
          label="Error Rate"
          value={`${errorPct}%`}
          color={errorColor}
          sub={m.retry_storm_detected ? "⚠ retry storm" : undefined}
        />
        <StatCard
          label="Avg Latency"
          value={`${m.latency?.avg_ms || 0}ms`}
          color={m.latency?.avg_ms > 1000 ? "#f85149" : "#d29922"}
        />
        <StatCard
          label="P95 Latency"
          value={`${m.latency?.p95_ms || 0}ms`}
          color={m.latency?.p95_ms > 2000 ? "#f85149" : "#8b949e"}
        />
      </div>

      {/* 1. Incident Summary */}
      <SectionCard
        icon={<Brain size={14} />}
        label="Incident Summary"
        color="#a371f7"
      >
        <p className="text-sm text-[#c9d1d9] leading-relaxed">
          {result.incident_summary}
        </p>
      </SectionCard>

      {/* 2. Impact */}
      <SectionCard
        icon={<Activity size={14} />}
        label="Impact"
        color="#f85149"
      >
        <p className="text-sm text-[#c9d1d9] leading-relaxed">
          {result.impact}
        </p>
      </SectionCard>

      {/* 3. Likely Cause */}
      <SectionCard
        icon={<AlertTriangle size={14} />}
        label="Likely Cause"
        color="#d29922"
      >
        <p className="text-sm text-[#c9d1d9] leading-relaxed">
          {result.likely_cause}
        </p>
      </SectionCard>

      {/* 4. Recommended Actions */}
      {result.recommended_actions?.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-mono font-medium text-[#8b949e] uppercase tracking-widest px-1">
            Recommended Actions
          </p>
          {result.recommended_actions.map((a) => (
            <ActionCard
              key={a.step}
              step={a.step}
              title={a.title}
              detail={a.detail}
              color="#00d4ff"
            />
          ))}
        </div>
      )}

      {/* 5. Raw Analysis JSON */}
      <RawJsonAccordion label="View Raw Analysis" data={result.raw_analysis} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// ZIP inspection results renderer
// ---------------------------------------------------------------------------

function ZipResults({ result }: { result: ZipResult }) {
  const score      = result.resilience_score || 0;
  const scoreColor =
    score >= 75 ? "#3fb950" : score >= 50 ? "#d29922" : "#f85149";

  const scoreLabel =
    score >= 75 ? "Strong"
    : score >= 50 ? "Adequate"
    : score >= 30 ? "At Risk"
    : "Critical Risk";

  return (
    <div className="space-y-4 animate-fade-in">

      {/* Score cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="Resilience Score"
          value={`${score}%`}
          color={scoreColor}
          sub={scoreLabel}
        />
        <StatCard
          label="Files Scanned"
          value={result.files_scanned || 0}
          color="#00d4ff"
        />
        <StatCard
          label="Risks Detected"
          value={result.risks_detected || 0}
          color={(result.risks_detected || 0) > 3 ? "#f85149" : "#d29922"}
        />
        <StatCard
          label="Checks Passed"
          value={result.checks_passed || 0}
          color="#3fb950"
        />
      </div>

      {/* 1. Architecture Health Summary */}
      <SectionCard
        icon={<Shield size={14} />}
        label="Architecture Health Summary"
        color="#a371f7"
      >
        <p className="text-sm text-[#c9d1d9] leading-relaxed">
          {result.architecture_health_summary}
        </p>
      </SectionCard>

      {/* 2. Operational Risk Impact */}
      <SectionCard
        icon={<Activity size={14} />}
        label="Operational Risk Impact"
        color="#f85149"
      >
        <p className="text-sm text-[#c9d1d9] leading-relaxed">
          {result.operational_risk_impact}
        </p>
      </SectionCard>

      {/* 3. Architectural Weaknesses */}
      <SectionCard
        icon={<AlertTriangle size={14} />}
        label="Likely Architectural Weaknesses"
        color="#d29922"
      >
        <p className="text-sm text-[#c9d1d9] leading-relaxed">
          {result.architectural_weaknesses}
        </p>
      </SectionCard>

      {/* 4. Recommended Improvements */}
      {result.recommended_improvements?.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-mono font-medium text-[#8b949e] uppercase tracking-widest px-1">
            Recommended Improvements
          </p>
          {result.recommended_improvements.map((imp) => (
            <ActionCard
              key={imp.step}
              step={imp.step}
              title={imp.title}
              detail={imp.detail}
              library={imp.library}
              color="#a371f7"
            />
          ))}
        </div>
      )}

      {/* 5. Raw Static Findings */}
      <RawJsonAccordion
        label="View Raw Static Findings"
        data={result.raw_findings || {}}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AnalyzePage() {
  const [dragging,  setDragging]  = useState(false);
  const [uploading, setUploading] = useState(false);
  const [jobId,     setJobId]     = useState<string | null>(null);
  const [polling,   setPolling]   = useState(false);
  const [result,    setResult]    = useState<JobResult | null>(null);
  const [error,     setError]     = useState<string | null>(null);
  const [pollMsg,   setPollMsg]   = useState("Running analysis…");
  const fileRef = useRef<HTMLInputElement>(null);

  const POLL_MESSAGES = [
    "Parsing log patterns…",
    "Clustering failure signatures…",
    "Running resilience checks…",
    "Generating AI diagnosis…",
    "Preparing recommendations…",
  ];

  const pollResult = useCallback(async (id: string) => {
    setPolling(true);
    let attempts = 0;
    const maxAttempts = 60;
    let msgIdx = 0;

    const check = async () => {
      attempts++;
      msgIdx = (msgIdx + 1) % POLL_MESSAGES.length;
      setPollMsg(POLL_MESSAGES[msgIdx]);

      try {
        const res  = await fetch(`${BASE_URL}/api/analyzer/results/${id}`);
        const data = (await res.json()) as JobResult;

        if (data.status === "complete" || data.status === "error") {
          setResult(data);
          setPolling(false);
          return;
        }
        if (attempts < maxAttempts) {
          setTimeout(check, 3000);
        } else {
          setError("Analysis timed out. Please try again.");
          setPolling(false);
        }
      } catch {
        setError("Lost connection. Please try again.");
        setPolling(false);
      }
    };

    setTimeout(check, 2000);
  }, []);

  const handleUpload = async (file: File) => {
    setError(null);
    setResult(null);
    setJobId(null);
    setUploading(true);

    try {
      const form = new FormData();
      form.append("file", file);

      const res  = await fetch(`${BASE_URL}/api/analyzer/upload`, {
        method: "POST",
        body:   form,
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Upload failed.");
        return;
      }

      setJobId(data.job_id);
      pollResult(data.job_id);
    } catch {
      setError("Could not reach the backend. Make sure it is running.");
    } finally {
      setUploading(false);
    }
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const reset = () => {
    setResult(null);
    setJobId(null);
    setError(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const isComplete = result && "status" in result && result.status === "complete";
  const isError    = result && "status" in result && result.status === "error";

  return (
    <div className="min-h-screen bg-[#0d1117]">

      {/* Header */}
      <header className="border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-[#8b949e] hover:text-[#e6edf3] transition-colors"
          >
            <ArrowLeft size={14} />
            <span className="text-sm font-mono">Back to Dashboard</span>
          </Link>
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-[#00d4ff]" />
            <span className="font-display font-bold text-[#e6edf3]">PulseDebug</span>
            <span className="font-display font-bold text-[#00d4ff]">AI</span>
            <span className="font-mono text-xs text-[#484f58] ml-2">
              Project Analyzer
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">

        {/* Hero */}
        <div>
          <h1 className="font-display text-2xl font-bold text-[#e6edf3] mb-3">
            Analyze Your Project Health
          </h1>
          <p className="text-[#8b949e] text-sm leading-relaxed max-w-2xl">
            Upload your backend project ZIP or API log files. PulseDebug runs
            resilience checks and generates a professional AI-powered audit report
            with specific, actionable remediation steps.
          </p>
        </div>

        {/* Upload zone */}
        {!isComplete && !polling && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            className="card p-14 flex flex-col items-center justify-center cursor-pointer
                       transition-all duration-200 text-center select-none"
            style={{
              borderColor: dragging
                ? "#a371f7"
                : uploading
                ? "#a371f7"
                : "#30363d",
              background: dragging ? "rgba(163,113,247,0.04)" : undefined,
            }}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".zip,.log,.json,.txt"
              onChange={onFileChange}
              className="hidden"
            />

            {uploading ? (
              <>
                <Loader2 size={32} className="text-[#a371f7] animate-spin mb-4" />
                <p className="text-sm text-[#8b949e]">Uploading file…</p>
              </>
            ) : (
              <>
                <div
                  className="w-16 h-16 rounded-full flex items-center justify-center mb-5"
                  style={{
                    background:  "rgba(163,113,247,0.10)",
                    border:      "1px solid rgba(163,113,247,0.30)",
                    boxShadow:   "0 0 28px rgba(163,113,247,0.18)",
                  }}
                >
                  <Upload size={24} style={{ color: "#a371f7" }} />
                </div>

                <p className="font-medium text-[#e6edf3] text-base mb-1">
                  Drop ZIP / logs here for resilience audit
                </p>
                <p className="text-sm text-[#8b949e] mb-4">
                  or click to browse your files
                </p>

                <div className="flex items-center gap-2 flex-wrap justify-center">
                  {[
                    { ext: ".zip",  color: "#00d4ff", desc: "Architecture audit" },
                    { ext: ".log",  color: "#a371f7", desc: "Incident analysis" },
                    { ext: ".json", color: "#3fb950", desc: "JSON logs" },
                    { ext: ".txt",  color: "#d29922", desc: "Plain text logs" },
                  ].map((item) => (
                    <div
                      key={item.ext}
                      className="flex flex-col items-center px-3 py-1.5 rounded border"
                      style={{
                        borderColor: `${item.color}33`,
                        background:  `${item.color}0d`,
                      }}
                    >
                      <span
                        className="font-mono text-xs font-bold"
                        style={{ color: item.color }}
                      >
                        {item.ext}
                      </span>
                      <span className="font-mono text-[10px] text-[#484f58] mt-0.5">
                        {item.desc}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="font-mono text-xs text-[#484f58] mt-4">
                  Max 10MB
                </p>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="card p-4 border-[#f85149]/30 bg-[#f85149]/5 flex items-center gap-3">
            <AlertTriangle size={14} className="text-[#f85149] flex-shrink-0" />
            <p className="text-sm text-[#f85149]">{error}</p>
            <button onClick={reset} className="btn-ghost ml-auto text-xs">
              Try again
            </button>
          </div>
        )}

        {/* Polling / AI generation shimmer */}
        {polling && (
          <div className="space-y-4">
            <GeminiShimmer label={pollMsg} />
            <div className="card p-6 space-y-3">
              {[90, 70, 80, 60].map((w, i) => (
                <div
                  key={i}
                  className="h-3 rounded animate-pulse"
                  style={{
                    width:            `${w}%`,
                    background:       "#21262d",
                    animationDelay:   `${i * 150}ms`,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {isComplete && result && "type" in result && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle size={16} className="text-[#3fb950]" />
                <span className="font-medium text-sm text-[#e6edf3]">
                  Analysis complete —{" "}
                  <span className="font-mono text-[#8b949e]">
                    {result.filename}
                  </span>
                </span>
              </div>
              <button
                onClick={reset}
                className="btn-ghost text-xs flex items-center gap-1.5"
              >
                <RefreshCw size={11} />
                Analyze another file
              </button>
            </div>

            {result.type === "log_analysis" && (
              <LogResults result={result as LogResult} />
            )}
            {result.type === "zip_inspection" && (
              <ZipResults result={result as ZipResult} />
            )}
          </div>
        )}

        {/* Error result */}
        {isError && result && "error" in result && (
          <div className="card p-5 border-[#f85149]/30 bg-[#f85149]/5">
            <p className="text-sm text-[#f85149]">
              Analysis failed: {result.error}
            </p>
            <button onClick={reset} className="btn-ghost mt-3 text-xs">
              Try again
            </button>
          </div>
        )}

      </main>
    </div>
  );
}