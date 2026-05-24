/**
 * PulseDebug AI — Deployment Timeline
 * File: frontend/src/components/dashboard/DeploymentTimeline.tsx
 * Purpose:
 *   Timeline of recent deployment events. Deployments with linked
 *   incidents are highlighted in yellow to show deployment→incident
 *   correlation visually.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { formatDistanceToNow, parseISO } from "date-fns";
import { GitBranch, AlertTriangle, CheckCircle, Package } from "lucide-react";
import { Deployment } from "@/lib/api";

const timeAgo = (iso: string) => {
  try { return formatDistanceToNow(parseISO(iso), { addSuffix: true }); }
  catch { return iso; }
};

export default function DeploymentTimeline({ deployments }: { deployments: Deployment[] }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch size={13} className="text-[#3fb950]" />
        <span className="section-header mb-0">Recent Deployments</span>
      </div>

      {deployments.length === 0 && (
        <p className="text-xs font-mono text-[#484f58]">
          No deployments yet — waiting for simulator<span className="animate-blink">_</span>
        </p>
      )}

      <div className="relative space-y-0">
        {deployments.length > 1 && (
          <div className="absolute left-[9px] top-3 bottom-3 w-px bg-[#30363d]" />
        )}

        {deployments.map((dep) => {
          const hasIncidents = (dep.linked_incident_count || 0) > 0;
          return (
            <div key={dep.id} className="flex items-start gap-3 py-2 relative">
              <div className={`w-[18px] h-[18px] rounded-full border-2 flex items-center justify-center flex-shrink-0 mt-0.5 bg-[#0d1117] ${
                hasIncidents ? "border-[#d29922]" : "border-[#3fb950]"
              }`}>
                {hasIncidents
                  ? <AlertTriangle size={8} className="text-[#d29922]" />
                  : <CheckCircle   size={8} className="text-[#3fb950]" />}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm font-medium text-[#e6edf3]">{dep.version}</span>
                  {hasIncidents && (
                    <span className="text-xs font-mono text-[#d29922] bg-[#d29922]/10 px-1.5 py-0.5 rounded border border-[#d29922]/20">
                      {dep.linked_incident_count} incident{dep.linked_incident_count !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <Package size={10} className="text-[#484f58]" />
                  <span className="font-mono text-xs text-[#484f58]">{dep.service}</span>
                  <span className="text-[#484f58]">·</span>
                  <span className="font-mono text-xs text-[#484f58]">{timeAgo(dep.deployed_at)}</span>
                </div>
                {dep.notes && (
                  <p className="text-xs text-[#8b949e] mt-1 leading-relaxed line-clamp-2">{dep.notes}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}