import type { Metadata } from "next";
import ForestPlot from "@/components/ForestPlot";
import { CarPath, DecileBars, QuintileBars, SpreadByQuarter, ToneOverTime } from "@/components/StudyCharts";
import { InfoCallout, PageHead, Section, Stat, Takeaway, Toc } from "@/components/ui";
import { study } from "@/lib/data";
import { bps } from "@/lib/format";

export const metadata: Metadata = { title: "Main results" };

export default function Results() {
  const s = study();
  const sum = s.summary[0];
  const reg = (id: string) => s.regressions.find((r) => r.id === id)!;
  const rob = (check: string) => s.robustness.find((r) => r.check.startsWith(check))!;
  const tone = rob("Q&A net tone");
  const ls = (p: string) => s.long_short.find((r) => r.period === p)!;
  const rows = [
    { r: reg("H1:z_sue"), label: "EPS surprise (control)" },
    { r: reg("H1:z_qa_hedging"), label: "H1 Hedging in answers" },
    { r: reg("H2:z_evasion"), label: "H2 Evasiveness" },
    { r: reg("H3:z_tone_gap"), label: "H3 Tone gap, next month" },
    { r: reg("H4:z_composite:low_sue"), label: "H4 Extra effect, small surprise" },
  ].map(({ r, label }) => ({ label, coef: r.coef_bps, se: r.se_bps, t: r.t_stat }));
  rows.push({ label: "Q&A net tone (extra test)", coef: tone.coef_bps, se: tone.se_bps, t: tone.t_stat, highlight: true } as typeof rows[number]);

  return (
    <>
      <PageHead
        eyebrow="Main results"
        title="The earnings number moves the stock. Hedging does not."
        lead={<>Across {sum.calls.toLocaleString()} calls, the earnings surprise explains the stock’s reaction and hedging does
          not add a reliable signal. The one lead is net tone: more positive Q&amp;A language goes with a better 2-day return.</>}
      />

      <InfoCallout>
        <b>How to read these numbers</b>
        <ul>
          <li>Returns are <b>abnormal</b>: the stock’s move minus what the market predicted, over days 0 to +1 after the call.</li>
          <li>Effects are in basis points (bps; 100 bps = 1%) for a one-standard-deviation change in the measure.</li>
          <li>A <b>t-stat</b> beyond ±2 is the usual bar for “probably not luck”.</li>
        </ul>
      </InfoCallout>

      <div className="tiles">
        <Stat label="Earnings surprise" tone="up" value={bps(sum.sue_coef_bps)} note={`t = ${sum.sue_t.toFixed(1)}, clear effect`} />
        <Stat label="Hedging" value={bps(reg("H1:z_qa_hedging").coef_bps)} note={`t = ${reg("H1:z_qa_hedging").t_stat.toFixed(2)}, not significant`} />
        <Stat label="Q&A net tone" tone="up" value={bps(tone.coef_bps)} note={`t = ${tone.t_stat.toFixed(2)}, the one lead`} accent />
        <Stat label="Least minus most hedging group" value={bps(ls("Full sample").mean_spread_bps)} note={`per quarter, t = ${ls("Full sample").t_stat.toFixed(2)}`} />
      </div>

      <Toc items={[["effects", "Effect sizes"], ["sanity", "Sanity check"], ["groups", "Tone groups"], ["quarters", "By quarter"], ["evasion", "Evasiveness"], ["time", "Tone over time"]]} />

      <div className="stack">
        <Section id="effects" title="Effect of each measure on the stock’s reaction"
          takeaway={<Takeaway>only the earnings surprise and net tone clear the bar; hedging, evasiveness and the tone gap could all be zero.</Takeaway>}>
          <ForestPlot rows={rows} />
        </Section>

        <Section id="sanity" title="Sanity check: bigger surprises, bigger reactions"
          takeaway={<Takeaway>returns rise from the worst misses (about −250 bps) to the biggest beats (about +270 bps), so the return measure works.</Takeaway>}>
          <DecileBars data={s.sue_bins} xLabel="Surprise decile (1 = worst miss)" />
        </Section>

        <Section id="groups" title="How each tone group’s stock moved"
          takeaway={<Takeaway>calls are sorted into five groups by hedging plus evasiveness each quarter; the most hedged group lags after the call, but the gap is small next to the noise.</Takeaway>}>
          <CarPath data={s.car_path} />
        </Section>

        <Section title="Average 2-day return by tone group"
          takeaway={<Takeaway>the gap between groups 1 and 5 was {Math.round(ls("In sample").mean_spread_bps)} bps in 2018 to 2022 and almost vanished from 2023 ({Math.round(ls("Out of sample").mean_spread_bps)} bps).</Takeaway>}>
          <QuintileBars data={s.quintiles} />
        </Section>

        <Section id="quarters" title="The gap quarter by quarter"
          takeaway={<Takeaway>the spread swings from strongly positive to negative between quarters, which is why it is not significant.</Takeaway>}>
          <SpreadByQuarter data={s.spread_by_quarter} split={sum.oos_split} />
        </Section>

        <Section id="evasion" title="Evasiveness and the reaction"
          takeaway={<Takeaway>no pattern: the most evasive calls do no worse than the most direct ones.</Takeaway>}>
          <DecileBars data={s.evasion_bins} xLabel="Evasiveness decile (1 = most direct)" />
        </Section>

        <Section id="time" title="Tone over time"
          takeaway={<Takeaway>hedging crept up from about 10 to 12 words per 1,000 since 2018, which is why each call is compared only with calls from the same quarter.</Takeaway>}>
          <ToneOverTime data={s.tone_by_quarter} />
        </Section>
      </div>
    </>
  );
}
