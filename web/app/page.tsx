import Link from "next/link";
import CompanySearch from "@/components/CompanySearch";
import { companies, study } from "@/lib/data";
import { bps } from "@/lib/format";

export default function Home() {
  const s = study();
  const sum = s.summary[0];
  const reg = (id: string) => s.regressions.find((r) => r.id === id);
  const hedge = reg("H1:z_qa_hedging");
  const tone = s.robustness.find((r) => r.check.startsWith("Q&A net tone"));
  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">An earnings call study</p>
          <h1>Does hedging on an earnings call move the stock?</h1>
          <p className="lead">
            Pick a company to see every earnings call since 2017: how much management hedged in the Q&amp;A, whether
            earnings beat expectations, and how the stock moved compared with the S&amp;P 500.
          </p>
          <div className="actions">
            <a className="btn primary" href="#explore">Explore a company</a>
            <Link className="btn" href="/results/">See the results</Link>
          </div>
        </div>
        <aside className="answer" aria-label="The short answer">
          <div className="label">The short answer</div>
          <div className="row">
            <span>Calls studied</span>
            <span className="v">{sum.calls.toLocaleString()}</span>
            <span className="s">{sum.firms} firms, {sum.first_call.slice(0, 4)} to {sum.last_call.slice(0, 4)}</span>
          </div>
          <div className="row">
            <span>Earnings surprise effect</span>
            <span className="v up">{bps(sum.sue_coef_bps)}</span>
            <span className="s">2-day return per 1 SD, t = {sum.sue_t.toFixed(1)}, a clear effect</span>
          </div>
          {hedge && (
            <div className="row">
              <span>Hedging effect</span>
              <span className="v">{bps(hedge.coef_bps)}</span>
              <span className="s">per 1 SD, t = {hedge.t_stat.toFixed(1)}, not significant</span>
            </div>
          )}
          {tone && (
            <div className="row">
              <span>Q&amp;A net tone effect</span>
              <span className="v up">{bps(tone.coef_bps)}</span>
              <span className="s">per 1 SD, t = {tone.t_stat.toFixed(2)}, the one lead</span>
            </div>
          )}
          <p className="sum">
            <b>Takeaway:</b> the earnings number drives the reaction; hedging language adds no reliable signal on top of it.
          </p>
        </aside>
      </section>

      <section id="explore" style={{ scrollMarginTop: 90 }}>
        <div className="explore-head">
          <div>
            <h2>Explore a company</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>Open a company to see its calls, its stock chart and the most hedged answers.</p>
          </div>
        </div>
        <CompanySearch companies={companies()} />
      </section>
    </>
  );
}
