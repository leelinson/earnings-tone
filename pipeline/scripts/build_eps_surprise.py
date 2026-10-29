"""Build data/raw/eps_surprise.csv for the earnings tone study.

One row per earnings call in the transcript cache, with actual EPS, consensus estimate
and surprise, matched to the call date. Uses public datasets and APIs only (no HTML scraping):

  1. sovai/earnings_surprise (Hugging Face, "academic research access", 6-month lag).
     Announcement dates + actual/estimate through 2024-04-26, restated for splits up to a
     ticker-specific date (inferred against Zacks). Primary source, except where split
     restatement has cost it precision.
  2. siddharthmb/stocks-earnings-eps_history (Hugging Face mirror of the DoltHub
     post-no-preference/earnings database, Zacks-sourced). Fiscal period end + reported/estimate,
     as-reported (not split-adjusted). Fills calls after April 2024, gaps, and heavily split names.
  3. Yahoo chart API on query1.finance.yahoo.com: split events and split-adjusted closes.
     Fallback for delisted names (EA, JNPR): as-traded closes from the DoltHub stocks mirror
     on HF (siddharthmb/stocks-ohlcv).

All per-share numbers are on the as-reported basis of the call date: EPS as the company reported
it then, and `price` = as-traded close on the trading day before the call (used by
surprise.add_sue for a price-scaled SUE). surprise_pct is basis-free.

Usage:
  python build_eps_surprise.py [transcripts.jsonl] [out.csv]
Defaults are the project's data/raw paths. Downloads are cached in data/raw/eps_cache/.
"""
import json, os, sys, time, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

RAW = Path(os.environ.get("EARNINGS_TONE_RAW", "data/raw"))
CACHE = RAW / "eps_cache"
HF = "https://huggingface.co/datasets/{}/resolve/main/{}"
TOL_DAYS = 3          # sovai announcement date must be within this many days of the call
MAX_LAG_DAYS = 110    # Zacks fiscal period end must precede the call by at most this
DISAGREE_ABS = 0.02   # flag calls where the two sources differ by more than this ($/share)
DISAGREE_REL = 0.03   # ... and by more than this fraction


def fetch(url, dest):
    dest = Path(dest)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())
    return dest


def load_calls(path):
    rows = [{k: r[k] for k in ("symbol", "date")} for r in map(json.loads, open(path)) if r.get("date")]
    c = pd.DataFrame(rows).rename(columns={"symbol": "ticker"})
    c["ticker"] = c["ticker"].str.upper()
    c["date"] = pd.to_datetime(c["date"]).dt.normalize().astype("datetime64[ns]")
    return c.drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"]).reset_index(drop=True)


