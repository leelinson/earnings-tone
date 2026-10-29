import type { Metadata } from "next";
import ForestPlot from "@/components/ForestPlot";
import { PlaceboHistogram } from "@/components/StudyCharts";
import { study } from "@/lib/data";

export const metadata: Metadata = { title: "Does it hold up?" };

const VERDICTS: Record<string, string> = {
  H1: "Not supported. Hedging points the expected way but is within the range of luck.",
  H2: "Not supported. Evasive answers show no link to the reaction.",
  H3: "Not supported. The gap between scripted and Q&A tone does not predict the next month.",
  H4: "Not supported. Tone does not matter more when the surprise is small.",
};

export default function Robustness() {
  const s = study();
  const sum = s.summary[0];
  const main = s.robustness.map((r) => ({
    label: r.check, coef: r.coef_bps, se: r.se_bps, t: r.t_stat, highlight: r.check === "Main result",
  }));
  const tests = s.regressions.filter((r) => r.is_test);
  return (
    <>
      <h1>Does it hold up?</h1>
      <p className="lead">
        The combined hedging-plus-evasiveness score stays small and insignificant however the sample is cut, and
        shuffled fake scores look just like it. The one exception, Q&amp;A net tone, is a lead to test on new data, not
        a finding.
      </p>

      <h2>The main result under different choices</h2>
      <p className="takeaway"><b>Takeaway:</b> every version of the combined score lands between about −55 and +28 bps with a t-stat under 1.6 in size; only net tone, a different measure, clears 2.</p>
      <div className="panel"><ForestPlot rows={main} /></div>

      <h2>Placebo: shuffled tone scores</h2>
      <p className="takeaway">
        <b>Takeaway:</b> tone scores were shuffled among calls in the same quarter 100 times. The real result
        (t = {sum.real_composite_t.toFixed(2)}) sits inside the pile of fake ones; {Math.round(100 * sum.placebo_share_sig)}% of fakes passed ±1.96, about the 5% luck alone gives.
      </p>
      <div className="panel"><PlaceboHistogram tStats={s.placebo.map((p) => p.t_stat)} realT={sum.real_composite_t} /></div>

      <h2>Verdict on each hypothesis</h2>
      <div className="panel table-scroll">
        <table>
          <thead><tr><th className="l">Hypothesis</th><th className="l">Measure</th><th>Effect</th><th>t-stat</th><th className="l">Verdict</th></tr></thead>
          <tbody>
            {tests.map((r) => (
              <tr key={r.id}>
                <td className="l">{r.hypothesis}: {r.question}</td>
                <td className="l">{r.label}</td>
                <td>{r.coef_bps > 0 ? "+" : ""}{Math.round(r.coef_bps)} bps</td>
                <td>{r.t_stat.toFixed(2)}</td>
                <td className="l" style={{ whiteSpace: "normal", minWidth: 260 }}>{VERDICTS[r.hypothesis]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Full regression table</h2>
      <p className="takeaway">Each model controls for sector × quarter and clusters errors by firm. Coefficients in bps per 1 SD.</p>
      <div className="panel table-scroll">
        <table>
          <thead><tr><th className="l">Model</th><th className="l">Variable</th><th className="l">Window</th><th>Coef</th><th>SE</th><th>t</th><th>p</th><th>N</th><th>R²</th></tr></thead>
          <tbody>
            {s.regressions.map((r) => (
              <tr key={r.id}>
                <td className="l">{r.hypothesis}</td>
                <td className="l">{r.label}</td>
                <td className="l">{r.window}</td>
                <td>{r.coef_bps.toFixed(1)}</td>
                <td>{r.se_bps.toFixed(1)}</td>
                <td>{r.t_stat.toFixed(2)}</td>
                <td>{r.p_value.toFixed(3)}</td>
                <td>{r.n.toLocaleString()}</td>
                <td>{r.r2.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
