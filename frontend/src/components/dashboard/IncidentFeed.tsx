/**
 * PulseDebug AI — Incident Feed
 * File: frontend/src/components/dashboard/IncidentFeed.tsx
 * Purpose:
 *   Scrollable list of active incidents sorted by severity and recency.
 *   Each row shows severity badge, title, service, occurrence count,
 *   deployment-correlation flag, and time since first detection.
 *   Clicking a row selects it and opens the detail panel.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { formatDistanceToNow, parseISO } from "date-fns";
import { Layers, GitBranch, ChevronRight, RefreshCw } from "lucide-react";
import { Incident } from "@/lib/api";

interface IncidentFeedProps {
  incidents:  Incident[];
  loading:    boolean;
  selectedId: number | null;
  onSelect:   (id: number) => void;
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    critical: "badge-critical", warning: "badge-warning", investigate: "badge-investigate",
  };
  const lbl: Record<string, string> = {
    critical: "CRITICAL", warning: "WARNING", investigate: "INVESTIGATE",
  };
  return <span className={cls[severity] || "badge-investigate"}>{lbl[severity] || severity.toUpperCase()}</span>;
}

function timeAgo(iso: string) {
  try { return formatDistanceToNow(parseISO(iso), { addSuffix: true }); }
  catch { return iso; }
}

export default function IncidentFeed({ incidents, loading, selectedId, onSelect }: IncidentFeedProps) {
  return (
    <div className="card flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#30363d]">
        <div className="flex items-center gap-2">
          <Layers size={14} className="text-[#00d4ff]" />
          <span className="font-medium text-sm text-[#e6edf3]">Incident Feed</span>
        </div>
        {loading
          ? <RefreshCw size={12} className="text-[#484f58] animate-spin" />
          : <span className="font-mono text-xs text-[#484f58]">{incidents.length} open</span>
        }
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-[#21262d]">
        {incidents.length === 0 && !loading && (
          <div className="px-5 py-8 text-center">
            <div className="text-[#3fb950] text-2xl mb-2">✓</div>
            <p className="text-sm text-[#8b949e]">No active incidents</p>
            <p className="text-xs text-[#484f58] mt-1 font-mono">All systems operational</p>
          </div>
        )}

        {loading && incidents.length === 0 && [...Array(4)].map((_, i) => (
          <div key={i} className="px-5 py-4 space-y-2">
            <div className="h-3 w-40 bg-[#21262d] rounded animate-pulse" />
            <div className="h-3 w-64 bg-[#21262d] rounded animate-pulse" />
            <div className="h-3 w-24 bg-[#21262d] rounded animate-pulse" />
          </div>
        ))}

        {incidents.map((inc) => (
          <button
            key={inc.id}
            onClick={() => onSelect(inc.id)}
            className={`w-full text-left px-5 py-4 transition-all duration-150 hover:bg-[#1c2128] group ${
              selectedId === inc.id ? "bg-[#1c2128] border-l-2 border-[#00d4ff]" : ""
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <SeverityBadge severity={inc.severity} />
              <ChevronRight size={12} className={`text-[#484f58] mt-0.5 flex-shrink-0 transition-transform ${
                selectedId === inc.id ? "text-[#00d4ff] translate-x-0.5" : "group-hover:translate-x-0.5"
              }`} />
            </div>
            <p className="text-sm font-medium text-[#e6edf3] leading-snug mb-1">{inc.title}</p>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="code text-xs">{inc.service}</span>
              <span className="font-mono text-xs text-[#484f58]">{inc.endpoint}</span>
            </div>
            <div className="flex items-center gap-4 mt-2">
              <span className="font-mono text-xs text-[#8b949e]">{inc.occurrence_count} events</span>
              {inc.deployment_related === 1 && (
                <span className="flex items-center gap-1 text-xs font-mono text-[#d29922]">
                  <GitBranch size={10} /> deploy-related
                </span>
              )}
              <span className="font-mono text-xs text-[#484f58] ml-auto">{timeAgo(inc.first_detected)}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}