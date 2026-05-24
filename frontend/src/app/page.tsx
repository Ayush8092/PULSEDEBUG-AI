/**
 * PulseDebug AI — Main Dashboard Page
 * File: frontend/src/app/page.tsx
 * Purpose:
 *   The primary (and only) page of the application.
 *   Composes all dashboard panels:
 *
 *   Left column (2/3 width):
 *     - System health cards (4 KPI metrics)
 *     - Live metrics chart
 *     - Live log feed (terminal-style)
 *
 *   Right column (1/3 width):
 *     - Incident feed
 *     - Deployment timeline
 *
 *   Bottom (full width, conditional):
 *     - Incident detail + AI diagnosis panel
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useState } from "react";
import Header from "@/components/dashboard/Header";
import HealthCards from "@/components/dashboard/HealthCards";
import LiveMetricsChart from "@/components/dashboard/LiveMetricsChart";
import LiveLogFeed from "@/components/dashboard/LiveLogFeed";
import IncidentFeed from "@/components/dashboard/IncidentFeed";
import IncidentDetail from "@/components/dashboard/IncidentDetail";
import DeploymentTimeline from "@/components/dashboard/DeploymentTimeline";
import {
  useStatus,
  useIncidents,
  useTimeseries,
  useDeployments,
  useRecentLogs,
} from "@/hooks/usePolling";

export default function DashboardPage() {
  const [selectedIncidentId, setSelectedIncidentId] = useState<number | null>(null);

  const { data: status,     loading: statusLoading }    = useStatus();
  const { data: incidents,  loading: incidentsLoading,
          refetch: refetchIncidents }                    = useIncidents("open");
  const { data: timeseries }                             = useTimeseries(10);
  const { data: deployments }                            = useDeployments();
  const { data: recentLogs }                             = useRecentLogs(60);

  const handleSelectIncident = (id: number) =>
    setSelectedIncidentId(id === selectedIncidentId ? null : id);

  const handleResolved = () => {
    setSelectedIncidentId(null);
    refetchIncidents();
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header status={status} />

      <main className="flex-1 max-w-[1600px] mx-auto w-full px-4 lg:px-6 py-6 space-y-6">

        {/* Row 1 — Health KPIs */}
        <HealthCards status={status} loading={statusLoading} />

        {/* Row 2 — Main grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Left — charts + log feed */}
          <div className="xl:col-span-2 space-y-6">
            <LiveMetricsChart data={timeseries} />
            <div className="h-[300px]">
              <LiveLogFeed logs={recentLogs} />
            </div>
          </div>

          {/* Right — incident feed + deployments */}
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

        {/* Row 3 — Incident detail (conditional) */}
        {selectedIncidentId !== null && (
          <div className="animate-slide-up">
            <IncidentDetail
              incidentId={selectedIncidentId}
              onResolved={handleResolved}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-[#21262d] py-4 px-6">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between">
          <span className="font-mono text-xs text-[#484f58]">
            PulseDebug AI · Hackathon MVP · 100% free infrastructure
          </span>
          <span className="font-mono text-xs text-[#484f58]">
            FastAPI + SQLite · Next.js · Gemini 2.5 Flash
          </span>
        </div>
      </footer>
    </div>
  );
}