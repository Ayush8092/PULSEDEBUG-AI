/**
 * PulseDebug AI — Dashboard Header
 * File: frontend/src/components/dashboard/Header.tsx
 * Purpose:
 *   Top navigation bar. Shows the PulseDebug logo, a LIVE indicator,
 *   current AI model badge, active incident count, and UTC clock.
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useEffect, useState } from "react";
import { Activity, Cpu, Zap, AlertTriangle } from "lucide-react";
import { SystemStatus } from "@/lib/api";

interface HeaderProps { status: SystemStatus | null; }

export default function Header({ status }: HeaderProps) {
  const [time, setTime] = useState("");

  useEffect(() => {
    const tick = () => setTime(new Date().toUTCString().replace("GMT", "UTC"));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const aiStatus = status?.ai;

  return (
    <header className="sticky top-0 z-50 border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm">
      <div className="max-w-[1600px] mx-auto px-6 h-14 flex items-center justify-between">

        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#00d4ff]/10 border border-[#00d4ff]/30">
            <Zap size={16} className="text-[#00d4ff]" />
          </div>
          <div>
            <span className="font-display font-bold text-[#e6edf3] tracking-tight">PulseDebug</span>
            <span className="font-display font-bold text-[#00d4ff] tracking-tight ml-1">AI</span>
          </div>
          <div className="hidden md:flex items-center gap-1.5 ml-3 px-2 py-0.5 rounded bg-[#3fb950]/10 border border-[#3fb950]/20">
            <span className="live-dot" />
            <span className="text-xs font-mono text-[#3fb950]">LIVE</span>
          </div>
        </div>

        {/* Centre — UTC clock */}
        <div className="hidden lg:block">
          <span className="font-mono text-xs text-[#484f58]">{time}</span>
        </div>

        {/* Right — AI status + incident count */}
        <div className="flex items-center gap-4">
          {aiStatus && (
            <div className="hidden sm:flex items-center gap-2">
              {aiStatus.available ? (
                <>
                  <Cpu size={13} className="text-[#a371f7]" />
                  <span className="font-mono text-xs text-[#8b949e]">{aiStatus.active_model}</span>
                </>
              ) : (
                <>
                  <AlertTriangle size={13} className="text-[#d29922]" />
                  <span className="font-mono text-xs text-[#d29922]">AI quota reached</span>
                </>
              )}
            </div>
          )}
          {status && (
            <div className="flex items-center gap-1.5 text-xs font-mono">
              <Activity size={13} className={(status.critical_incidents || 0) > 0 ? "text-[#f85149]" : "text-[#3fb950]"} />
              <span className="text-[#8b949e]">
                {status.active_incidents} active incident{status.active_incidents !== 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}