"use client";
import Link from "next/link";
import { useState } from "react";
import type { Company } from "@/lib/data";

const SHORT: Record<string, string> = { "Information Technology": "Tech", "Communication Services": "Communication" };

export default function CompanySearch({ companies }: { companies: Company[] }) {
  const [q, setQ] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const sectors = Array.from(new Set(companies.map((c) => c.sector).filter(Boolean))) as string[];
  const needle = q.trim().toLowerCase();
  const shown = companies.filter(
    (c) => (!sector || c.sector === sector)
      && (!needle || c.ticker.toLowerCase().includes(needle) || c.name.toLowerCase().includes(needle)),
  );
  return (
    <>
      <div className="searchbar">
        <label className="search">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            placeholder="Search by ticker or name, e.g. NVDA or Netflix"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search companies"
          />
        </label>
        <div className="chips" role="group" aria-label="Filter by sector">
          <button className={`chip${sector == null ? " on" : ""}`} aria-pressed={sector == null} onClick={() => setSector(null)}>
            All {companies.length}
          </button>
          {sectors.map((s) => (
            <button key={s} className={`chip${sector === s ? " on" : ""}`} aria-pressed={sector === s} onClick={() => setSector(s)}>
              {SHORT[s] ?? s} {companies.filter((c) => c.sector === s).length}
            </button>
          ))}
        </div>
      </div>
      <div className="grid">
        {shown.map((c) => (
          <Link key={c.ticker} href={`/company/${c.ticker}/`} className="card">
            <span className="tk">{c.ticker}</span>
            <span className="t" title={c.name}>{c.name}</span>
            <span className="n">{c.n_calls} calls · {c.first_call?.slice(0, 4)} to {c.last_call?.slice(0, 4)}</span>
          </Link>
        ))}
      </div>
      {shown.length === 0 && <p className="muted">No company matches “{q}”.</p>}
    </>
  );
}
