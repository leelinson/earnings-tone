import type { Metadata } from "next";
import ForestPlot from "@/components/ForestPlot";
import { PlaceboHistogram } from "@/components/StudyCharts";
import { PageHead, Section, Takeaway } from "@/components/ui";
import { study } from "@/lib/data";
// Small summary from pipeline/scripts/finbert_robustness.py (regression coefficients only).
import finbert from "@/lib/finbert_check.json";

export const metadata: Metadata = { title: "Does it hold up?" };

const VERDICTS: Record<string, string> = {
  H1: "Not supported. Hedging points the expected way but is within the range of luck.",
  H2: "Not supported. Evasive answers show no link to the reaction.",
  H3: "Not supported. The gap between scripted and Q&A tone does not predict the next month.",
  H4: "Not supported. Tone does not matter more when the surprise is small.",
};

const fb = (check: string) => {
  const r = finbert.rows.find((x) => x.check === check);
  return r ? `${r.coef_bps > 0 ? "+" : "\u2212"}${Math.abs(Math.round(r.coef_bps))} bps, t = ${r.t_stat.toFixed(1).replace("-", "\u2212")}` : "";
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
      <PageHead
        eyebrow="Does it hold up?"
        title="Checking the result every way we could"
        lead={<>The combined hedging-plus-evasiveness score stays small and insignificant however the sample is cut, and
          shuffled fake scores look just like it. The one exception, Q&amp;A net tone, is a lead to test on new data, not
          a finding.</>}
      />

      <div className="stack">
        <Section title="The main result under different choices"
          takeaway={<Takeaway>every version of the combined score lands between about −55 and +28 bps with a t-stat under 1.6 in size; only net tone, a different measure, clears 2.</Takeaway>}>
          <ForestPlot rows={main} />
        </Section>

        <Section title="Placebo: shuffled tone scores"
          takeaway={<Takeaway>tone scores were shuffled among calls in the same quarter 100 times. The real result
            (t = {sum.real_composite_t.toFixed(2)}) sits inside the pile of fake ones; {Math.round(100 * sum.placebo_share_sig)}% of fakes passed ±1.96, about the 5% luck alone gives.</Takeaway>}>
          <PlaceboHistogram tStats={s.placebo.map((p) => p.t_stat)} realT={sum.real_composite_t} />
        </Section>

        <Section title="Second opinion: FinBERT reads the same calls"
          takeaway={<Takeaway>a sentence-reading model confirms the dictionary only weakly: its answer tone is
            {" "}{fb("FinBERT tone in answers")}, and gone after 2023. Analyst question tone and negative answer
            sentences clear the bar, but they move on day 0 with the news, so they likely restate the quarter rather
            than predict anything. The one forward-looking signal is the FinBERT tone gap: scripted remarks rosier than
            the answers go with weaker drift over days +2 to +20 ({fb("FinBERT tone gap, drift days +2 to +20")}), and
            it holds after 2023, unlike the dictionary version (H3).</Takeaway>}
          foot={<>FinBERT (ProsusAI/finbert) labels each executive and analyst sentence; a call’s score is the mean of
            P(positive) minus P(negative). Same controls as above, standardized within quarter, {finbert.n_matched.toLocaleString()} calls.
            Rank correlation with the dictionary measure: {finbert.spearman.answers.toFixed(2)} for answers,
            {" "}{finbert.spearman.tone_gap.toFixed(2)} for the tone gap.</>}>
          <ForestPlot rows={finbert.rows.filter((r) => !r.check.startsWith("Horse race")).map((r) => ({
            label: r.check, coef: r.coef_bps, se: r.se_bps, t: r.t_stat, highlight: r.check.startsWith("Dictionary"),
          }))} />
        </Section>

        <Section title="Verdict on each hypothesis" flush>
          <div className="table-scroll">
            <table>
              <thead><tr><th className="l">Hypothesis</th><th className="l">Measure</th><th>Effect</th><th>t-stat</th><th className="l">Verdict</th></tr></thead>
              <tbody>
                {tests.map((r) => (
                  <tr key={r.id}>
                    <td className="l"><b>{r.hypothesis}</b> {r.question}</td>
                    <td className="l">{r.label}</td>
                    <td>{r.coef_bps > 0 ? "+" : ""}{Math.round(r.coef_bps)} bps</td>
                    <td>{r.t_stat.toFixed(2)}</td>
                    <td className="l wrap-cell"><span className="pill" style={{ marginRight: 8 }}>Not supported</span>{VERDICTS[r.hypothesis].replace(/^Not supported\. /, "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="Full regression table" takeaway="Each model controls for sector × quarter and clusters errors by firm. Coefficients in bps per 1 SD." flush>
          <div className="table-scroll">
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
                    <td style={{ fontWeight: Math.abs(r.t_stat) >= 1.96 ? 650 : undefined }}>{r.t_stat.toFixed(2)}</td>
                    <td>{r.p_value.toFixed(3)}</td>
                    <td>{r.n.toLocaleString()}</td>
                    <td>{r.r2.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </>
  );
}
