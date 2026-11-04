"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WindowPoint } from "@/lib/data";
import { axis, axisLabel, Frame, grid, LegendRow, Tip, xAxis } from "./chartTheme";

export default function WindowChart({ data, ticker }: { data: WindowPoint[]; ticker: string }) {
  const fmt = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
  return (
    <>
      <LegendRow items={[{ label: ticker, color: "var(--accent)", thick: true }, { label: "S&P 500 (SPY)", color: "var(--market)" }]} />
      <Frame>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 20, left: 0 }}>
            <CartesianGrid {...grid} />
            <XAxis dataKey="day" {...xAxis} label={axisLabel("Trading days from the first reaction day")} />
            <YAxis {...axis} width={56} tickFormatter={fmt} />
            <ReferenceLine x={0} stroke="var(--muted)" strokeDasharray="4 4" />
            <ReferenceLine y={0} stroke="var(--line-strong)" />
            <Tooltip content={<Tip fmt={fmt} title={(d) => `Day ${d}`} />} />
            <Line dataKey="stock_pct" name={ticker} stroke="var(--accent)" strokeWidth={2.25} dot={false} isAnimationActive={false} />
            <Line dataKey="market_pct" name="S&P 500" stroke="var(--market)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </Frame>
    </>
  );
}
