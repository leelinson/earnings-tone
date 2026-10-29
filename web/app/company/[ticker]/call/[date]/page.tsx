import type { Metadata } from "next";
import Link from "next/link";
import WindowChart from "@/components/WindowChart";
import { call, companies, company } from "@/lib/data";
import { longDate, pct, pctile, signClass } from "@/lib/format";

export const dynamicParams = false;
export const generateStaticParams = () =>
  companies().flatMap((c) => company(c.ticker).calls.map((x) => ({ ticker: c.ticker, date: x.call_date })));

type Props = { params: Promise<{ ticker: string; date: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ticker, date } = await params;
  return { title: `${ticker} call, ${longDate(date)}` };
}

function verdict(car: number | null, beat: string | null, hedgingPct: number | null) {
  if (car == null) return "There is no price reaction to measure for this call.";
  const move = `the stock ${car >= 0 ? "beat" : "lagged"} the market by ${Math.abs(100 * car).toFixed(1)}% over two days`;
  const eps = beat ? `Earnings ${beat === "Beat" ? "beat" : beat === "Miss" ? "missed" : "matched"} expectations and ${move}` : `${move[0].toUpperCase()}${move.slice(1)}`;
  const hedge = hedgingPct == null ? "" : hedgingPct >= 80 ? " Management hedged more than most companies that quarter."
    : hedgingPct <= 20 ? " Management hedged less than most companies that quarter." : "";
  return `${eps}.${hedge}`;
}

export default async function CallPage({ params }: Props) {
  const { ticker, date } = await params;
  const { call: c, window, qa } = call(`${ticker}_${date}`);
  const { company: co, calls } = company(ticker);
  const i = calls.findIndex((x) => x.call_id === c.call_id);
  const prev = calls[i - 1], next = calls[i + 1];
  const top = [...qa].filter((p) => p.answer_words >= 60).sort((a, b) => b.hedging_per1k - a.hedging_per1k)[0];
  const maxHedge = Math.max(1, ...qa.map((p) => p.hedging_per1k));
  return (
    <>
      <div className="crumbs">
        <Link href="/">All companies</Link> / <Link href={`/company/${ticker}/`}>{ticker}</Link> / {longDate(c.call_date)}
      </div>
      <h1>{co.name}: earnings call of {longDate(c.call_date)}</h1>
      <p className="lead">{verdict(c.car_0_1, c.beat, c.hedging_pct)}</p>

      <div className="tiles">
        <div className="tile"><div className="k">Earnings vs expectations</div><div className="v">{c.beat ?? "–"}</div>
          <div className="s">{c.sources_disagree ? "data sources disagree" : c.surprise_pct == null ? "" : `surprise ranked ${pctile(c.surprise_pct)} that quarter`}</div></div>
        <div className="tile"><div className="k">2-day reaction</div><div className={`v ${signClass(c.car_0_1)}`}>{pct(c.car_0_1)}</div>
          <div className="s">abnormal return, days 0 to +1</div></div>
        <div className="tile"><div className="k">Next month</div><div className={`v ${signClass(c.car_2_20)}`}>{pct(c.car_2_20)}</div>
          <div className="s">abnormal return, days +2 to +20</div></div>
        <div className="tile"><div className="k">Hedging</div><div className="v">{pctile(c.hedging_pct)}</div>
          <div className="s">{c.hedging_per1k == null ? "" : `${c.hedging_per1k.toFixed(1)} words per 1,000`}</div></div>
        <div className="tile"><div className="k">Net tone</div><div className="v">{pctile(c.net_tone_pct)}</div>
          <div className="s">positive minus negative words</div></div>
      </div>
      <p className="note">
        {c.after_close ? "Call held after the market close, so the reaction starts the next trading day" : "Call held during or before market hours"}
        {c.reaction_day ? ` (${longDate(c.reaction_day)}).` : "."}
        {c.date_fixed ? ` The transcript is dated ${longDate(c.transcript_date)}; the study uses the earnings release date instead.` : ""}
      </p>

      {window.length > 0 && (
        <>
          <h2>How the stock moved around the call</h2>
          <p className="takeaway"><b>How to read:</b> % change from the close before the reaction day, {ticker} against the S&amp;P 500.</p>
          <div className="panel"><WindowChart data={window} ticker={ticker} /></div>
        </>
      )}

      {top && (
        <>
          <h2>The most hedged answer</h2>
          <div className="panel highlight">
            <p className="muted" style={{ marginTop: 0 }}>Analyst: {top.question}</p>
            <p style={{ marginBottom: 0 }}>Management: {top.answer}</p>
            <p className="note" style={{ marginBottom: 0 }}>{top.hedging_per1k.toFixed(1)} hedging words per 1,000 (uncertain words, weak modals like “may” and “could”, and phrases like “too early to tell”). Excerpt.</p>
          </div>
        </>
      )}

      {qa.length > 0 && (
        <>
          <h2>All {qa.length} questions and answers</h2>
          <p className="takeaway">The orange bar shows how much each answer hedged. Text is shortened.</p>
          <div className="panel" style={{ paddingTop: 0, paddingBottom: 0 }}>
            {qa.map((p) => (
              <div className="qa" key={p.pair_no}>
                <p className="q">Q{p.pair_no}. {p.question}</p>
                <p className="a">{p.answer}</p>
                <div className="meta">
                  <span><span className="bar" style={{ width: `${Math.max(2, (60 * p.hedging_per1k) / maxHedge)}px` }} /> hedging {p.hedging_per1k.toFixed(1)}</span>
                  <span>on-topic {p.relevance == null ? "–" : p.relevance.toFixed(2)}</span>
                  {p.non_answer ? <span className="badge">non-answer phrase</span> : null}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="pager">
        <span>{prev && <Link href={`/company/${ticker}/call/${prev.call_date}/`}>← {longDate(prev.call_date)}</Link>}</span>
        <span>{next && <Link href={`/company/${ticker}/call/${next.call_date}/`}>{longDate(next.call_date)} →</Link>}</span>
      </div>
    </>
  );
}
