import type { Metadata } from "next";
import ForestPlot from "@/components/ForestPlot";
import { CarPath, DecileBars, QuintileBars, SpreadByQuarter, ToneOverTime } from "@/components/StudyCharts";
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
      <h1>Main results</h1>
      <p className="lead">
        Across {sum.calls.toLocaleString()} calls, the earnings surprise explains the stock’s reaction and hedging does
        not add a reliable signal. The one lead is net tone: more positive Q&amp;A language goes with a better 2-day return.
      </p>
      <div className="howto">
        <b>How to read these numbers</b>
        <ul>
          <li>Returns are <b>abnormal</b>: the stock’s move minus what the market predicted, over days 0 to +1 after the call.</li>
          <li>Effects are in basis points (bps; 100 bps = 1%) for a one-standard-deviation change in the measure.</li>
          <li>A <b>t-stat</b> beyond ±2 is the usual bar for “probably not luck”.</li>
        </ul>
      </div>

      <div className="tiles">
        <div className="tile"><div className="k">Earnings surprise</div><div className="v up">{bps(sum.sue_coef_bps)}</div><div className="s">t = {sum.sue_t.toFixed(1)}, clear effect</div></div>
        <div className="tile"><div className="k">Hedging</div><div className="v">{bps(reg("H1:z_qa_hedging").coef_bps)}</div><div className="s">t = {reg("H1:z_qa_hedging").t_stat.toFixed(2)}, not significant</div></div>
        <div className="tile"><div className="k">Q&amp;A net tone</div><div className="v up">{bps(tone.coef_bps)}</div><div className="s">t = {tone.t_stat.toFixed(2)}, the one lead</div></div>
        <div className="tile"><div className="k">Least minus most hedging group</div><div className="v">{bps(ls("Full sample").mean_spread_bps)}</div><div className="s">per quarter, t = {ls("Full sample").t_stat.toFixed(2)}</div></div>
      </div>

      <h2>Effect of each measure on the stock’s reaction</h2>
      <p className="takeaway"><b>Takeaway:</b> only the earnings surprise and net tone clear the bar; hedging, evasiveness and the tone gap could all be zero.</p>
      <div className="panel"><ForestPlot rows={rows} /></div>

      <h2>Sanity check: bigger surprises, bigger reactions</h2>
      <p className="takeaway"><b>Takeaway:</b> returns rise from the worst misses (about −250 bps) to the biggest beats (about +270 bps), so the return measure works.</p>
      <div className="panel"><DecileBars data={s.sue_bins} xLabel="Surprise decile (1 = worst miss)" /></div>

      <h2>How each tone group’s stock moved</h2>
      <p className="takeaway"><b>Takeaway:</b> calls are sorted into five groups by hedging plus evasiveness each quarter; the most hedged group lags after the call, but the gap is small next to the noise.</p>
      <div className="panel"><CarPath data={s.car_path} /></div>

      <h2>Average 2-day return by tone group</h2>
      <p className="takeaway"><b>Takeaway:</b> the gap between groups 1 and 5 was {Math.round(ls("In sample").mean_spread_bps)} bps in 2018 to 2022 and almost vanished from 2023 ({Math.round(ls("Out of sample").mean_spread_bps)} bps).</p>
      <div className="panel"><QuintileBars data={s.quintiles} /></div>

      <h2>The gap quarter by quarter</h2>
      <p className="takeaway"><b>Takeaway:</b> the spread swings from strongly positive to negative between quarters, which is why it is not significant.</p>
      <div className="panel"><SpreadByQuarter data={s.spread_by_quarter} split={sum.oos_split} /></div>

      <h2>Evasiveness and the reaction</h2>
      <p className="takeaway"><b>Takeaway:</b> no pattern: the most evasive calls do no worse than the most direct ones.</p>
      <div className="panel"><DecileBars data={s.evasion_bins} xLabel="Evasiveness decile (1 = most direct)" /></div>

      <h2>Tone over time</h2>
      <p className="takeaway"><b>Takeaway:</b> hedging crept up from about 10 to 12 words per 1,000 since 2018, which is why each call is compared only with calls from the same quarter.</p>
      <div className="panel"><ToneOverTime data={s.tone_by_quarter} /></div>
    </>
  );
}
