"use client";
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { axis, axisLabel, Frame, grid, LegendRow, Tip, xAxis } from "./chartTheme";

const bpsFmt = (v: number) => `${v > 0 ? "+" : ""}${Math.round(v)}`;
const tipBps = (v: number) => `${bpsFmt(v)} bps`;
const signFill = (v: number) => (v >= 0 ? "var(--up)" : "var(--down)");
// group 1 (least hedging) in the accent, group 5 (most hedging) in the hedging color, the middle in greys
const QCOLORS = ["var(--accent)", "#9aa6c4", "var(--market)", "#d6a868", "var(--hedge)"];
const QNAMES = ["Group 1 (least hedging)", "Group 2", "Group 3", "Group 4", "Group 5 (most hedging)"];
const cursor = { fill: "var(--panel-2)" };

export function DecileBars({ data, xLabel }: { data: { decile: number; mean_car_bps: number; n_calls: number }[]; xLabel: string }) {
  return (
    <Frame>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 20, left: 0 }}>
          <CartesianGrid {...grid} />
          <XAxis dataKey="decile" {...xAxis} label={axisLabel(xLabel)} />
          <YAxis {...axis} width={48} tickFormatter={bpsFmt} label={{ value: "bps", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }} />
          <ReferenceLine y={0} stroke="var(--line-strong)" />
          <Tooltip cursor={cursor} content={<Tip fmt={tipBps} title={(d) => `Decile ${d}`} />} />
          <Bar dataKey="mean_car_bps" name="Average 2-day return" radius={[3, 3, 3, 3]} maxBarSize={56} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.decile} fill={signFill(d.mean_car_bps)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Frame>
  );
}

