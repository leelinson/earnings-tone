"use client";
// One look for every Recharts chart: quiet axes, dashed gridlines, the same tooltip card.
import type { TooltipProps } from "recharts";

export const axis = {
  stroke: "var(--line-strong)", fontSize: 12, tickLine: false, axisLine: false,
  tick: { fill: "var(--muted)" },
} as const;
export const xAxis = { ...axis, axisLine: { stroke: "var(--line-strong)" } } as const;
export const grid = { stroke: "var(--line)", strokeDasharray: "3 4", vertical: false } as const;
export const axisLabel = (value: string) => ({ value, position: "insideBottom" as const, offset: -12, fill: "var(--muted)", fontSize: 12 });

export function Tip({ active, payload, label, title, fmt }: TooltipProps<number, string> & {
  title?: (label: unknown, payload: unknown[]) => React.ReactNode; fmt?: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <div className="t">{title ? title(label, payload) : String(label)}</div>
      {payload.map((p) => (
        <div className="r" key={String(p.dataKey)}>
          <span className="sw" style={{ background: p.color || "var(--muted)" }} />
          <span>{p.name}</span>
          <b style={{ marginLeft: "auto" }}>{fmt ? fmt(Number(p.value)) : p.value}</b>
        </div>
      ))}
    </div>
  );
}

export function LegendRow({ items }: { items: { label: string; color: string; dot?: boolean; thick?: boolean }[] }) {
  return (
    <div className="legend" aria-hidden="true">
      {items.map((i) => (
        <span key={i.label}><i className={i.dot ? "dot" : ""} style={{ background: i.color, height: i.dot ? undefined : i.thick ? 3 : 2 }} />{i.label}</span>
      ))}
    </div>
  );
}

export function Frame({ height = 280, children }: { height?: number; children: React.ReactNode }) {
  return <div style={{ width: "100%", height }}>{children}</div>;
}
