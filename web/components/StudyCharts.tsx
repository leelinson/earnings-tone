"use client";
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const axis = { stroke: "var(--muted)", fontSize: 12 };
const tip = { contentStyle: { background: "var(--panel)", border: "1px solid var(--line)", fontSize: 13 } };
const bpsFmt = (v: number) => `${v > 0 ? "+" : ""}${Math.round(v)}`;
const tipBps = (v: number) => `${bpsFmt(v)} bps`;
const signFill = (v: number) => (v >= 0 ? "var(--up)" : "var(--down)");
const QCOLORS = ["var(--up)", "#6aa985", "var(--market)", "#d08a6f", "var(--down)"];

function Frame({ height = 280, children }: { height?: number; children: React.ReactElement }) {
  return <div style={{ width: "100%", height }}><ResponsiveContainer>{children}</ResponsiveContainer></div>;
}

export function DecileBars({ data, xLabel }: { data: { decile: number; mean_car_bps: number; n_calls: number }[]; xLabel: string }) {
  return (
    <Frame>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="decile" {...axis} label={{ value: xLabel, position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
        <YAxis {...axis} width={52} tickFormatter={bpsFmt} label={{ value: "bps", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }} />
        <ReferenceLine y={0} stroke="var(--muted)" />
        <Tooltip {...tip} formatter={tipBps} labelFormatter={(d) => `Decile ${d}`} />
        <Bar dataKey="mean_car_bps" name="Average 2-day return" isAnimationActive={false}>
          {data.map((d) => <Cell key={d.decile} fill={signFill(d.mean_car_bps)} />)}
        </Bar>
      </BarChart>
    </Frame>
  );
}

export function CarPath({ data }: { data: { quintile: string; day: number; car_bps: number }[] }) {
  const days = Array.from(new Set(data.map((d) => d.day))).sort((a, b) => a - b);
  const rows = days.map((day) => Object.fromEntries([["day", day], ...data.filter((d) => d.day === day).map((d) => [d.quintile, d.car_bps])]));
  const names: Record<string, string> = { Q1: "Group 1 (least hedging)", Q5: "Group 5 (most hedging)" };
  return (
    <Frame height={320}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="day" {...axis} label={{ value: "Trading days from the first reaction day", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
        <YAxis {...axis} width={52} tickFormatter={bpsFmt} />
        <ReferenceLine x={0} stroke="var(--muted)" strokeDasharray="4 4" />
        <ReferenceLine y={0} stroke="var(--line)" />
        <Tooltip {...tip} formatter={tipBps} labelFormatter={(d) => `Day ${d}`} />
        <Legend verticalAlign="top" wrapperStyle={{ fontSize: 13, paddingBottom: 8 }} />
        {["Q1", "Q2", "Q3", "Q4", "Q5"].map((q, i) => (
          <Line key={q} dataKey={q} name={names[q] ?? `Group ${q.slice(1)}`} stroke={QCOLORS[i]} strokeWidth={q === "Q1" || q === "Q5" ? 2.5 : 1.25} dot={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </Frame>
  );
}

export function QuintileBars({ data }: { data: { period: string; quintile: string; mean_car_bps: number }[] }) {
  const periods = Array.from(new Set(data.map((d) => d.period)));
  const [period, setPeriod] = useState(periods[0]);
  const rows = data.filter((d) => d.period === period).map((d) => ({ ...d, label: `Group ${d.quintile.slice(1)}` }));
  return (
    <>
      <div role="tablist" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
        {periods.map((p) => (
          <button key={p} role="tab" aria-selected={p === period} onClick={() => setPeriod(p)} className={`chip${p === period ? " on" : ""}`}>
            {p === "In sample" ? "2018 to 2022" : p === "Out of sample" ? "2023 onward" : "All years"}
          </button>
        ))}
      </div>
      <Frame height={260}>
        <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="label" {...axis} />
          <YAxis {...axis} width={52} tickFormatter={bpsFmt} />
          <ReferenceLine y={0} stroke="var(--muted)" />
          <Tooltip {...tip} formatter={tipBps} />
          <Bar dataKey="mean_car_bps" name="Average 2-day return" isAnimationActive={false}>
            {rows.map((d) => <Cell key={d.quintile} fill={signFill(d.mean_car_bps)} />)}
          </Bar>
        </BarChart>
      </Frame>
    </>
  );
}

export function SpreadByQuarter({ data, split }: { data: { quarter: string; spread_bps: number; sample: string }[]; split: string }) {
  return (
    <Frame>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="quarter" {...axis} interval={3} />
        <YAxis {...axis} width={52} tickFormatter={bpsFmt} />
        <ReferenceLine y={0} stroke="var(--muted)" />
        <ReferenceLine x={split} stroke="var(--accent)" strokeDasharray="4 4" label={{ value: "2023 onward", position: "insideTopRight", fill: "var(--accent)", fontSize: 12 }} />
        <Tooltip {...tip} formatter={tipBps} />
        <Bar dataKey="spread_bps" name="Group 1 minus group 5" isAnimationActive={false}>
          {data.map((d) => <Cell key={d.quarter} fill={signFill(d.spread_bps)} fillOpacity={d.sample === "In sample" ? 1 : 0.55} />)}
        </Bar>
      </BarChart>
    </Frame>
  );
}

export function ToneOverTime({ data }: { data: { quarter: string; qa_hedging: number; qa_net_tone: number }[] }) {
  return (
    <Frame>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="quarter" {...axis} interval={3} />
        <YAxis {...axis} width={40} />
        <Tooltip {...tip} formatter={(v: number) => `${v.toFixed(1)} per 1,000 words`} />
        <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: 13 }} />
        <Line dataKey="qa_hedging" name="Hedging words" stroke="var(--hedge)" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line dataKey="qa_net_tone" name="Net tone (positive minus negative)" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </Frame>
  );
}

export function PlaceboHistogram({ tStats, realT }: { tStats: number[]; realT: number }) {
  const edges = Array.from({ length: 13 }, (_, i) => -3 + 0.5 * i);
  const bins = edges.slice(0, -1).map((lo, i) => ({
    mid: lo + 0.25, label: `${lo.toFixed(1)} to ${edges[i + 1].toFixed(1)}`,
    n: tStats.filter((t) => t >= lo && (i === edges.length - 2 ? t <= edges[i + 1] : t < edges[i + 1])).length,
  }));
  return (
    <Frame>
      <BarChart data={bins} margin={{ top: 16, right: 12, bottom: 18, left: 0 }} barCategoryGap={1}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis dataKey="mid" type="number" domain={[-3, 3]} ticks={[-3, -2, -1, 0, 1, 2, 3]} {...axis}
               label={{ value: "t-stat", position: "insideBottom", offset: -10, fill: "var(--muted)", fontSize: 12 }} />
        <YAxis {...axis} width={36} allowDecimals={false} />
        <ReferenceLine x={-1.96} stroke="var(--muted)" strokeDasharray="3 3" />
        <ReferenceLine x={1.96} stroke="var(--muted)" strokeDasharray="3 3" />
        <ReferenceLine x={realT} stroke="var(--accent)" strokeWidth={2} label={{ value: `real data, t = ${realT.toFixed(2)}`, position: "top", fill: "var(--accent)", fontSize: 12 }} />
        <Tooltip {...tip} formatter={(v: number) => `${v} shuffles`} labelFormatter={(_, p) => (p?.[0]?.payload as { label?: string })?.label ?? ""} />
        <Bar dataKey="n" name="Shuffles" fill="var(--market)" isAnimationActive={false} />
      </BarChart>
    </Frame>
  );
}
