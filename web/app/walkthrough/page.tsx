import type { Metadata } from "next";
import { study } from "@/lib/data";

export const metadata: Metadata = { title: "Project walkthrough" };

const fmt = (v: number, f: string) =>
  f.startsWith("bps") ? `${v > 0 ? "+" : ""}${v.toFixed(Number(f.slice(3)) || 0)} bps`
    : f === "pct" ? `${(100 * v).toFixed(0)}%` : f === "float2" ? v.toFixed(2) : v.toLocaleString();

export default function Walkthrough() {
  const s = study();
  const tests = s.regressions.filter((r) => r.is_test);
  return (
    <>
      <h1>Project walkthrough</h1>
      <p className="lead">
        The question: when executives hedge or dodge questions on an earnings call, does the stock do worse than the
        earnings number alone would predict? Here is how the study was built and what it found.
      </p>

      <h2>What the tests found</h2>
      <p className="takeaway">Effect on the stock’s abnormal return per one standard deviation of each measure, controlling for the earnings surprise. A t-stat beyond ±2 is the usual bar.</p>
      <div className="panel table-scroll">
        <table>
          <thead><tr><th className="l">Question</th><th className="l">Measure</th><th className="l">Window</th><th>Effect</th><th>t-stat</th></tr></thead>
          <tbody>
            {tests.map((r) => (
              <tr key={r.id}>
                <td className="l">{r.hypothesis}: {r.question}</td>
                <td className="l">{r.label}</td>
                <td className="l">{r.window}</td>
                <td>{fmt(r.coef_bps, "bps0")}</td>
                <td>{r.t_stat.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>The steps</h2>
      <ol className="steps">
        {s.project_steps.map((st) => (
          <li key={st.step}>
            <span className="num">{st.step}</span>
            <div>
              <b>{st.title}</b>
              <div>{st.what}</div>
              <div className="muted">Why: {st.why}</div>
              <div><span className="fig">{fmt(st.figure, st.fmt)}</span> <span className="muted">{st.figure_label}</span></div>
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}
