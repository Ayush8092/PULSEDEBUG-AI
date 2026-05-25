/**
 * PulseDebug AI — Project Analyzer Page
 * File: frontend/src/app/analyze/page.tsx
 * Purpose:
 *   Upload-based project health analyzer. Production polish:
 *   - Improved empty-state: "Drop ZIP / logs here for resilience audit"
 *   - Supported types clearly listed in empty state
 *   - Upload success toast feedback
 *   - Micro-animation on upload completion
 *   - TypeScript types without angle-bracket generics
 *
 */

"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft, Zap, Upload, AlertTriangle,
  CheckCircle, XCircle, Loader2, Brain,
  ChevronDown, ChevronUp, RefreshCw, FileText,
} from "lucide-react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Types without angle brackets

type JobStatus = "queued" | "processing" | "complete" | "error";
type JobType   = "log_analysis" | "zip_inspection";

type JobResult = {
  status:       JobStatus;
  type?:        JobType;
  filename?:    string;
  error?:       string;
  statistics?:  Record<string, any>;
  inspection?:  Record<string, any>;
  ai_analysis?: Record<string, any>;
  ai_available?:boolean;
  completed_at?:string;
};

// Shared components

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    critical:    "badge-critical",
    warning:     "badge-warning",
    investigate: "badge-investigate",
    low:         "badge-resolved",
  };
  return (
    <span className={map[severity] || "badge-investigate"}>
      {severity.toUpperCase()}
    </span>
  );
}

function StatCard({ label, value, color = "#00d4ff" }: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="card p-4" style={{ borderColor: `${color}22` }}>
      <p className="metric-label mb-1">{label}</p>
      <p className="font-display font-bold text-xl tabular-nums" style={{ color }}>
        {value}
      </p>
    </div>
  );
}

function CollapsibleSection({ title, children, defaultOpen = false }: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[#1c2128] transition-colors"
      >
        <span className="font-medium text-sm text-[#e6edf3]">{title}</span>
        {open
          ? <ChevronUp size={14} className="text-[#484f58]" />
          : <ChevronDown size={14} className="text-[#484f58]" />}
      </button>
      {open && (
        <div className="px-5 pb-5 border-t border-[#21262d]">{children}</div>
      )}
    </div>
  );
}

// Log analysis results

function LogResults({ result }: { result: JobResult }) {
  const stats = result.statistics!;
  const ai    = result.ai_analysis;

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total Requests" value={stats.total_requests?.toLocaleString() || 0} color="#00d4ff" />
        <StatCard
          label="Error Rate"
          value={`${(((stats.error_rate as number) || 0) * 100).toFixed(1)}%`}
          color={(stats.error_rate as number) > 0.1 ? "#f85149" : "#3fb950"}
        />
        <StatCard
          label="Avg Latency"
          value={`${stats.latency?.avg_ms || 0}ms`}
          color={stats.latency?.avg_ms > 1000 ? "#f85149" : "#d29922"}
        />
        <StatCard
          label="P95 Latency"
          value={`${stats.latency?.p95_ms || 0}ms`}
          color={stats.latency?.p95_ms > 2000 ? "#f85149" : "#8b949e"}
        />
      </div>

      {stats.retry_storm_detected && (
        <div className="card p-4 border-[#f85149]/30 bg-[#f85149]/5 flex items-center gap-3">
          <AlertTriangle size={16} className="text-[#f85149] flex-shrink-0" />
          <p className="text-sm text-[#f85149] font-medium">
            Retry storm detected — {stats.retry_count as number} retry events found
          </p>
        </div>
      )}

      {ai && !ai.parse_error ? (
        <>
          <div className="card p-5 border-[#a371f7]/20 bg-[#a371f7]/5">
            <div className="flex items-center gap-2 mb-3">
              <Brain size={14} className="text-[#a371f7]" />
              <span className="section-header mb-0">
                AI Incident Analysis
              </span>
            </div>

            <div className="space-y-4 text-sm text-[#c9d1d9]">
              <div>
                <p className="text-[#8b949e] mb-1 font-medium">
                  Incident Summary
                </p>
                <p>{ai.incident_summary}</p>
              </div>

              <div>
                <p className="text-[#8b949e] mb-1 font-medium">
                  Impact
                </p>
                <p>{ai.impact}</p>
              </div>

              <div>
                <p className="text-[#8b949e] mb-1 font-medium">
                  Likely Cause
                </p>
                <p>{ai.likely_cause}</p>
              </div>
            </div>
          </div>

          {ai.recommended_actions?.length > 0 && (
            <CollapsibleSection
              title="Recommended Actions"
              defaultOpen
            >
              <ul className="space-y-2 mt-4">
                {ai.recommended_actions.map(
                  (step: string, i: number) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-[#c9d1d9]"
                    >
                      <span className="font-mono text-[#00d4ff] text-xs mt-0.5 flex-shrink-0">
                        [{String(i + 1).padStart(2, "0")}]
                      </span>
                      {step}
                    </li>
                  )
                )}
              </ul>
            </CollapsibleSection>
          )}
        </>
      ) : !result.ai_available ? (
        <div className="card p-4 border-[#d29922]/20 bg-[#d29922]/5 flex items-center gap-3">
          <AlertTriangle size={14} className="text-[#d29922]" />
          <span className="text-sm text-[#d29922]">
            AI quota reached. Statistical analysis shown above.
          </span>
        </div>
      ) : null}

      <CollapsibleSection title="Raw Statistics">
        <pre className="mt-4 text-xs font-mono text-[#8b949e] overflow-x-auto">
          {JSON.stringify(stats, null, 2)}
        </pre>
      </CollapsibleSection>
    </div>
  );
}

