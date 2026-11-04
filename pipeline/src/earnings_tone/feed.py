"""Live feed: score new earnings calls for the largest S&P 500 companies.

One `update` run (daily in GitHub Actions):
  1. rank the universe by market cap (Yahoo, no key)
  2. spend the Alpha Vantage request budget: first on companies that just reported
     (refresh EARNINGS, then fetch the new transcript), then on backfilling missed
     quarters, largest companies first
  3. score each new transcript: Loughran-McDonald counts, FinBERT, Alpha Vantage's own
     sentiment, and a few short excerpts
  4. refresh stock reactions (CARs) from Yahoo prices for every call in the feed
  5. write site JSON with each call ranked against its company's history and its peers

State lives in one folder (kept as a release asset by the workflow). It holds derived
scores and short excerpts only, never transcript text:
  calls.parquet     one row per scored call
  earnings.parquet  Alpha Vantage EARNINGS rows per company (report dates, EPS surprise)
  attempts.json     transcript requests that came back empty, so they are retried later
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import alphavantage as av
from . import features, nlp, prices

FEED_START = pd.Timestamp("2025-01-01")  # calls before this come from the Hugging Face history
RECENT_DAYS = 10            # a report this recent is "new" and jumps the queue
EARNINGS_STALE_DAYS = 30    # refetch EARNINGS at least this often
RETRY_DAYS = 2              # wait between tries when a transcript is not posted yet
MAX_TRIES = 4
HISTORY_MIN = 4             # own-history z-scores need this many earlier calls

METRICS = {
    "fb_qa_net": "FinBERT tone in answers",
    "fb_prep_net": "FinBERT tone in prepared remarks",
    "fb_tone_gap": "FinBERT tone gap (prepared minus answers)",
    "fb_q_net": "FinBERT tone of analyst questions",
    "qa_net_tone": "LM net tone in answers",
    "qa_hedging": "LM hedging in answers",
    "tone_gap": "LM tone gap",
    "qa_relevance": "Answer relevance",
    "non_answer_rate": "Non-answer rate",
}


@dataclass
class State:
    calls: pd.DataFrame = field(default_factory=pd.DataFrame)
    earnings: pd.DataFrame = field(default_factory=pd.DataFrame)
    attempts: dict = field(default_factory=dict)

    @classmethod
    def load(cls, d: str | Path) -> "State":
        d = Path(d)
        rd = lambda n: pd.read_parquet(d / n) if (d / n).exists() else pd.DataFrame()
        att = json.loads((d / "attempts.json").read_text()) if (d / "attempts.json").exists() else {}
        return cls(rd("calls.parquet"), rd("earnings.parquet"), att)

    def save(self, d: str | Path) -> None:
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        self.calls.to_parquet(d / "calls.parquet")
        self.earnings.to_parquet(d / "earnings.parquet")
        (d / "attempts.json").write_text(json.dumps(self.attempts, indent=1, sort_keys=True))

    def has_call(self, ticker: str, date: pd.Timestamp, days: int = 5) -> bool:
        if self.calls.empty:
            return False
        c = self.calls[self.calls["ticker"] == ticker]
        return bool(((pd.to_datetime(c["call_date"]) - date).abs() <= pd.Timedelta(days=days)).any())


def score_transcript(t, scorer, lexicon, extra: dict) -> dict:
    """All call-level measures for one transcript, plus short excerpts for the site."""
    row = features.transcript_features(t, lexicon)
    row.update({k: v for k, v in nlp.transcript_scores(t, scorer).items() if k.startswith("fb_")})
    ex = nlp.most_extreme(t, scorer, n=2)
    row["excerpts"] = json.dumps({k: [{"text": e["text"][:280], "score": e["score"]} for e in v] for k, v in ex.items()})
    row.update(extra)
    return row


def _due_quarters(state: State, ticker: str, today: pd.Timestamp) -> list[dict]:
    """Reported quarters since FEED_START with no scored call yet, newest first."""
    e = state.earnings
    if e.empty:
        return []
    e = e[(e["ticker"] == ticker) & (e["report_date"] >= FEED_START) & (e["report_date"] < today)]
    out = []
    for r in e.sort_values("report_date", ascending=False).to_dict("records"):
        if state.has_call(ticker, r["report_date"]):
            continue
        a = state.attempts.get(f"{ticker}|{r['fiscal_quarter']}", {})
        if a.get("tries", 0) >= MAX_TRIES:
            continue
        if a.get("last") and today - pd.Timestamp(a["last"]) < pd.Timedelta(days=RETRY_DAYS):
            continue
        out.append(r)
    return out


def _earnings_stale(state: State, ticker: str, yahoo_last: pd.Timestamp | None, today: pd.Timestamp) -> bool:
    e = state.earnings
    if e.empty or ticker not in set(e["ticker"]):
        return True
    mine = e[e["ticker"] == ticker]
    fetched = pd.Timestamp(mine["fetched"].max())
    if today - fetched >= pd.Timedelta(days=EARNINGS_STALE_DAYS):
        return True
    # Yahoo shows a report since we last looked that Alpha Vantage's table lacks.
    return bool(yahoo_last is not None and yahoo_last > fetched and yahoo_last < today
                and not (mine["report_date"] >= yahoo_last.normalize() - pd.Timedelta(days=1)).any())


def plan(state: State, uni: pd.DataFrame, today: pd.Timestamp) -> list[str]:
    """Order to visit companies: just reported first, then everyone by market cap."""
    recent = uni[uni["earnings_at"].notna() & (uni["earnings_at"] < today)
                 & (uni["earnings_at"] >= today - pd.Timedelta(days=RECENT_DAYS))]
    first = recent.sort_values("earnings_at", ascending=False)["ticker"].tolist()
    return first + [t for t in uni["ticker"] if t not in first]


def update(state: State, uni: pd.DataFrame, client: av.Client, scorer, lexicon,
           today: pd.Timestamp | None = None, log=print, anchors: dict | None = None) -> dict:
    today = (today or pd.Timestamp.now(tz="America/New_York").tz_localize(None)).normalize()
    anchors = av.load_anchors() if anchors is None else anchors
    new_rows = []
    stats = {"earnings_fetched": 0, "transcripts_fetched": 0, "transcripts_empty": 0,
             "label_mismatch": 0, "scored": 0}
    yahoo_last = dict(zip(uni["ticker"], uni["earnings_at"]))
    try:
        for ticker in plan(state, uni, today):
            last = yahoo_last.get(ticker)
            last = None if last is None or pd.isna(last) else pd.Timestamp(last)
            if _earnings_stale(state, ticker, last, today):
                e = client.earnings(ticker, anchors.get(ticker))
                stats["earnings_fetched"] += 1
                if not e.empty:
                    e["ticker"] = ticker
                    e["fetched"] = today
                    keep = state.earnings[state.earnings["ticker"] != ticker] if not state.earnings.empty else state.earnings
                    state.earnings = pd.concat([keep, e], ignore_index=True)
            for r in _due_quarters(state, ticker, today):
                key = f"{ticker}|{r['fiscal_quarter']}"
                entries = client.transcript(ticker, r["fiscal_quarter"])
                stats["transcripts_fetched"] += 1
                if entries and not av.label_agrees(r["fiscal_quarter"], entries):
                    # The opening names another quarter: our label is off, so never store it.
                    state.attempts[key] = {"tries": MAX_TRIES, "last": str(today.date()),
                                           "status": f"label_mismatch: says {av.stated_quarter(entries)}"}
                    stats["label_mismatch"] += 1
                    log(f"  {key}: transcript names {av.stated_quarter(entries)}, skipped")
                    continue
                after_close = r.get("report_time") != "pre-market"
                t = av.to_transcript(ticker, r["report_date"], after_close, entries) if entries else None
                if t is None or not t.qa_pairs():
                    a = state.attempts.get(key, {})
                    state.attempts[key] = {"tries": a.get("tries", 0) + 1, "last": str(today.date())}
                    stats["transcripts_empty"] += 1
                    log(f"  {key}: no usable transcript yet")
                    continue
                state.attempts.pop(key, None)
                row = score_transcript(t, scorer, lexicon, {
                    "source": "alphavantage", "fiscal_quarter": r["fiscal_quarter"],
                    "report_time": r.get("report_time"), "surprise_pct": r.get("surprise_pct"),
                    "reported_eps": r.get("reported_eps"), "estimated_eps": r.get("estimated_eps"),
                    "av_sentiment": t.meta.get("av_sentiment"),
                })
                new_rows.append(row)
                stats["scored"] += 1
                log(f"  {key}: scored ({row['fb_qa_n_sent']} answer sentences)")
    except av.BudgetExhausted as e:
        log(f"Stopping: {e}")
    if new_rows:
        add = pd.DataFrame(new_rows)
        state.calls = pd.concat([state.calls, add], ignore_index=True) if not state.calls.empty else add
    stats["requests_used"] = client.used
    return stats


def refresh_cars(state: State, px: pd.DataFrame) -> None:
    """Recompute CARs for every call; recent calls gain them once day +1 has closed."""
    if state.calls.empty:
        return
    c = state.calls.drop(columns=[x for x in ("event_day0", "beta", "resid_sd", *prices.WINDOWS) if x in state.calls])
    c["call_date"] = pd.to_datetime(c["call_date"])
    cars = prices.compute_cars(px, c[["ticker", "call_date", "call_after_close"]])
    state.calls = c.merge(cars, on=["ticker", "call_date"], how="left") if not cars.empty else c


def add_history(state: State, hist: pd.DataFrame) -> None:
    """Merge pre-feed calls (Hugging Face) so each company has a baseline. Feed rows win."""
    hist = hist.assign(source=hist.get("source", "huggingface"))
    hist["call_date"] = pd.to_datetime(hist["call_date"])
    if state.calls.empty:
        state.calls = hist.reset_index(drop=True)
        return
    keep = [r for r in hist.itertuples(index=False) if not state.has_call(r.ticker, r.call_date)]
    state.calls = pd.concat([state.calls, pd.DataFrame(keep, columns=hist.columns)], ignore_index=True)


def ranked(calls: pd.DataFrame) -> pd.DataFrame:
    """Add own-history z-scores (vs the company's earlier calls) and peer percentiles (same quarter)."""
    df = calls.copy()
    df["call_date"] = pd.to_datetime(df["call_date"])
    df = df.sort_values(["ticker", "call_date"]).reset_index(drop=True)
    df["quarter"] = pd.PeriodIndex(df["call_date"], freq="Q").astype(str)
    for m in METRICS:
        if m not in df:
            continue
        g = df.groupby("ticker")[m]
        prior_mean = g.transform(lambda s: s.shift().expanding(HISTORY_MIN).mean())
        prior_sd = g.transform(lambda s: s.shift().expanding(HISTORY_MIN).std())
        df[f"own_z_{m}"] = (df[m] - prior_mean) / prior_sd.replace(0, np.nan)
        df[f"pct_{m}"] = df.groupby("quarter")[m].rank(pct=True) * 100
    return df


def _clean(v):
    if v is None or v is pd.NaT or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else round(float(v), 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return v


def export_site(state: State, uni: pd.DataFrame, out: str | Path, today: pd.Timestamp | None = None,
                since: pd.Timestamp = FEED_START) -> Path:
    """web/data/feed/latest.json: the universe, upcoming reports and every scored feed call."""
    today = (today or pd.Timestamp.now(tz="America/New_York").tz_localize(None)).normalize()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = ranked(state.calls) if not state.calls.empty else pd.DataFrame()
    cols = ["ticker", "call_date", "quarter", "fiscal_quarter", "source", "report_time", "surprise_pct",
            "car_0_1", "car_2_20", "av_sentiment", "excerpts", "n_questions",
            *METRICS, *[f"own_z_{m}" for m in METRICS], *[f"pct_{m}" for m in METRICS]]
    names = dict(zip(uni["ticker"], uni["name"]))
    rank = dict(zip(uni["ticker"], uni["rank"]))
    calls = []
    if not df.empty:
        recent = df[(df["call_date"] >= since) & df["ticker"].isin(names)].sort_values("call_date", ascending=False)
        for r in recent.to_dict("records"):
            row = {k: _clean(r.get(k)) for k in cols if k in r}
            row["excerpts"] = json.loads(r["excerpts"]) if isinstance(r.get("excerpts"), str) else None
            row["name"], row["rank"] = names[r["ticker"]], rank[r["ticker"]]
            calls.append(row)
    upcoming = uni[uni["earnings_at"].notna() & (uni["earnings_at"] >= today)
                   & (uni["earnings_at"] < today + pd.Timedelta(days=45))].sort_values("earnings_at")
    payload = {
        "updated": pd.Timestamp.now(tz="UTC").isoformat(timespec="minutes"),
        "metrics": METRICS,
        "universe": [{k: _clean(v) for k, v in r.items()} for r in
                     uni[["rank", "ticker", "name", "market_cap", "earnings_at"]].to_dict("records")],
        "upcoming": [{"ticker": r["ticker"], "name": r["name"], "date": _clean(pd.Timestamp(r["earnings_at"]).normalize()),
                      "estimate": bool(r["earnings_date_estimate"])} for r in upcoming.head(30).to_dict("records")],
        "calls": calls,
        "n_companies_with_calls": len({c["ticker"] for c in calls}),
    }
    p = out / "latest.json"
    p.write_text(json.dumps(payload, default=str))
    return p
