import type { Metadata } from "next";
import Link from "next/link";
import PriceChart from "@/components/PriceChart";
import { BeatPill, InfoCallout, PageHead, Section, Stat } from "@/components/ui";
import { companies, company } from "@/lib/data";
import { longDate, pct, pctile, signClass } from "@/lib/format";

export const dynamicParams = false;
export const generateStaticParams = () => companies().map((c) => ({ ticker: c.ticker }));

type Props = { params: Promise<{ ticker: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ticker } = await params;
  return { title: `${company(ticker).company.name} (${ticker})` };
}

export default async function CompanyPage({ params }: Props) {
  const { ticker } = await params;
  const { company: c, calls, prices } = company(ticker);
  const s = c.summary;
  const callHref = (d: string) => `/company/${ticker}/call/${d}/`;
  const studied = calls.filter((x) => x.car_0_1 != null);
  const big = studied.reduce<typeof studied[number] | null>(
    (m, x) => (m == null || Math.abs(x.car_0_1!) > Math.abs(m.car_0_1!) ? x : m), null);
  return (
    <>
      <PageHead
        crumbs={[{ href: "/", label: "All companies" }, { label: ticker }]}
        title={<div className="title-row"><h1>{c.name}</h1><span className="ticker-badge">{ticker}</span></div>}
      >
        <div className="meta-row">
          {c.sector && <span className="pill">{c.sector}</span>}
          <span>{c.n_calls} earnings calls, {c.first_call && longDate(c.first_call)} to {c.last_call && longDate(c.last_call)}</span>
        </div>
      </PageHead>

      <div className="tiles">
        <Stat label="Beat expectations" value={s.beat_rate == null ? "–" : `${Math.round(100 * s.beat_rate)}%`} note="of calls with EPS data" />
        <Stat label="Typical 2-day move" value={s.avg_abs_car_0_1 == null ? "–" : `±${(100 * s.avg_abs_car_0_1).toFixed(1)}%`} note="vs the S&P 500, average size" />
        <Stat label="Hedging, average rank" value={pctile(s.avg_hedging_pct)} note="percentile among calls that quarter" />
        <Stat label="Biggest reaction" tone={signClass(big?.car_0_1)} value={pct(big?.car_0_1)}
              note={big ? <Link href={callHref(big.call_date)}>{longDate(big.call_date)}</Link> : "no price data"} />
      </div>

      <div className="stack">
        {prices.length > 0 ? (
          <Section
            title="Stock price and its earnings calls"
            takeaway={<><b>How to read:</b> each dot is a call, green if the stock beat the market over the next two days and red if it lagged. Click a dot to open that call.</>}
          >
            <PriceChart prices={prices} calls={calls.map((x) => ({ ...x, href: callHref(x.call_date) }))} />
          </Section>
        ) : (
          <InfoCallout>No price history is available for {ticker} (the stock is delisted), so reactions can’t be measured.</InfoCallout>
        )}

        <Section
          title="Every call"
          takeaway="Hedging and net tone are percentiles among all calls in the same quarter: 90th means more than 90% of calls that quarter."
          flush
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="l">Call date</th><th className="l">Earnings</th><th>2-day reaction</th><th>Next month</th>
                  <th>Hedging</th><th>Net tone</th><th>Questions</th>
                </tr>
              </thead>
              <tbody>
                {[...calls].reverse().map((x) => (
                  <tr key={x.call_id}>
                    <td className="l"><Link href={callHref(x.call_date)}>{longDate(x.call_date)}</Link></td>
                    <td className="l"><BeatPill beat={x.beat} /></td>
                    <td className={signClass(x.car_0_1)}>{pct(x.car_0_1)}</td>
                    <td className={signClass(x.car_2_20)}>{pct(x.car_2_20)}</td>
                    <td>{pctile(x.hedging_pct)}</td>
                    <td>{pctile(x.net_tone_pct)}</td>
                    <td>{x.n_questions ?? "–"}</td>
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
