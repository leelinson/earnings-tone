import type { Metadata } from "next";
import Link from "next/link";
import WindowChart from "@/components/WindowChart";
import { BeatPill, PageHead, Section, Stat } from "@/components/ui";
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
      <PageHead
        crumbs={[{ href: "/", label: "All companies" }, { href: `/company/${ticker}/`, label: ticker }, { label: longDate(c.call_date) }]}
        eyebrow={`${co.name} · earnings call`}
        title={longDate(c.call_date)}
      >
        <p className="verdict">{verdict(c.car_0_1, c.beat, c.hedging_pct)}</p>
      </PageHead>

      <div className="tiles">
        <Stat label="Earnings vs expectations" value={<BeatPill beat={c.beat} />}
              note={c.sources_disagree ? "data sources disagree" : c.surprise_pct == null ? "" : `surprise ranked ${pctile(c.surprise_pct)} that quarter`} />
        <Stat label="2-day reaction" tone={signClass(c.car_0_1)} value={pct(c.car_0_1)} note="abnormal return, days 0 to +1" accent />
        <Stat label="Next month" tone={signClass(c.car_2_20)} value={pct(c.car_2_20)} note="abnormal return, days +2 to +20" />
        <Stat label="Hedging" value={pctile(c.hedging_pct)} note={c.hedging_per1k == null ? "" : `${c.hedging_per1k.toFixed(1)} words per 1,000`} />
        <Stat label="Net tone" value={pctile(c.net_tone_pct)} note="positive minus negative words" />
      </div>
      <p className="note" style={{ margin: "-6px 0 20px" }}>
        {c.after_close ? "Call held after the market close, so the reaction starts the next trading day" : "Call held during or before market hours"}
        {c.reaction_day ? ` (${longDate(c.reaction_day)}).` : "."}
        {c.date_fixed ? ` The transcript is dated ${longDate(c.transcript_date)}; the study uses the earnings release date instead.` : ""}
      </p>

      <div className="stack">
        {window.length > 0 && (
          <Section
            title="How the stock moved around the call"
            takeaway={<><b>How to read:</b> % change from the close before the reaction day, {ticker} against the S&amp;P 500.</>}
          >
            <WindowChart data={window} ticker={ticker} />
          </Section>
        )}

        {top && (
          <Section
            title="The most hedged answer"
            foot={<>{top.hedging_per1k.toFixed(1)} hedging words per 1,000 (uncertain words, weak modals like “may” and “could”, and phrases like “too early to tell”). Excerpt.</>}
          >
            <figure className="quote">
              <p className="who">Analyst</p>
              <p className="q">{top.question}</p>
              <p className="who">Management</p>
              <blockquote className="a" style={{ margin: 0 }}>{top.answer}</blockquote>
            </figure>
          </Section>
        )}

        {qa.length > 0 && (
          <Section title={`All ${qa.length} questions and answers`} takeaway="The orange bar shows how much each answer hedged, relative to the most hedged answer on this call. Text is shortened." flush>
            <div style={{ borderTop: "1px solid var(--line)" }}>
              {qa.map((p) => (
                <div className="qa" key={p.pair_no}>
                  <span className="no">Q{p.pair_no}</span>
                  <div>
                    <p className="q">{p.question}</p>
                    <p className="a">{p.answer}</p>
                    <div className="meta">
                      <span>
                        <span className="meter"><span style={{ width: `${Math.max(4, (100 * p.hedging_per1k) / maxHedge)}%` }} /></span>
                        hedging {p.hedging_per1k.toFixed(1)}
                      </span>
                      <span>on-topic {p.relevance == null ? "–" : p.relevance.toFixed(2)}</span>
                      {p.non_answer ? <span className="pill hedge">non-answer phrase</span> : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>

      <nav className="pager" aria-label="Other calls">
        {prev && <Link href={`/company/${ticker}/call/${prev.call_date}/`}><span className="k">← Previous call</span>{longDate(prev.call_date)}</Link>}
        {next && <Link className="next" href={`/company/${ticker}/call/${next.call_date}/`}><span className="k">Next call →</span>{longDate(next.call_date)}</Link>}
      </nav>
    </>
  );
}
