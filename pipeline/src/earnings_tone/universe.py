"""The live feed's universe: the largest S&P 500 companies by market cap.

Market caps and earnings dates come from Yahoo Finance's public "largest market cap"
screener (query1.finance.yahoo.com, no key). Yahoo lists every US-traded equity, ADRs
included, so we keep only S&P 500 members from universe/sp500_members.txt: the tickers
with 2024+ calls in the Hugging Face S&P 500 transcript set. Edit that file when index
membership changes. Berkshire Hathaway is excluded by design (it holds no earnings call).
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

SCREENER = ("https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
            "?scrIds=largest_market_cap&count=250&start={start}")
MEMBERS_FILE = Path(__file__).resolve().parents[2] / "universe" / "sp500_members.txt"
UA = {"User-Agent": "Mozilla/5.0 (earnings-tone research project)"}
# Share classes of one company: keep the first listed, drop the rest.
DUPLICATE_CLASSES = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}


def load_members(path: str | Path = MEMBERS_FILE) -> set[str]:
    return {t.strip().upper() for t in Path(path).read_text().split() if t.strip()}


def _get(url: str, tries: int = 3) -> dict:
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 ** k)
    raise RuntimeError("unreachable")


def _ts(x) -> pd.Timestamp | None:
    return pd.Timestamp(int(x), unit="s", tz="UTC").tz_convert("America/New_York").tz_localize(None) if x else None


def screener_quotes(pages: int = 2) -> list[dict]:
    out: list[dict] = []
    for p in range(pages):
        out += _get(SCREENER.format(start=250 * p))["finance"]["result"][0]["quotes"]
    return out


def rank_universe(quotes: list[dict], members: set[str], n: int = 100) -> pd.DataFrame:
    """Top n members by market cap, with Yahoo's latest or next earnings timestamps."""
    rows = []
    for q in quotes:
        sym = str(q.get("symbol", "")).replace("-", ".").upper()
        if sym not in members or sym in DUPLICATE_CLASSES or not q.get("marketCap"):
            continue
        rows.append({
            "ticker": sym,
            "name": q.get("displayName") or q.get("shortName") or q.get("longName") or sym,
            "market_cap": float(q["marketCap"]),
            "earnings_at": _ts(q.get("earningsTimestamp")),
            "earnings_call_at": _ts(q.get("earningsCallTimestampStart")),
            "earnings_date_estimate": bool(q.get("isEarningsDateEstimate", False)),
        })
    df = pd.DataFrame(rows).drop_duplicates("ticker").sort_values("market_cap", ascending=False).head(n)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df.reset_index(drop=True)


def top_companies(n: int = 100, members_path: str | Path = MEMBERS_FILE) -> pd.DataFrame:
    return rank_universe(screener_quotes(), load_members(members_path), n)
