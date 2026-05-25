/**
 * PulseDebug AI — Dashboard Header
 * File: frontend/src/components/dashboard/Header.tsx
 * Purpose:
 *   Top navigation bar. Production polish fixes:
 *   - Accepts connectionBadge prop for backend status chip
 *   - Fixed right-side crowding with better spacing
 *   - Softer text brightness on secondary elements
 *   - Uses browser-local time not UTC
 *   - Cleaner alignment throughout
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import { useEffect, useState } from "react";
import { Activity, Cpu, Zap, AlertTriangle } from "lucide-react";
import { SystemStatus } from "@/lib/api";

interface HeaderProps {
  status: SystemStatus | null;
  connectionBadge?: React.ReactNode;
}

export default function Header({ status, connectionBadge }: HeaderProps) {
  const [time, setTime] = useState("");

  useEffect(() => {
    const tick = () =>
      setTime(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const aiStatus = status?.ai;

  return (
    <header className="sticky top-0 z-50 border-b border-[#30363d] bg-[#0d1117]/90 backdrop-blur-sm">
      <div className="max-w-[1600px] mx-auto px-6 h-14 flex items-center justify-between gap-4">

        {/* Logo */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#00d4ff]/10 border border-[#00d4ff]/30">
            <Zap size={16} className="text-[#00d4ff]" />
          </div>
          <div className="flex items-baseline">
            <span className="font-display font-bold text-[#e6edf3] tracking-tight">
              PulseDebug
            </span>
            <span className="font-display font-bold text-[#00d4ff] tracking-tight ml-1">
              AI
            </span>
          </div>
          <div className="hidden md:flex items-center gap-1.5 ml-1 px-2 py-0.5 rounded bg-[#3fb950]/10 border border-[#3fb950]/20">
            <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950] animate-pulse" />
            <span className="text-xs font-mono text-[#3fb950]">LIVE</span>
          </div>
        </div>

        {/* Centre clock */}
        <div className="hidden lg:block">
          <span className="font-mono text-xs text-[#484f58]">{time}</span>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3 flex-shrink-0">

          {connectionBadge}

          {aiStatus && (
            <div className="hidden sm:flex items-center gap-1.5">
              {aiStatus.available ? (
                <>
                  <Cpu size={12} className="text-[#a371f7]" />
                  <span className="font-mono text-xs text-[#484f58]">
                    {aiStatus.active_model}
                  </span>
                </>
              ) : (
                <>
                  <AlertTriangle size={12} className="text-[#d29922]" />
                  <span className="font-mono text-xs text-[#d29922]">
                    AI quota reached
                  </span>
                </>
              )}
            </div>
          )}

          {status && (
            <div className="flex items-center gap-1.5 text-xs font-mono">
              <Activity
                size={12}
                className={
                  (status.critical_incidents || 0) > 0
                    ? "text-[#f85149]"
                    : "text-[#3fb950]"
                }
              />
              <span className="text-[#8b949e]">
                {status.active_incidents} incident
                {status.active_incidents !== 1 ? "s" : ""}
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}