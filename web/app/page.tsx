import CompanySearch from "@/components/CompanySearch";
import { companies, study } from "@/lib/data";
import { bps } from "@/lib/format";

export default function Home() {
  const s = study();
  const sum = s.summary[0];
  const reg = (id: string) => s.regressions.find((r) => r.id === id);
  const hedge = reg("H1:z_qa_hedging");
  return (
    <>
      <h1>Does hedging on an earnings call move the stock?</h1>
      <p className="lead">
        Pick a company to see every earnings call since 2017: how much management hedged in the Q&amp;A, whether
        earnings beat expectations, and how the stock moved compared with the S&amp;P 500.
      </p>
      <div className="tiles">
        <div className="tile">
          <div className="k">Calls studied</div>
          <div className="v">{sum.calls.toLocaleString()}</div>
          <div className="s">{sum.firms} firms, {sum.first_call.slice(0, 4)} to {sum.last_call.slice(0, 4)}</div>
        </div>
        <div className="tile">
          <div className="k">Earnings surprise effect</div>
          <div className="v">{bps(sum.sue_coef_bps)}</div>
          <div className="s">2-day return per 1 SD, t = {sum.sue_t.toFixed(1)}</div>
        </div>
        {hedge && (
          <div className="tile">
            <div className="k">Hedging effect</div>
            <div className="v">{bps(hedge.coef_bps)}</div>
            <div className="s">per 1 SD, t = {hedge.t_stat.toFixed(1)}, not significant</div>
          </div>
        )}
      </div>
      <p className="takeaway">
        <b>Takeaway:</b> the earnings number drives the reaction; hedging language adds no reliable signal on top of it.
      </p>
      <h2>Explore a company</h2>
      <CompanySearch companies={companies()} />
    </>
  );
}