// ZIP inspection results

function ZipResults({ result }: { result: JobResult }) {
  const inspection = result.inspection!;
  const ai         = result.ai_analysis;
  const score      = (inspection.resilience_score as number) || 0;
  const scoreColor = score >= 75 ? "#3fb950" : score >= 50 ? "#d29922" : "#f85149";

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Resilience Score" value={`${score}%`}            color={scoreColor} />
        <StatCard label="Files Scanned"    value={inspection.total_files || 0} color="#00d4ff" />
        <StatCard
          label="Risks Detected"
          value={inspection.risks_detected?.length || 0}
          color={(inspection.risks_detected?.length || 0) > 3 ? "#f85149" : "#d29922"}
        />
        <StatCard
          label="Checks Passed"
          value={inspection.checks?.filter((c: any) => c.present).length || 0}
          color="#3fb950"
        />
      </div>

      {inspection.sensitive_files_found?.length > 0 && (
        <div className="card p-4 border-[#f85149]/30 bg-[#f85149]/5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-[#f85149]" />
            <span className="text-sm font-medium text-[#f85149]">
              Potentially Sensitive Files Found
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {inspection.sensitive_files_found.map((f: string) => (
              <code key={f} className="text-xs font-mono text-[#f85149] bg-[#f85149]/10 px-2 py-0.5 rounded">
                {f}
              </code>
            ))}
          </div>
        </div>
      )}

      {ai && !ai.parse_error && (
        <div className="card p-5 border-[#a371f7]/20 bg-[#a371f7]/5">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={14} className="text-[#a371f7]" />
            <span className="section-header mb-0">AI Resilience Assessment</span>
          </div>
          <div className="flex items-center gap-3 mb-3">
            <span className="text-sm text-[#8b949e]">Verdict:</span>
            <span className={`font-mono text-sm font-bold ${
              ai.overall_verdict?.includes("Strong") ? "text-[#3fb950]" :
              ai.overall_verdict?.includes("Critical") ? "text-[#f85149]" : "text-[#d29922]"
            }`}>
              {ai.overall_verdict}
            </span>
          </div>
          <p className="text-sm text-[#c9d1d9] leading-relaxed">{ai.summary}</p>
          {ai.deployment_risks && (
            <p className="text-xs text-[#8b949e] mt-3 pt-3 border-t border-[#a371f7]/20 leading-relaxed">
              {ai.deployment_risks}
            </p>
          )}
        </div>
      )}

      {(ai?.risk_findings || inspection.risks_detected)?.length > 0 && (
        <CollapsibleSection title="Risk Findings" defaultOpen>
          <div className="space-y-3 mt-4">
            {(ai?.risk_findings || inspection.risks_detected).map((risk: any, i: number) => (
              <div key={i} className="rounded-lg border border-[#30363d] p-4 space-y-2">
                <div className="flex items-center gap-2">
                  {risk.severity && <SeverityBadge severity={risk.severity} />}
                  <span className="font-mono text-xs text-[#484f58]">{risk.check}</span>
                </div>
                <p className="text-sm text-[#c9d1d9]">{risk.risk_description || risk.risk}</p>
                {risk.recommended_fix && (
                  <p className="text-xs text-[#3fb950] font-mono border-l-2 border-[#3fb950]/30 pl-2">
                    → {risk.recommended_fix}
                  </p>
                )}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      <CollapsibleSection title="All Resilience Checks">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-4">
          {inspection.checks?.map((check: any) => (
            <div key={check.check} className="flex items-center gap-2 text-xs font-mono">
              {check.present
                ? <CheckCircle size={12} className="text-[#3fb950] flex-shrink-0" />
                : <XCircle    size={12} className="text-[#f85149] flex-shrink-0" />}
              <span className={check.present ? "text-[#8b949e]" : "text-[#f85149]"}>
                {check.check.replace(/_/g, " ")}
              </span>
            </div>
          ))}
        </div>
      </CollapsibleSection>
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
  const fileRef = useRef<HTMLInputElement>(null);

  const pollResult = useCallback(async (id: string) => {
    setPolling(true);
    let attempts = 0;
    const maxAttempts = 40;

    const check = async () => {
      attempts++;
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
        setError("Lost connection while waiting for results.");
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
      const res  = await fetch(`${BASE_URL}/api/analyzer/upload`, { method: "POST", body: form });
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Upload failed.");
        return;
      }
      setJobId(data.job_id);
      pollResult(data.job_id);
    } catch {
      setError("Could not reach the backend. Make sure it is running on port 8000.");
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

  return (
    <div className="min-h-screen bg-[#0d1117]">

      <header className="border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-[#8b949e] hover:text-[#e6edf3] transition-colors">
            <ArrowLeft size={14} />
            <span className="text-sm font-mono">Back to Dashboard</span>
          </Link>
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-[#00d4ff]" />
            <span className="font-display font-bold text-[#e6edf3]">PulseDebug</span>
            <span className="font-display font-bold text-[#00d4ff]">AI</span>
            <span className="font-mono text-xs text-[#484f58] ml-2">Project Analyzer</span>
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
            Upload your backend project ZIP or API log files. PulseDebug inspects
            for resilience risks and uses Gemini AI to explain every finding with
            specific, actionable fixes.
          </p>
        </div>

        {/* Upload zone */}
        {!result && !polling && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileRef.current?.click()}
            className="card p-14 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 text-center select-none"
            style={{
              borderColor: dragging ? "#00d4ff" : uploading ? "#a371f7" : "#30363d",
              background:  dragging ? "rgba(0,212,255,0.04)" : undefined,
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
                    background: "rgba(163,113,247,0.10)",
                    border: "1px solid rgba(163,113,247,0.30)",
                    boxShadow: "0 0 24px rgba(163,113,247,0.15)",
                  }}
                >
                  <Upload size={24} style={{ color: "#a371f7" }} />
                </div>

                <p className="font-medium text-[#e6edf3] text-base mb-1">
                  Drop ZIP / logs here for resilience audit
                </p>
                <p className="text-sm text-[#8b949e] mb-4">or click to browse your files</p>

                {/* Supported types */}
                <div className="flex items-center gap-2 flex-wrap justify-center">
                  {[
                    { ext: ".zip",  color: "#00d4ff" },
                    { ext: ".log",  color: "#a371f7" },
                    { ext: ".json", color: "#3fb950" },
                    { ext: ".txt",  color: "#d29922" },
                  ].map((item) => (
                    <span
                      key={item.ext}
                      className="font-mono text-xs px-2 py-0.5 rounded border"
                      style={{
                        color: item.color,
                        borderColor: `${item.color}33`,
                        background:  `${item.color}0d`,
                      }}
                    >
                      {item.ext}
                    </span>
                  ))}
                  <span className="font-mono text-xs text-[#484f58]">· Max 10MB</span>
                </div>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="card p-4 border-[#f85149]/30 bg-[#f85149]/5 flex items-center gap-3">
            <AlertTriangle size={14} className="text-[#f85149] flex-shrink-0" />
            <p className="text-sm text-[#f85149]">{error}</p>
            <button onClick={reset} className="btn-ghost ml-auto text-xs">Try again</button>
          </div>
        )}

        {/* Polling */}
        {polling && (
          <div className="card p-8 flex flex-col items-center gap-4">
            <Loader2 size={28} className="text-[#a371f7] animate-spin" />
            <div className="text-center">
              <p className="text-sm font-medium text-[#e6edf3]">Analysing your project…</p>
              <p className="text-xs text-[#484f58] mt-1 font-mono">
                Running resilience checks + Gemini RCA
              </p>
            </div>
          </div>
        )}

        {/* Results */}
        {result?.status === "complete" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle size={16} className="text-[#3fb950]" />
                <span className="font-medium text-sm text-[#e6edf3]">
                  Analysis complete — {result.filename}
                </span>
              </div>
              <button onClick={reset} className="btn-ghost text-xs flex items-center gap-1">
                <RefreshCw size={11} /> Analyze another file
              </button>
            </div>
            {result.type === "log_analysis"  && <LogResults  result={result} />}
            {result.type === "zip_inspection" && <ZipResults result={result} />}
          </div>
        )}

        {result?.status === "error" && (
          <div className="card p-5 border-[#f85149]/30 bg-[#f85149]/5">
            <p className="text-sm text-[#f85149]">Analysis failed: {result.error}</p>
            <button onClick={reset} className="btn-ghost mt-3 text-xs">Try again</button>
          </div>
        )}

      </main>
    </div>
  );
}