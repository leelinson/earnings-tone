import type { Metadata } from "next";
import { PageHead, Section } from "@/components/ui";
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
      <PageHead
        eyebrow="Project walkthrough"
        title="How the study was built, step by step"
        lead={<>The question: when executives hedge or dodge questions on an earnings call, does the stock do worse than the
          earnings number alone would predict? Here is how the study was built and what it found.</>}
      />

      <div className="stack">
        <Section title="What the tests found"
          takeaway="Effect on the stock’s abnormal return per one standard deviation of each measure, controlling for the earnings surprise. A t-stat beyond ±2 is the usual bar."
          flush>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Question</th><th className="l">Measure</th><th className="l">Window</th><th>Effect</th><th>t-stat</th></tr></thead>
              <tbody>
                {tests.map((r) => (
                  <tr key={r.id}>
                    <td className="l"><b>{r.hypothesis}</b> {r.question}</td>
                    <td className="l">{r.label}</td>
                    <td className="l">{r.window}</td>
                    <td>{fmt(r.coef_bps, "bps0")}</td>
                    <td>{r.t_stat.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title={`The ${s.project_steps.length} steps`}>
          <ol className="steps">
            {s.project_steps.map((st) => (
              <li key={st.step}>
                <span className="dot">{st.step}</span>
                <div>
                  <h3>{st.title}</h3>
                  <p className="what">{st.what}</p>
                  <p className="why">Why: {st.why}</p>
                  <span className="fig"><b>{fmt(st.figure, st.fmt)}</b><span className="muted">{st.figure_label}</span></span>
                </div>
              </li>
            ))}
          </ol>
        </Section>
      </div>
    </>
  );
}
