import type { Metadata } from "next";
import { Fragment } from "react";
import { study } from "@/lib/data";

export const metadata: Metadata = { title: "Data and glossary" };

const GLOSSARY: [string, string][] = [
  ["Earnings call", "A quarterly conference call where management presents results (prepared remarks) and then takes analysts' questions (Q&A)."],
  ["Q&A", "The unscripted part of the call. This study scores only executives' answers here, because prepared remarks are written and vetted in advance."],
  ["Hedging", "Words per 1,000 that signal uncertainty: Loughran-McDonald uncertainty words, weak modals such as “may”, “could” and “might”, and phrases like “too early to tell”."],
  ["Evasiveness", "How far answers drift from the question (low word overlap between question and answer) plus non-answer phrases such as “we don't break that out”."],
  ["Net tone", "Positive minus negative finance words per 1,000 words of executive answers."],
  ["Tone gap", "Net tone of the prepared remarks minus net tone of the Q&A. A big gap means the script sounded better than the answers."],
  ["Abnormal return (CAR)", "The stock's return minus what its usual relationship with the S&P 500 predicts, summed over a window. CAR[0,+1] covers the reaction day and the day after."],
  ["Day 0", "The first trading day the market could react: the call date if the call was before the close, otherwise the next trading day."],
  ["EPS surprise (SUE)", "Reported earnings per share minus the analyst consensus, divided by the share price. The site shows only beat, miss or in line, plus a percentile."],
  ["bps", "Basis points. 100 bps = 1 percentage point."],
  ["Standard deviation (SD)", "Effects are per 1 SD of a measure, so a hedging effect of −26 bps means a call one SD more hedged than average had a 0.26% lower return."],
  ["t-stat", "The effect divided by its uncertainty. Beyond about ±2 means an effect that size would rarely appear by luck alone."],
  ["Tone group", "Each quarter, calls are split into five equal groups by hedging plus evasiveness. Group 1 hedged least, group 5 most."],
  ["In sample / out of sample", "2018 to 2022 was used to build the study; 2023 onward is a later check the design never looked at."],
  ["Placebo", "Rerunning the test with tone scores shuffled among calls of the same quarter. Real effects should beat the shuffled ones."],
];

export default function DataPage() {
  const s = study();
  const flow = s.sample_flow;
  const max = flow[0].calls;
  const sum = s.summary[0];
  return (
    <>
      <h1>Data and glossary</h1>
      <p className="lead">
        Where the {sum.calls.toLocaleString()} calls came from, how each number was built, and what the terms mean.
      </p>

      <h2>From transcripts to the final sample</h2>
      <div className="panel flow">
        {flow.map((f) => (
          <div className="row" key={f.step}>
            <div className="fbar" style={{ width: `${(100 * f.calls) / max}%` }}>{f.stage}</div>
            <b style={{ textAlign: "right" }}>{f.calls.toLocaleString()}</b>
          </div>
        ))}
      </div>

      <h2>Method</h2>
      <ol>
        <li>Split each transcript into prepared remarks and Q&amp;A, label speakers as operator, executive or analyst, and pair each question with its answer.</li>
        <li>Score executives’ Q&amp;A answers with the Loughran-McDonald finance dictionary: hedging, net tone, and evasiveness from question-answer similarity.</li>
        <li>Standardize each score within its calendar quarter, so a market-wide change in tone does not leak into the results.</li>
        <li>Estimate each stock’s normal relationship with SPY over trading days −250 to −30, then measure abnormal returns for days 0 to +1 and +2 to +20.</li>
        <li>Move the event date to the earnings release date for 180 transcripts dated one to three days late.</li>
        <li>Regress abnormal returns on each tone measure, controlling for the EPS surprise and the prior month’s return, with sector × quarter effects and firm-clustered errors.</li>
        <li>Check it: quintile portfolios, a 2023-onward holdout, 100 placebo shuffles and alternative samples.</li>
      </ol>

      <h2>Glossary</h2>
      <div className="panel">
        <dl className="glossary">
          {GLOSSARY.map(([t, d]) => (<Fragment key={t}><dt>{t}</dt><dd>{d}</dd></Fragment>))}
        </dl>
      </div>

      <h2>Caveats</h2>
      <ul>
        <li>64 tech and communication services firms only; results may not carry over to other sectors.</li>
        <li>The dictionary counts words without context, so “we are not uncertain” still counts as uncertain.</li>
        <li>EPS consensus comes from public datasets, not I/B/E/S; 70 calls where sources disagree are flagged and tested separately.</li>
        <li>No control yet for company size or a sector benchmark instead of SPY.</li>
        <li>Netflix’s interview-format calls have no Q&amp;A section and are excluded; EA and Juniper have no price history.</li>
      </ul>

      <h2>Sources and licenses</h2>
      <div className="panel table-scroll">
        <table>
          <thead><tr><th className="l">Data</th><th className="l">Source</th><th className="l">How it appears here</th></tr></thead>
          <tbody>
            <tr><td className="l">Transcripts</td><td className="l">Hugging Face dataset kurry/sp500_earnings_transcripts</td><td className="l">Scores and short excerpts only</td></tr>
            <tr><td className="l">Prices</td><td className="l">Yahoo Finance chart data</td><td className="l">Adjusted closes, abnormal returns</td></tr>
            <tr><td className="l">EPS surprise</td><td className="l">sovai/earnings_surprise (academic use) and a Zacks-based Hugging Face mirror</td><td className="l">Beat, miss or in line and a percentile; no raw estimates</td></tr>
            <tr><td className="l">Word lists</td><td className="l">Loughran-McDonald master dictionary</td><td className="l">Used to score tone</td></tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
