import type { Metadata } from "next";
import Link from "next/link";
import PriceChart from "@/components/PriceChart";
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
      <div className="crumbs"><Link href="/">All companies</Link> / {ticker}</div>
      <h1>{c.name} <span className="muted">({ticker})</span></h1>
      <p className="lead">
        {c.n_calls} earnings calls from {c.first_call && longDate(c.first_call)} to {c.last_call && longDate(c.last_call)}
        {c.sector ? `, ${c.sector}` : ""}.
      </p>

      <div className="tiles">
        <div className="tile">
          <div className="k">Beat expectations</div>
          <div className="v">{s.beat_rate == null ? "–" : `${Math.round(100 * s.beat_rate)}%`}</div>
          <div className="s">of calls with EPS data</div>
        </div>
        <div className="tile">
          <div className="k">Typical 2-day move</div>
          <div className="v">{s.avg_abs_car_0_1 == null ? "–" : `±${(100 * s.avg_abs_car_0_1).toFixed(1)}%`}</div>
          <div className="s">vs the S&amp;P 500, average size</div>
        </div>
        <div className="tile">
          <div className="k">Hedging, average rank</div>
          <div className="v">{pctile(s.avg_hedging_pct)}</div>
          <div className="s">percentile among calls that quarter</div>
        </div>
        <div className="tile">
          <div className="k">Biggest reaction</div>
          <div className={`v ${signClass(big?.car_0_1)}`}>{pct(big?.car_0_1)}</div>
          <div className="s">{big ? <Link href={callHref(big.call_date)}>{longDate(big.call_date)}</Link> : "no price data"}</div>
        </div>
      </div>

      {prices.length > 0 ? (
        <>
          <h2>Stock price and its earnings calls</h2>
          <p className="takeaway">
            <b>How to read:</b> each dot is a call, green if the stock beat the market over the next two days and red if
            it lagged. Click a dot to open that call.
          </p>
          <div className="panel">
            <PriceChart prices={prices} calls={calls.map((x) => ({ ...x, href: callHref(x.call_date) }))} />
          </div>
        </>
      ) : (
        <p className="note">No price history is available for {ticker} (the stock is delisted), so reactions can’t be measured.</p>
      )}

      <h2>Every call</h2>
      <p className="takeaway">
        Hedging and net tone are percentiles among all calls in the same quarter: 90th means more than 90% of calls that
        quarter.
      </p>
      <div className="panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>Call date</th><th className="l">Earnings</th><th>2-day reaction</th><th>Next month</th>
              <th>Hedging</th><th>Net tone</th><th>Questions</th>
            </tr>
          </thead>
          <tbody>
            {[...calls].reverse().map((x) => (
              <tr key={x.call_id}>
                <td><Link href={callHref(x.call_date)}>{longDate(x.call_date)}</Link></td>
                <td className="l">{x.beat ?? "–"}</td>
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
    </>
  );
}