def yahoo_chart(t):
    """Split events (date -> ratio) and split-adjusted daily close, from the chart API."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=1483228800"
           f"&period2={int(time.time())}&interval=1d&events=split")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    tz = r["meta"]["exchangeTimezoneName"]
    idx = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
    close = pd.Series(r["indicators"]["quote"][0]["close"], index=idx, dtype=float).dropna()
    close = close[~close.index.duplicated(keep="last")]
    splits = [(pd.Timestamp(s["date"], unit="s").normalize(), s["numerator"] / s["denominator"])
              for s in r.get("events", {}).get("splits", {}).values()]
    return close, sorted(splits)


def yahoo_all(tickers):
    out, failed = {}, []
    for t in tickers:
        for k in range(3):
            try:
                out[t] = yahoo_chart(t); break
            except Exception as e:
                if k == 2: failed.append(t)
                time.sleep(2 ** k)
        time.sleep(0.3)
    return out, failed


def split_factor(splits, after):
    """Product of split ratios strictly after `after`: multiply today-basis per-share numbers by this."""
    return float(np.prod([r for d, r in splits if d > after])) if splits else 1.0


def match_sovai(calls, sov):
    s = (sov.sort_values("date").groupby(["ticker", "date_pub"]).last().reset_index()
         [["ticker", "date_pub", "actual_earning_result", "estimated_earning"]]
         .rename(columns={"actual_earning_result": "a", "estimated_earning": "e"}))
    s["date_pub"] = pd.to_datetime(s["date_pub"]).astype("datetime64[ns]")
    s = s.dropna(subset=["a", "e"]).sort_values("date_pub")
    m = pd.merge_asof(calls.sort_values("date"), s, left_on="date", right_on="date_pub", by="ticker",
                      direction="nearest", tolerance=pd.Timedelta(days=TOL_DAYS))
    # one announcement -> at most one call (closest)
    m["gap"] = (m["date"] - m["date_pub"]).abs()
    m = m.sort_values("gap")
    m.loc[m.duplicated(["ticker", "date_pub"]) & m["date_pub"].notna(), ["a", "e", "date_pub"]] = np.nan
    return m.drop(columns="gap").set_index(["ticker", "date"])


def match_zacks(calls, z):
    z = z.rename(columns={"act_symbol": "ticker", "reported": "a", "estimate": "e"})
    z["period_end"] = pd.to_datetime(z["period_end_date"]).astype("datetime64[ns]")
    z.loc[z.ticker == "FB", "ticker"] = "META"
    z = z.dropna(subset=["a", "e"]).drop_duplicates(["ticker", "period_end"]).sort_values("period_end")
    m = pd.merge_asof(calls.sort_values("date"), z[["ticker", "period_end", "a", "e"]],
                      left_on="date", right_on="period_end", by="ticker", direction="backward",
                      allow_exact_matches=False, tolerance=pd.Timedelta(days=MAX_LAG_DAYS))
    # one fiscal period -> at most one call (the earliest after period end)
    m = m.sort_values("date")
    m.loc[m.duplicated(["ticker", "period_end"]) & m["period_end"].notna(), ["a", "e", "period_end"]] = np.nan
    return m.set_index(["ticker", "date"])


def dolt_prices(tickers, dest):
    """As-traded daily closes from the DoltHub stocks mirror on HF (fallback for delisted names).
    The source is a 1.2 GB CSV, so it is streamed once and filtered to `tickers`."""
    dest = Path(dest)
    if not dest.exists():
        want = set(tickers)
        req = urllib.request.Request(HF.format("siddharthmb/stocks-ohlcv", "ohlcv.csv"),
                                     headers={"User-Agent": "Mozilla/5.0"})
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "w") as f:
            f.write(r.readline().decode())
            for line in r:
                line = line.decode()
                if line.split(",", 2)[1] in want:
                    f.write(line)
    d = pd.read_csv(dest, parse_dates=["date"])
    return {t: g.set_index("date")["close"].sort_index() for t, g in d.groupby("act_symbol")}


def prior_close(close, d):
    prior = close[close.index < d]
    if len(prior) and (d - prior.index[-1]).days <= 5:
        return prior.index[-1], prior.iloc[-1]
    return None, np.nan


def close_enough(x, y, slack=0.0):
    return abs(x - y) <= max(DISAGREE_ABS, DISAGREE_REL * max(abs(x), abs(y))) + slack


def sovai_basis(sm, zm, splits_by_ticker):
    """sovai restates history for splits, but only for splits up to some date that varies by
    ticker (and not for spin-off adjustments that Yahoo books as splits). For each ticker pick the
    cutoff whose restatement, undone, best matches Zacks' as-reported actuals.
    Returns ticker -> (label, f) with as_reported = sovai * f(call_date)."""
    j = sm[["a"]].join(zm[["a"]], rsuffix="_z").dropna()
    choice = {}
    for t in sm.index.get_level_values(0).unique():
        sp = splits_by_ticker.get(t, [])
        cands = {"none": lambda d: 1.0}
        for c, _ in sp:
            cands[f"thru {c.date()}"] = lambda d, c=c, sp=sp: float(np.prod([r for sd, r in sp if d < sd <= c]))
        default = list(cands)[-1]  # restated for every split so far
        if t not in j.index.get_level_values(0):
            choice[t] = (default, cands[default]); continue
        jt = j.loc[t]
        score = {k: sum(close_enough(r.a * f(d), r.a_z) for d, r in jt.iterrows()) for k, f in cands.items()}
        best = max(cands, key=lambda k: (score[k], k == default))
        choice[t] = (best, cands[best])
    return choice


def main(transcripts=RAW / "transcripts_tech.jsonl", out=RAW / "eps_surprise.csv"):
    calls = load_calls(transcripts)
    tickers = sorted(calls.ticker.unique())
    print(f"{len(calls)} calls, {len(tickers)} tickers, {calls.date.min().date()} to {calls.date.max().date()}")

    sov = pd.read_parquet(fetch(HF.format("sovai/earnings_surprise", "earnings_surprise.parquet"),
                                CACHE / "sovai_earnings_surprise.parquet"))
    sov = sov[sov.ticker.isin(tickers) & (sov.date_pub >= "2017-01-01")]
    zk = pd.read_csv(fetch(HF.format("siddharthmb/stocks-earnings-eps_history", "eps_history.csv"),
                           CACHE / "zacks_eps_history.csv"))
    zk = zk[zk.act_symbol.isin(tickers + ["FB"])]

    yq, yfail = yahoo_all(tickers)
    print("Yahoo chart failed for:", yfail)
    splits = {t: v[1] for t, v in yq.items()}
    dolt = dolt_prices(tickers, CACHE / "dolt_ohlcv_universe.csv")

    sm, zm = match_sovai(calls, sov), match_zacks(calls, zk)
    basis = sovai_basis(sm, zm, splits)
    print("sovai split basis by ticker:", {t: b for t, (b, _) in basis.items() if b != "none"})

    rows = []
    for (t, d) in calls.set_index(["ticker", "date"]).index:
        s, z = sm.loc[(t, d)], zm.loc[(t, d)]
        # everything on the as-reported (as-traded) per-share basis of the call date
        sa = se = np.nan
        f = basis[t][1](d) if t in basis else 1.0
        if pd.notna(s.a):
            sa, se = s.a * f, s.e * f
        za, ze = z.a, z.e
        # sovai stores 2 decimals on its restated basis, so after a 2:1 or larger split its old
        # values lose precision (NVDA 2018: 0.05 x 40); Zacks keeps as-reported cents
        if pd.notna(sa) and not (f >= 2 and pd.notna(za)):
            src, a, e = "sovai", sa, se
        elif pd.notna(za):
            src, a, e = "zacks", za, ze
        else:
            src, a, e = "", np.nan, np.nan
        price, psrc = np.nan, ""
        if t in yq:
            pd_, p = prior_close(yq[t][0], d)
            if pd_ is not None:
                price, psrc = p * split_factor(splits[t], pd_), "yahoo"
        if np.isnan(price) and t in dolt:
            pd_, p = prior_close(dolt[t], d)
            if pd_ is not None:
                price, psrc = p, "dolthub"
        both = pd.notna(sa) and pd.notna(za)
        rows.append(dict(ticker=t, date=d.date(), eps_actual=a, eps_estimate=e, surprise=a - e,
                         surprise_pct=(a - e) / abs(e) if pd.notna(e) and e != 0 else np.nan,
                         price=price, source=src, price_source=psrc,
                         announce_date=s.date_pub.date() if pd.notna(s.date_pub) else None,
                         fiscal_period_end=z.period_end.date() if pd.notna(z.period_end) else None,
                         alt_eps_actual=(za if src == "sovai" else sa) if both else np.nan,
                         alt_eps_estimate=(ze if src == "sovai" else se) if both else np.nan,
                         # allow for sovai's rounding on its restated basis
                         actual_disagree=int(both and not close_enough(sa, za, 0.005 * f)),
                         estimate_disagree=int(both and not close_enough(se, ze, 0.005 * f))))
    df = pd.DataFrame(rows)
    for c in ["eps_actual", "eps_estimate", "surprise", "surprise_pct", "price", "alt_eps_actual", "alt_eps_estimate"]:
        df[c] = df[c].round(4)
    have = df.dropna(subset=["eps_actual"])
    have.to_csv(out, index=False)

    # coverage report
    print(f"\nwrote {out}: {len(have)} of {len(df)} calls ({len(have)/len(df):.1%})")
    print("by source:", have.source.value_counts().to_dict(), "| price:", have.price_source.value_counts().to_dict())
    both = have.alt_eps_actual.notna()
    print(f"both sources: {int(both.sum())}, actual disagrees: {int(have.actual_disagree.sum())}, "
          f"estimate disagrees: {int(have.estimate_disagree.sum())}")
    df["year"] = pd.to_datetime(df.date).dt.year
    print("coverage by year:", df.groupby("year").eps_actual.apply(lambda x: f"{x.notna().mean():.0%}").to_dict())
    print("missing calls by ticker:", df[df.eps_actual.isna()].ticker.value_counts().to_dict())
    return df


if __name__ == "__main__":
    main(*sys.argv[1:3])
