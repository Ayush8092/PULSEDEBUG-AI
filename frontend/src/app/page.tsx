/**
 * PulseDebug AI — Main Dashboard Page
 * File: frontend/src/app/page.tsx
 * Purpose:
 *   Primary dashboard. Updated to use SSE for real-time log streaming,
 *   and adds link to the new External Incidents Feed page.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Upload, Code2, CheckCircle, X, Wifi, WifiOff, Layers } from "lucide-react";
import Header from "@/components/dashboard/Header";
import HealthCards from "@/components/dashboard/HealthCards";
import LiveMetricsChart from "@/components/dashboard/LiveMetricsChart";
import LiveLogFeed from "@/components/dashboard/LiveLogFeed";
import IncidentFeed from "@/components/dashboard/IncidentFeed";
import IncidentDetail from "@/components/dashboard/IncidentDetail";
import DeploymentTimeline from "@/components/dashboard/DeploymentTimeline";
import {
  useStatus, useIncidents, useTimeseries,
  useDeployments, useSSELogs,
} from "@/hooks/usePolling";

type Toast = { id: string; message: string; type: "success"|"info"|"warning" };

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: string) => void }) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg border shadow-xl animate-slide-up"
          style={{
            background:  t.type === "success" ? "rgba(63,185,80,0.12)" : t.type === "warning" ? "rgba(210,153,34,0.12)" : "rgba(0,212,255,0.12)",
            borderColor: t.type === "success" ? "rgba(63,185,80,0.3)"  : t.type === "warning" ? "rgba(210,153,34,0.3)"  : "rgba(0,212,255,0.3)",
          }}
        >
          <CheckCircle size={13} style={{ color: t.type === "success" ? "#3fb950" : t.type === "warning" ? "#d29922" : "#00d4ff" }} />
          <span className="font-mono text-xs text-[#e6edf3]">{t.message}</span>
          <button onClick={() => onDismiss(t.id)} className="ml-2 text-[#484f58] hover:text-[#e6edf3]">
            <X size={11} />
          </button>
        </div>
      ))}
    </div>
  );
}

function ConnectionBadge({ connected }: { connected: boolean | null }) {
  if (connected === null) return null;
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-mono"
      style={{
        background:  connected ? "rgba(63,185,80,0.08)"  : "rgba(248,81,73,0.08)",
        borderColor: connected ? "rgba(63,185,80,0.25)"  : "rgba(248,81,73,0.25)",
        color:       connected ? "#3fb950" : "#f85149",
      }}
    >
      {connected ? <><Wifi size={10} /><span>Backend Connected</span></> : <><WifiOff size={10} /><span>Reconnecting…</span></>}
    </div>
  );
}

export default function DashboardPage() {
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);
  const [toasts,    setToasts]    = useState<Toast[]>([]);
  const [connected, setConnected] = useState<boolean | null>(null);
  const prevIncidentCount = useRef<number>(0);

  const { data: status,    loading: statusLoading }           = useStatus();
  const { data: incidents, loading: incidentsLoading,
          refetch: refetchIncidents }                          = useIncidents("open", "all", "all");
  const { data: timeseries }                                   = useTimeseries(10);
  const { data: deployments }                                  = useDeployments();

  // True SSE streaming — replaces polling for the log feed
  const streamedLogs = useSSELogs(60);

  useEffect(() => {
    if (status !== null) setConnected(true);
  }, [status]);

  useEffect(() => {
    const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const check = async () => {
      try {
        const res = await fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(4000) });
        setConnected(res.ok);
      } catch { setConnected(false); }
    };
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const count = incidents.length;
    if (prevIncidentCount.current > 0 && count > prevIncidentCount.current) {
      addToast("New incident detected — feed updated", "warning");
    }
    prevIncidentCount.current = count;
  }, [incidents.length]);

  const addToast = useCallback((message: string, type: Toast["type"] = "success") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const handleSelectIncident = (id: number) =>
    setSelectedIncidentId(id === selectedIncidentId ? null : id);

  const handleResolved = () => {
    setSelectedIncidentId(null);
    refetchIncidents();
    addToast("Incident resolved successfully", "success");
  };

  const externalCount = incidents.filter((i) => i.source === "external").length;

  return (
    <div className="min-h-screen flex flex-col">
      <Header status={status} connectionBadge={<ConnectionBadge connected={connected} />} />

      <main className="flex-1 max-w-[1600px] mx-auto w-full px-4 lg:px-6 py-4 space-y-4">

        {/* CTA cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Link href="/analyze"
            className="card p-4 flex items-center gap-4 transition-all duration-200 group"
            style={{ borderColor: "rgba(163,113,247,0.25)" }}>
            <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                 style={{ background: "rgba(163,113,247,0.12)", border: "1px solid rgba(163,113,247,0.35)", boxShadow: "0 0 12px rgba(163,113,247,0.15)" }}>
              <Upload size={16} style={{ color: "#a371f7" }} />
            </div>
            <div>
              <p className="font-medium text-sm text-[#e6edf3]">Analyze Your Project</p>
              <p className="text-xs mt-0.5" style={{ color: "#a371f7" }}>Upload ZIP / logs →</p>
            </div>
          </Link>

          <Link href="/integrate"
            className="card p-4 flex items-center gap-4 transition-all duration-200 group"
            style={{ borderColor: "rgba(0,212,255,0.25)" }}>
            <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                 style={{ background: "rgba(0,212,255,0.10)", border: "1px solid rgba(0,212,255,0.30)", boxShadow: "0 0 12px rgba(0,212,255,0.12)" }}>
              <Code2 size={16} style={{ color: "#00d4ff" }} />
            </div>
            <div>
              <p className="font-medium text-sm text-[#e6edf3]">Connect Your API</p>
              <p className="text-xs mt-0.5" style={{ color: "#00d4ff" }}>View integration docs →</p>
            </div>
          </Link>

          <Link href="/incidents"
            className="card p-4 flex items-center gap-4 transition-all duration-200 group"
            style={{ borderColor: "rgba(0,212,255,0.15)" }}>
            <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                 style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.20)" }}>
              <Layers size={16} style={{ color: "#00d4ff" }} />
            </div>
            <div>
              <p className="font-medium text-sm text-[#e6edf3]">External Feed</p>
              <p className="text-xs mt-0.5 font-mono" style={{ color: "#00d4ff" }}>
                {externalCount > 0 ? `${externalCount} external incident${externalCount !== 1 ? "s" : ""}` : "View all incidents →"}
              </p>
            </div>
          </Link>
        </div>

        {/* Health cards */}
        <HealthCards status={status} loading={statusLoading} />

        {/* Main grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2 space-y-5">
            <LiveMetricsChart data={timeseries} />
            <div className="h-[300px]">
              {/* Uses true SSE streaming instead of polling */}
              <LiveLogFeed logs={streamedLogs} />
            </div>
          </div>
          <div className="space-y-4 flex flex-col">
            <div className="flex-1 min-h-[360px]">
              <IncidentFeed
                incidents={incidents}
                loading={incidentsLoading}
                selectedId={selectedIncidentId}
                onSelect={handleSelectIncident}
              />
            </div>
            <DeploymentTimeline deployments={deployments} />
          </div>
        </div>

        {selectedIncidentId !== null && (
          <div className="animate-slide-up">
            <IncidentDetail
              incidentId={selectedIncidentId}
              onResolved={handleResolved}
              onAIComplete={() => addToast("AI analysis complete", "success")}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-[#21262d] py-3 px-6">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between flex-wrap gap-2">
          <span className="font-mono text-xs text-[#484f58]">PulseDebug AI · 100% free infrastructure</span>
          <div className="flex items-center gap-4">
            <Link href="/incidents" className="font-mono text-xs text-[#484f58] hover:text-[#8b949e]">Incident Feed</Link>
            <Link href="/analyze"   className="font-mono text-xs text-[#484f58] hover:text-[#8b949e]">Analyzer</Link>
            <Link href="/integrate" className="font-mono text-xs text-[#484f58] hover:text-[#8b949e]">SDK Docs</Link>
            <span className="font-mono text-xs text-[#484f58]">FastAPI · SQLite · Gemini + Groq</span>
          </div>
        </div>
      </footer>

      <ToastContainer toasts={toasts} onDismiss={(id) => setToasts((p) => p.filter((t) => t.id !== id))} />
    </div>
  );
}