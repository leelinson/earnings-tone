"use client";
import { useRouter } from "next/navigation";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";

type Dot = { t: number; price: number; date: string; car: number | null; href: string };

const ms = (d: string) => Date.parse(`${d}T00:00:00Z`);
const yearTick = (t: number) => new Date(t).getUTCFullYear().toString();

export default function PriceChart({ prices, calls }: {
  prices: { date: string; adj_close: number }[];
  calls: { call_date: string; reaction_day: string | null; car_0_1: number | null; href: string }[];
}) {
  const router = useRouter();
  const line = prices.map((p) => ({ t: ms(p.date), price: p.adj_close }));
  // put each call on the weekly line at the close of the week that holds its reaction day
  const dots: Dot[] = calls.flatMap((c) => {
    const t = ms(c.reaction_day ?? c.call_date);
    const before = line.filter((p) => p.t <= t + 6 * 864e5);
    const at = before.length ? before[before.length - 1] : undefined;
    return at ? [{ t, price: at.price, date: c.call_date, car: c.car_0_1, href: c.href }] : [];
  });
  const years = Array.from(new Set(line.map((p) => new Date(p.t).getUTCFullYear())));
  const ticks = years.map((y) => Date.UTC(y, 0, 1)).filter((t) => t >= line[0].t);
  const color = (car: number | null) => (car == null ? "var(--market)" : car >= 0 ? "var(--up)" : "var(--down)");
  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <ComposedChart margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={yearTick} ticks={ticks}
                 stroke="var(--muted)" fontSize={12} allowDuplicatedCategory={false} />
          <YAxis dataKey="price" stroke="var(--muted)" fontSize={12} width={48} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            cursor={false}
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as (Dot & { price: number }) | undefined;
              if (!active || !p) return null;
              return (
                <div className="panel" style={{ padding: "6px 10px", fontSize: 13 }}>
                  {"date" in p && p.date ? (
                    <>Call {p.date} · 2-day reaction{" "}
                      <b style={{ color: color(p.car) }}>{p.car == null ? "n/a" : `${p.car > 0 ? "+" : ""}${(100 * p.car).toFixed(1)}%`}</b>
                      <br /><span className="muted">click to open</span></>
                  ) : (
                    <>{new Date(p.t).toISOString().slice(0, 10)} · ${p.price.toFixed(2)}</>
                  )}
                </div>
              );
            }}
          />
          <Line data={line} dataKey="price" stroke="var(--accent)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Scatter
            data={dots}
            dataKey="price"
            isAnimationActive={false}
            onClick={(d: { payload?: Dot }) => d.payload && router.push(d.payload.href)}
            shape={(props: { cx?: number; cy?: number; payload?: Dot }) => (
              <circle cx={props.cx} cy={props.cy} r={4.5} fill={color(props.payload?.car ?? null)}
                      stroke="var(--panel)" strokeWidth={1.5} style={{ cursor: "pointer" }} />
            )}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
