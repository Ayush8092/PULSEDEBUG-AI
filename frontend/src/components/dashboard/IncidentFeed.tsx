/**
 * PulseDebug AI — Incident Feed
 * File: frontend/src/components/dashboard/IncidentFeed.tsx
 * Purpose:
 *   Scrollable list of active incidents.
 *   Fix: the auto-scroll to top on new incident no longer scrolls the
 *   whole page. It only scrolls the internal list container, and only
 *   when the container is already visible in the viewport. If the user
 *   is reading something else on the page the feed stays put.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { Layers, GitBranch, ChevronRight, RefreshCw } from "lucide-react";
import { Incident } from "@/lib/api";

function useRelativeTime(isoString: string): string {
  const [label, setLabel] = useState("");

  useEffect(() => {
    const compute = () => {
      try {
        const diff = Math.floor(
          (Date.now() - new Date(isoString).getTime()) / 1000
        );
        if (diff < 60)    return `${diff}s ago`;
        if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
      } catch {
        return "";
      }
    };
    setLabel(compute());
    const t = setInterval(() => setLabel(compute()), 30_000);
    return () => clearInterval(t);
  }, [isoString]);

  return label;
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    critical:    "badge-critical",
    warning:     "badge-warning",
    investigate: "badge-investigate",
  };
  const lbl: Record<string, string> = {
    critical:    "CRITICAL",
    warning:     "WARNING",
    investigate: "INVESTIGATE",
  };
  return (
    <span className={cls[severity] || "badge-investigate"}>
      {lbl[severity] || severity.toUpperCase()}
    </span>
  );
}

function IncidentRow({
  inc,
  selected,
  isNew,
  onSelect,
}: {
  inc:      Incident;
  selected: boolean;
  isNew:    boolean;
  onSelect: () => void;
}) {
  const timeLabel = useRelativeTime(inc.first_detected);
  const [highlight, setHighlight] = useState(false);

  useEffect(() => {
    if (isNew) {
      setHighlight(true);
      const t = setTimeout(() => setHighlight(false), 2500);
      return () => clearTimeout(t);
    }
  }, [isNew]);

  return (
    <button
      onClick={onSelect}
      className="w-full text-left px-5 py-4 transition-all duration-200 hover:bg-[#1c2128] group"
      style={{
        borderLeft: selected
          ? "2px solid #00d4ff"
          : highlight
          ? "2px solid #d29922"
          : "2px solid transparent",
        background: highlight
          ? "rgba(210,153,34,0.04)"
          : selected
          ? "#1c2128"
          : undefined,
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <SeverityBadge severity={inc.severity} />
        <ChevronRight
          size={12}
          className={`text-[#484f58] mt-0.5 flex-shrink-0 transition-transform duration-150 ${
            selected
              ? "text-[#00d4ff] translate-x-0.5"
              : "group-hover:translate-x-0.5"
          }`}
        />
      </div>

      <p className="text-sm font-medium text-[#e6edf3] leading-snug mb-1 text-left">
        {inc.title}
      </p>

      <div className="flex items-center gap-3 flex-wrap">
        <span className="code text-xs">{inc.service}</span>
        <span className="font-mono text-xs text-[#484f58]">
          {inc.endpoint}
        </span>
      </div>

      <div className="flex items-center gap-4 mt-2">
        <span className="font-mono text-xs text-[#8b949e]">
          {inc.occurrence_count} events
        </span>
        {inc.deployment_related === 1 && (
          <span className="flex items-center gap-1 text-xs font-mono text-[#d29922]">
            <GitBranch size={10} />
            deploy-related
          </span>
        )}
        <span className="font-mono text-xs text-[#484f58] ml-auto">
          {timeLabel}
        </span>
      </div>
    </button>
  );
}

interface IncidentFeedProps {
  incidents:  Incident[];
  loading:    boolean;
  selectedId: number | null;
  onSelect:   (id: number) => void;
}

export default function IncidentFeed({
  incidents,
  loading,
  selectedId,
  onSelect,
}: IncidentFeedProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const prevIds = useRef<Set<number>>(new Set());
  const [newIds, setNewIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    const incoming = new Set(incidents.map((i) => i.id));
    const added    = new Set<number>();

    incoming.forEach((id) => {
      if (!prevIds.current.has(id)) added.add(id);
    });

    if (added.size > 0) {
      setNewIds(added);

      // Only scroll inside the container if it is already visible
      // in the viewport — never force the whole page to scroll down
      if (listRef.current) {
        const rect = listRef.current.getBoundingClientRect();
        const isVisible =
          rect.top >= 0 &&
          rect.bottom <= (window.innerHeight || document.documentElement.clientHeight);

        if (isVisible) {
          listRef.current.scrollTo({ top: 0, behavior: "smooth" });
        }
      }

      setTimeout(() => setNewIds(new Set()), 3000);
    }

    prevIds.current = incoming;
  }, [incidents]);

  return (
    <div className="card flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#30363d]">
        <div className="flex items-center gap-2">
          <Layers size={14} className="text-[#00d4ff]" />
          <span className="font-medium text-sm text-[#e6edf3]">
            Incident Feed
          </span>
        </div>
        {loading ? (
          <RefreshCw size={12} className="text-[#484f58] animate-spin" />
        ) : (
          <span className="font-mono text-xs text-[#484f58]">
            {incidents.length} open
          </span>
        )}
      </div>

      {/* List — internal scroll only, never affects page position */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto divide-y divide-[#21262d]"
      >
        {incidents.length === 0 && !loading && (
          <div className="px-5 py-8 text-center">
            <div className="text-[#3fb950] text-2xl mb-2">✓</div>
            <p className="text-sm text-[#8b949e]">No active incidents</p>
            <p className="text-xs text-[#484f58] mt-1 font-mono">
              All systems nominal
            </p>
          </div>
        )}

        {loading &&
          incidents.length === 0 &&
          [...Array(4)].map((_, i) => (
            <div key={i} className="px-5 py-4 space-y-2">
              <div className="h-3 w-40 bg-[#21262d] rounded animate-pulse" />
              <div className="h-3 w-64 bg-[#21262d] rounded animate-pulse" />
              <div className="h-3 w-24 bg-[#21262d] rounded animate-pulse" />
            </div>
          ))}

        {incidents.map((inc) => (
          <IncidentRow
            key={inc.id}
            inc={inc}
            selected={selectedId === inc.id}
            isNew={newIds.has(inc.id)}
            onSelect={() => onSelect(inc.id)}
          />
        ))}
      </div>
    </div>
  );
}