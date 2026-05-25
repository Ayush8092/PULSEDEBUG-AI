/**
 * PulseDebug AI — Live Metrics Chart
 * File: frontend/src/components/dashboard/LiveMetricsChart.tsx
 * Purpose:
 *   Recharts ComposedChart. Production polish:
 *   - Uses browser-local time in tooltips and axis
 *   - No UTC/local mismatch with header clock
 *
 * Author: PulseDebug AI Hackathon Team
 */

"use client";

import {
  ComposedChart,
  Area,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { TimeseriesPoint } from "@/lib/api";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;

  let ts = label;
  try {
    ts = new Date(label).toLocaleTimeString([], {
      hour:   "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {}

  return (
    <div className="card px-3 py-2 text-xs font-mono space-y-1 shadow-xl">
      <p className="text-[#8b949e] mb-1">{ts}</p>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <span style={{ color: p.color }}>■</span>
          <span className="text-[#8b949e]">{p.name}:</span>
          <span style={{ color: p.color }} className="font-medium">
            {p.name === "latency"
              ? `${Math.round(p.value)}ms`
              : p.value}
          </span>
        </div>
      ))}
    </div>
  );
};

function fmtMinute(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour:   "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function LiveMetricsChart({
  data,
}: {
  data: TimeseriesPoint[];
}) {
  const formatted = data.map((d) => ({
    ...d,
    time: fmtMinute(d.minute),
  }));

  if (!data.length) {
    return (
      <div className="card p-6">
        <div className="section-header mb-4">Live Metrics</div>
        <div className="h-48 flex items-center justify-center">
          <span className="font-mono text-sm text-[#484f58]">
            Waiting for traffic data
            <span className="animate-blink">_</span>
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="section-header mb-0">
          Live Metrics — Last 10 Minutes
        </div>
        <div className="flex items-center gap-1.5">
          <span className="live-dot" />
          <span className="text-xs font-mono text-[#3fb950]">
            streaming
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart
          data={formatted}
          margin={{ top: 4, right: 8, bottom: 0, left: -10 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#30363d"
            vertical={false}
          />
          <XAxis
            dataKey="time"
            tick={{
              fill:       "#484f58",
              fontSize:   10,
              fontFamily: "JetBrains Mono",
            }}
            axisLine={{ stroke: "#30363d" }}
            tickLine={false}
          />
          <YAxis
            yAxisId="left"
            tick={{
              fill:       "#484f58",
              fontSize:   10,
              fontFamily: "JetBrains Mono",
            }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{
              fill:       "#484f58",
              fontSize:   10,
              fontFamily: "JetBrains Mono",
            }}
            axisLine={false}
            tickLine={false}
            unit="ms"
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              fontSize:   10,
              fontFamily: "JetBrains Mono",
              color:      "#8b949e",
            }}
          />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="total"
            name="requests"
            stroke="#00d4ff"
            fill="#00d4ff"
            fillOpacity={0.08}
            strokeWidth={1.5}
          />
          <Bar
            yAxisId="left"
            dataKey="errors"
            name="errors"
            fill="#f85149"
            fillOpacity={0.7}
            radius={[2, 2, 0, 0]}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="avg_latency"
            name="latency"
            stroke="#a371f7"
            strokeWidth={1.5}
            dot={false}
            strokeDasharray="4 2"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}