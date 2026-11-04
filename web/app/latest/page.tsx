import type { Metadata } from "next";
import Link from "next/link";
import { InfoCallout, PageHead, Section, Stat } from "@/components/ui";
import { companies, feed, type FeedCall } from "@/lib/data";
import { longDate, pct, pctile, signClass } from "@/lib/format";

export const metadata: Metadata = { title: "Live feed" };

const num = (r: FeedCall, k: string) => (typeof r[k] === "number" ? (r[k] as number) : null);
const sigma = (z: number | null) =>
  z == null ? "–" : `${z > 0 ? "+" : z < 0 ? "−" : ""}${Math.abs(z).toFixed(1)}σ`;
const surprise = (x: number | null) => (x == null ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(1)}%`);

export default function Latest() {
  const f = feed();
  const studied = new Set(companies().map((c) => c.ticker));
  if (!f) {
    return (
      <>
        <PageHead eyebrow="Live feed" title="Latest earnings calls" />
        <InfoCallout>The live feed hasn’t run yet. Once it does, the newest calls from the 100 largest S&amp;P 500 companies appear here every day.</InfoCallout>
      </>
    );
  }
  const calls = f.calls;
  const latest = calls.slice(0, 60);
  const highlights = calls.filter((c) => c.excerpts && c.excerpts.negative.length).slice(0, 6);
  const withCar = calls.filter((c) => c.car_0_1 != null);
  const updated = new Date(f.updated);
  return (
    <>
      <PageHead
        eyebrow="Live feed"
        title="Latest earnings calls"
        lead={<>New calls from the 100 largest S&amp;P 500 companies, scored daily with FinBERT (a finance-tuned language
          model that reads each sentence) and the Loughran-McDonald word lists. Each call is compared with the company’s own
          past calls and with every other call that quarter.</>}
      />
      <div className="tiles">
        <Stat label="Companies tracked" value={f.universe.length} note="largest S&P 500 members by market cap" />
        <Stat label="Calls scored" value={calls.length} note={`${f.n_companies_with_calls} companies since Jan 2025`} />
        <Stat label="With a 2-day reaction" value={withCar.length} note="needs two trading days after the call" />
        <Stat label="Last updated" value={updated.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}
              note={`${updated.toISOString().slice(11, 16)} UTC, refreshed daily`} />
      </div>

      <InfoCallout>
        <b>How to read this.</b> “Answer tone” is FinBERT’s average of P(positive) minus P(negative) over every executive
        sentence in the Q&amp;A. The percentile ranks it against all calls that quarter; “vs own history” says how far it sits
        from the company’s earlier calls, in standard deviations. In the main study only Q&amp;A tone showed a (weak) link to
        the 2-day return, so treat these as a description of the call, not a trading signal.
      </InfoCallout>

      <div className="stack">
        <Section title="Newest calls" takeaway="Most recent first. Earnings surprise is reported EPS against the consensus estimate." flush>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="l">Call date</th><th className="l">Company</th><th>EPS surprise</th>
                  <th>Answer tone (FinBERT)</th><th>vs own history</th><th>Prepared vs answers gap</th>
                  <th>Hedging</th><th>2-day reaction</th>
                </tr>
              </thead>
              <tbody>
                {latest.map((c) => (
                  <tr key={`${c.ticker}-${c.call_date}`}>
                    <td className="l">{longDate(c.call_date)}</td>
                    <td className="l">
                      {studied.has(c.ticker) ? <Link href={`/company/${c.ticker}/`}><b>{c.ticker}</b></Link> : <b>{c.ticker}</b>}{" "}
                      <span className="muted">{c.name}</span>
                    </td>
                    <td className={signClass(c.surprise_pct)}>{surprise(c.surprise_pct)}</td>
                    <td>{pctile(num(c, "pct_fb_qa_net"))}</td>
                    <td className={signClass(num(c, "own_z_fb_qa_net"))}>{sigma(num(c, "own_z_fb_qa_net"))}</td>
                    <td>{pctile(num(c, "pct_fb_tone_gap"))}</td>
                    <td>{pctile(num(c, "pct_qa_hedging"))}</td>
                    <td className={signClass(c.car_0_1)}>{pct(c.car_0_1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {highlights.length > 0 && (
          <Section title="What FinBERT picked out" takeaway="The most negative and most positive executive sentences from each of the latest calls.">
            <div className="stack">
              {highlights.map((c) => (
                <div key={`${c.ticker}-${c.call_date}-x`}>
                  <p className="who note" style={{ margin: "0 0 6px" }}>
                    <b>{c.ticker}</b> · {longDate(c.call_date)} · answer tone {pctile(num(c, "pct_fb_qa_net"))} percentile
                  </p>
                  {c.excerpts!.negative.slice(0, 1).map((e) => (
                    <blockquote key={e.text} className="quote" style={{ borderLeftColor: "var(--down)", marginBottom: 10 }}>
                      <p className="a" style={{ fontSize: 15.5 }}>“{e.text}”</p>
                      <p className="note" style={{ margin: "4px 0 0" }}>Most negative · score {e.score.toFixed(2)}</p>
                    </blockquote>
                  ))}
                  {c.excerpts!.positive.slice(0, 1).map((e) => (
                    <blockquote key={e.text} className="quote" style={{ borderLeftColor: "var(--up)" }}>
                      <p className="a" style={{ fontSize: 15.5 }}>“{e.text}”</p>
                      <p className="note" style={{ margin: "4px 0 0" }}>Most positive · score {e.score.toFixed(2)}</p>
                    </blockquote>
                  ))}
                </div>
              ))}
            </div>
          </Section>
        )}

        {f.upcoming.length > 0 && (
          <Section title="Reporting soon" takeaway="Next report dates from Yahoo Finance; dates marked estimated are not yet confirmed.">
            <div className="chips">
              {f.upcoming.map((u) => (
                <span key={u.ticker} className="pill">
                  <b>{u.ticker}</b> {longDate(u.date)}{u.estimate ? " (est.)" : ""}
                </span>
              ))}
            </div>
          </Section>
        )}
      </div>
      <p className="note" style={{ marginTop: 20 }}>
        Transcripts: Alpha Vantage (free tier, about 25 requests a day, so a busy earnings week can take a few days to catch
        up). Company baselines before 2025 use the Hugging Face S&amp;P 500 transcript set. Market caps and dates: Yahoo Finance.
        Only scores and short excerpts are stored.
      </p>
    </>
  );
}
