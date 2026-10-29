// Point estimate with a 95% interval (±1.96 SE) per row, in bps. Plain SVG, rendered at build time.
type Row = { label: string; coef: number; se: number; t: number; note?: string; highlight?: boolean };

export default function ForestPlot(props: { rows: Row[]; unit?: string }) {
  return (
    <>
      <div className="wide-only"><Wide {...props} /></div>
      <div className="narrow-only"><Narrow {...props} /></div>
      <p className="note">Filled dot: the 95% range excludes zero (|t| ≥ 1.96). Hollow dot: could be no effect at all.</p>
    </>
  );
}

function scale(rows: Row[]) {
  const lo = Math.min(-50, ...rows.map((r) => r.coef - 1.96 * r.se));
  const hi = Math.max(50, ...rows.map((r) => r.coef + 1.96 * r.se));
  const step = hi - lo > 300 ? 100 : 50;
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
  return { lo, hi, ticks };
}

const stat = (r: Row) => `${r.coef > 0 ? "+" : ""}${Math.round(r.coef)} · ${r.t.toFixed(2)}`;
const tone = (r: Row) => {
  const sig = Math.abs(r.t) >= 1.96;
  return { sig, c: r.highlight ? "var(--accent)" : sig ? "var(--text)" : "var(--muted)" };
};

// phone layout: label and stats on one line, the interval on the full width below
function Narrow({ rows, unit = "bps per 1 SD" }: { rows: Row[]; unit?: string }) {
  const W = 360, rowH = 44, top = 22;
  const { lo, hi, ticks } = scale(rows);
  const x = (v: number) => 8 + ((v - lo) / (hi - lo)) * (W - 16);
  const H = top + rows.length * rowH + 22;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Effect sizes with 95% intervals" style={{ width: "100%", display: "block" }} fontSize="12.5">
      <text x={0} y={12} fill="var(--muted)">{unit} (bar = 95% range) · effect · t</text>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1={top} y2={H - 20} stroke={v === 0 ? "var(--muted)" : "var(--line)"} strokeDasharray={v === 0 ? "4 4" : undefined} />
          <text x={x(v)} y={H - 6} textAnchor="middle" fill="var(--muted)">{v > 0 ? `+${v}` : v}</text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = top + i * rowH;
        const { sig, c } = tone(r);
        return (
          <g key={r.label}>
            <text x={0} y={y + 15} fill="var(--text)" fontWeight={r.highlight ? 650 : 400}>{r.label}</text>
            <text x={W} y={y + 15} textAnchor="end" fill={sig ? "var(--text)" : "var(--muted)"} fontWeight={sig ? 650 : 400}>{stat(r)}</text>
            <line x1={x(r.coef - 1.96 * r.se)} x2={x(r.coef + 1.96 * r.se)} y1={y + 30} y2={y + 30} stroke={c} strokeWidth={2} />
            <circle cx={x(r.coef)} cy={y + 30} r={5} fill={sig ? c : "var(--panel)"} stroke={c} strokeWidth={2} />
          </g>
        );
      })}
    </svg>
  );
}

function Wide({ rows, unit = "bps per 1 SD" }: { rows: Row[]; unit?: string }) {
  const W = 720, labelW = 280, statW = 110, rowH = 30, top = 28;
  const plotW = W - labelW - statW - 16;
  const { lo, hi, ticks } = scale(rows);
  const x = (v: number) => labelW + ((v - lo) / (hi - lo)) * plotW;
  const H = top + rows.length * rowH + 24;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Effect sizes with 95% intervals" style={{ width: "100%", display: "block" }} fontSize="12.5">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1={top - 6} y2={H - 22} stroke={v === 0 ? "var(--muted)" : "var(--line)"} strokeDasharray={v === 0 ? "4 4" : undefined} />
          <text x={x(v)} y={H - 6} textAnchor="middle" fill="var(--muted)">{v > 0 ? `+${v}` : v}</text>
        </g>
      ))}
      <text x={labelW + plotW / 2} y={14} textAnchor="middle" fill="var(--muted)">{unit} (bar = 95% range)</text>
      <text x={W - 8} y={14} textAnchor="end" fill="var(--muted)">effect · t-stat</text>
      {rows.map((r, i) => {
        const y = top + i * rowH + rowH / 2;
        const { sig, c } = tone(r);
        return (
          <g key={r.label}>
            <text x={0} y={y + 4} fill="var(--text)" fontWeight={r.highlight ? 650 : 400}>{r.label}</text>
            <line x1={x(r.coef - 1.96 * r.se)} x2={x(r.coef + 1.96 * r.se)} y1={y} y2={y} stroke={c} strokeWidth={2} />
            <circle cx={x(r.coef)} cy={y} r={5} fill={sig ? c : "var(--panel)"} stroke={c} strokeWidth={2} />
            <text x={W - 8} y={y + 4} textAnchor="end" fill={sig ? "var(--text)" : "var(--muted)"} fontWeight={sig ? 650 : 400}>
              {stat(r)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