export function CarPath({ data }: { data: { quintile: string; day: number; car_bps: number }[] }) {
  const days = Array.from(new Set(data.map((d) => d.day))).sort((a, b) => a - b);
  const rows = days.map((day) => Object.fromEntries([["day", day], ...data.filter((d) => d.day === day).map((d) => [d.quintile, d.car_bps])]));
  return (
    <>
      <LegendRow items={QNAMES.map((label, i) => ({ label, color: QCOLORS[i], thick: i === 0 || i === 4 }))} />
      <Frame height={320}>
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 20, left: 0 }}>
            <CartesianGrid {...grid} />
            <XAxis dataKey="day" {...xAxis} label={axisLabel("Trading days from the first reaction day")} />
            <YAxis {...axis} width={48} tickFormatter={bpsFmt} />
            <ReferenceLine x={0} stroke="var(--muted)" strokeDasharray="4 4" />
            <ReferenceLine y={0} stroke="var(--line-strong)" />
            <Tooltip content={<Tip fmt={tipBps} title={(d) => `Day ${d}`} />} />
            {["Q1", "Q2", "Q3", "Q4", "Q5"].map((q, i) => (
              <Line key={q} dataKey={q} name={QNAMES[i]} stroke={QCOLORS[i]} strokeWidth={i === 0 || i === 4 ? 2.5 : 1.25}
                    strokeOpacity={i === 0 || i === 4 ? 1 : 0.8} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Frame>
    </>
  );
}

export function QuintileBars({ data }: { data: { period: string; quintile: string; mean_car_bps: number }[] }) {
  const periods = Array.from(new Set(data.map((d) => d.period)));
  const [period, setPeriod] = useState(periods[0]);
  const rows = data.filter((d) => d.period === period).map((d) => ({ ...d, label: `Group ${d.quintile.slice(1)}` }));
  return (
    <>
      <div role="tablist" className="chips" style={{ marginBottom: 12 }}>
        {periods.map((p) => (
          <button key={p} role="tab" aria-selected={p === period} onClick={() => setPeriod(p)} className={`chip${p === period ? " on" : ""}`}>
            {p === "In sample" ? "2018 to 2022" : p === "Out of sample" ? "2023 onward" : "All years"}
          </button>
        ))}
      </div>
      <Frame height={260}>
        <ResponsiveContainer>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...grid} />
            <XAxis dataKey="label" {...xAxis} />
            <YAxis {...axis} width={48} tickFormatter={bpsFmt} />
            <ReferenceLine y={0} stroke="var(--line-strong)" />
            <Tooltip cursor={cursor} content={<Tip fmt={tipBps} />} />
            <Bar dataKey="mean_car_bps" name="Average 2-day return" radius={[3, 3, 3, 3]} maxBarSize={88} isAnimationActive={false}>
              {rows.map((d) => <Cell key={d.quintile} fill={signFill(d.mean_car_bps)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Frame>
    </>
  );
}

export function SpreadByQuarter({ data, split }: { data: { quarter: string; spread_bps: number; sample: string }[]; split: string }) {
  return (
    <>
      <LegendRow items={[
        { label: "2018 to 2022 (in sample)", color: "var(--text-2)", dot: true },
        { label: "2023 onward (holdout, lighter)", color: "var(--market)", dot: true },
      ]} />
      <Frame>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...grid} />
            <XAxis dataKey="quarter" {...xAxis} interval={3} />
            <YAxis {...axis} width={48} tickFormatter={bpsFmt} />
            <ReferenceLine y={0} stroke="var(--line-strong)" />
            <ReferenceLine x={split} stroke="var(--accent)" strokeDasharray="4 4" label={{ value: "2023 onward", position: "insideTopRight", fill: "var(--accent)", fontSize: 12 }} />
            <Tooltip cursor={cursor} content={<Tip fmt={tipBps} />} />
            <Bar dataKey="spread_bps" name="Group 1 minus group 5" radius={[2, 2, 2, 2]} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.quarter} fill={signFill(d.spread_bps)} fillOpacity={d.sample === "In sample" ? 1 : 0.5} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Frame>
    </>
  );
}

export function ToneOverTime({ data }: { data: { quarter: string; qa_hedging: number; qa_net_tone: number }[] }) {
  return (
    <>
      <LegendRow items={[
        { label: "Hedging words", color: "var(--hedge)", thick: true },
        { label: "Net tone (positive minus negative)", color: "var(--accent)", thick: true },
      ]} />
      <Frame>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid {...grid} />
            <XAxis dataKey="quarter" {...xAxis} interval={3} />
            <YAxis {...axis} width={36} />
            <Tooltip content={<Tip fmt={(v) => `${v.toFixed(1)} per 1,000`} />} />
            <Line dataKey="qa_hedging" name="Hedging words" stroke="var(--hedge)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="qa_net_tone" name="Net tone" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </Frame>
    </>
  );
}

export function PlaceboHistogram({ tStats, realT }: { tStats: number[]; realT: number }) {
  const edges = Array.from({ length: 13 }, (_, i) => -3 + 0.5 * i);
  const bins = edges.slice(0, -1).map((lo, i) => ({
    mid: lo + 0.25, label: `t from ${lo.toFixed(1)} to ${edges[i + 1].toFixed(1)}`,
    n: tStats.filter((t) => t >= lo && (i === edges.length - 2 ? t <= edges[i + 1] : t < edges[i + 1])).length,
  }));
  return (
    <Frame>
      <ResponsiveContainer>
        <BarChart data={bins} margin={{ top: 22, right: 8, bottom: 20, left: 0 }} barCategoryGap={2}>
          <CartesianGrid {...grid} />
          <XAxis dataKey="mid" type="number" domain={[-3, 3]} ticks={[-3, -2, -1, 0, 1, 2, 3]} {...xAxis} label={axisLabel("t-stat")} />
          <YAxis {...axis} width={32} allowDecimals={false} />
          <ReferenceLine x={-1.96} stroke="var(--muted)" strokeDasharray="3 3" />
          <ReferenceLine x={1.96} stroke="var(--muted)" strokeDasharray="3 3" />
          <ReferenceLine x={realT} stroke="var(--accent)" strokeWidth={2} label={{ value: `real data, t = ${realT.toFixed(2)}`, position: "top", fill: "var(--accent)", fontSize: 12 }} />
          <Tooltip cursor={cursor} content={<Tip fmt={(v) => `${v}`} title={(_, p) => ((p[0] as { payload?: { label?: string } })?.payload?.label ?? "")} />} />
          <Bar dataKey="n" name="Shuffles" fill="var(--market)" radius={[2, 2, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </Frame>
  );
}
