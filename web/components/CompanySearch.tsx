"use client";
import Link from "next/link";
import { useState } from "react";
import type { Company } from "@/lib/data";

export default function CompanySearch({ companies }: { companies: Company[] }) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const shown = companies.filter(
    (c) => !needle || c.ticker.toLowerCase().includes(needle) || c.name.toLowerCase().includes(needle),
  );
  return (
    <>
      <input
        className="search"
        placeholder="Search by ticker or name, e.g. NVDA or Netflix"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Search companies"
      />
      <div className="grid">
        {shown.map((c) => (
          <Link key={c.ticker} href={`/company/${c.ticker}/`} className="card">
            <div className="t">{c.ticker}</div>
            <div>{c.name}</div>
            <div className="n">
              {c.n_calls} calls · {c.first_call?.slice(0, 4)} to {c.last_call?.slice(0, 4)}
            </div>
          </Link>
        ))}
        {shown.length === 0 && <p className="muted">No company matches “{q}”.</p>}
      </div>
    </>
  );
}
