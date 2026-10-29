"use client";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WindowPoint } from "@/lib/data";

export default function WindowChart({ data, ticker }: { data: WindowPoint[]; ticker: string }) {
  const fmt = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
  return (
    <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="day" stroke="var(--muted)" fontSize={12}
                 label={{ value: "Trading days from the first reaction day", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
          <YAxis stroke="var(--muted)" fontSize={12} width={60} tickFormatter={fmt} />
          <ReferenceLine x={0} stroke="var(--muted)" strokeDasharray="4 4" />
          <ReferenceLine y={0} stroke="var(--line)" />
          <Tooltip formatter={(v: number) => fmt(v)} labelFormatter={(d) => `Day ${d}`}
                   contentStyle={{ background: "var(--panel)", border: "1px solid var(--line)", fontSize: 13 }} />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 13 }} />
          <Line dataKey="stock_pct" name={ticker} stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="market_pct" name="S&P 500 (SPY)" stroke="var(--market)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
