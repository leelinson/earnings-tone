"""Alpha Vantage client for earnings dates, EPS surprise and call transcripts.

Free keys allow 25 requests a day and 5 a minute (personal, non-commercial use).
Every call goes through `Client.get`, which spaces requests, counts them against the
day's budget and stops cleanly when Alpha Vantage says the limit is reached.

Endpoints used:
  EARNINGS                  one request per company: every quarter's fiscal period end,
                            report date, report time, reported and estimated EPS
  EARNINGS_CALL_TRANSCRIPT  one request per call, by fiscal quarter (YYYYQn)
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from .data import Transcript, Turn, label_turns

BASE = "https://www.alphavantage.co/query"


class BudgetExhausted(Exception):
    """The day's request budget is spent, or Alpha Vantage reports its rate limit."""


class Client:
    def __init__(self, api_key: str, budget: int = 25, min_interval: float = 12.5, opener=None):
        self.key, self.budget, self.min_interval = api_key, budget, min_interval
        self.used = 0
        self._last = 0.0
        self._open = opener or (lambda url: urllib.request.urlopen(url, timeout=60).read())

    @property
    def left(self) -> int:
        return self.budget - self.used

    def get(self, **params) -> dict:
        if self.used >= self.budget:
            raise BudgetExhausted(f"daily budget of {self.budget} requests used")
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        url = f"{BASE}?{urllib.parse.urlencode({**params, 'apikey': self.key})}"
        self._last = time.monotonic()
        self.used += 1
        data = json.loads(self._open(url))
        # Limits come back as HTTP 200 with a single "Information" or "Note" message.
        msg = data.get("Information") or data.get("Note") if isinstance(data, dict) else None
        if msg and len(data) == 1:
            raise BudgetExhausted(str(msg)[:200])
        if isinstance(data, dict) and "Error Message" in data:
            raise ValueError(data["Error Message"])
        return data

    def earnings(self, symbol: str, anchor: tuple[pd.Timestamp, str] | None = None) -> pd.DataFrame:
        return parse_earnings(self.get(function="EARNINGS", symbol=symbol), anchor)

    def transcript(self, symbol: str, quarter: str) -> list[dict]:
        return self.get(function="EARNINGS_CALL_TRANSCRIPT", symbol=symbol, quarter=quarter).get("transcript") or []


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fiscal_quarter(period_end: pd.Timestamp, fy_end_month: int) -> str:
    """Fiscal quarter label for a quarter ending on period_end, e.g. NVDA 2025-07-27 -> 2026Q2.

    Fiscal years are named for the calendar year they end in. A period ending within the
    first week of a month (52/53-week calendars, e.g. AAPL's 2024-12-28 vs 2025-01-04) is
    counted in the month before.
    """
    d = period_end - pd.Timedelta(days=7) if period_end.day <= 7 else period_end
    m, y = d.month, d.year
    q = ((m - fy_end_month - 1) % 12) // 3 + 1
    fy = y if m <= fy_end_month else y + 1
    return f"{fy}Q{q}"


ANCHORS_FILE = Path(__file__).resolve().parents[2] / "universe" / "fiscal_anchors.csv"
ANCHOR_TOLERANCE_DAYS = 7


def load_anchors(path: str | Path = ANCHORS_FILE) -> dict[str, tuple[pd.Timestamp, str]]:
    """ticker -> (date of its last Hugging Face call, that call's fiscal quarter label)."""
    if not Path(path).exists():
        return {}
    df = pd.read_csv(path)
    return {r.ticker: (pd.Timestamp(r.call_date), r.fiscal_quarter) for r in df.itertuples()}


def shift_quarter(label: str, n: int) -> str:
    """'2025Q4' shifted by +1 -> '2026Q1'."""
    y, q = int(label[:4]), int(label[-1])
    k = y * 4 + (q - 1) + n
    return f"{k // 4}Q{k % 4 + 1}"


def _fy_month_from_annual(data: dict) -> int:
    """Fallback only: the most common month among annual period ends (the newest row can be
    a partial year, and for some companies the rows are calendar years)."""
    months = [pd.Timestamp(a["fiscalDateEnding"]).month for a in data.get("annualEarnings", [])[1:]
              if a.get("fiscalDateEnding")]
    return max(set(months), key=months.count) if months else 12


def parse_earnings(data: dict, anchor: tuple[pd.Timestamp, str] | None = None) -> pd.DataFrame:
    """Quarterly rows with report date, report time, EPS surprise and the fiscal quarter label.

    Labels count quarters from the anchor: the company's last Hugging Face call, whose fiscal
    label is known (universe/fiscal_anchors.csv). That is exact whatever the fiscal calendar.
    Without an anchor the label falls back to a fiscal year-end guess and `label_source`
    says so; the transcript check in `stated_quarter` then guards against a wrong guess.
    """
    rows = []
    for r in data.get("quarterlyEarnings", []):
        if not r.get("reportedDate") or not r.get("fiscalDateEnding"):
            continue
        rows.append({
            "ticker": str(data.get("symbol", "")).upper(),
            "fiscal_period_end": pd.Timestamp(r["fiscalDateEnding"]),
            "report_date": pd.Timestamp(r["reportedDate"]),
            "report_time": r.get("reportTime"),
            "reported_eps": _num(r.get("reportedEPS")),
            "estimated_eps": _num(r.get("estimatedEPS")),
            "surprise_pct": _num(r.get("surprisePercentage")),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("fiscal_period_end").sort_values("fiscal_period_end").reset_index(drop=True)
    pos = None
    if anchor is not None:
        gap = (df["report_date"] - anchor[0]).abs()
        if gap.min() <= pd.Timedelta(days=ANCHOR_TOLERANCE_DAYS):
            pos = int(gap.idxmin())
    if pos is not None:
        df["fiscal_quarter"] = [shift_quarter(anchor[1], i - pos) for i in range(len(df))]
        df["label_source"] = "anchor"
    else:
        m = _fy_month_from_annual(data)
        df["fiscal_quarter"] = [fiscal_quarter(e, m) for e in df["fiscal_period_end"]]
        df["label_source"] = "fy_month_guess"
    return df.sort_values("report_date").reset_index(drop=True)


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4}
STATED_RE = re.compile(
    r"\b(first|second|third|fourth|1st|2nd|3rd|4th)[- ]quarter(?:\s+(?:of\s+)?(?:fiscal\s+(?:year\s+)?)?(20\d\d))?"
    r"|\bfiscal\s+(?:year\s+)?(20\d\d)\s+(first|second|third|fourth)[- ]quarter"
    r"|\bQ([1-4])\s+(?:FY\s?|fiscal\s+)?'?(20\d\d|\d\d)\b",
    re.I,
)


def stated_quarter(entries: list[dict], n_entries: int = 4) -> tuple[int, int | None] | None:
    """The quarter (and year, if said) a transcript's opening names, e.g. "welcome to the
    third quarter fiscal 2026 call" -> (3, 2026). None when the opening names no quarter."""
    text = " ".join(str(e.get("content") or "") for e in entries[:n_entries])
    m = STATED_RE.search(text)
    if not m:
        return None
    if m.group(1):
        return ORDINALS[m.group(1).lower()], int(m.group(2)) if m.group(2) else None
    if m.group(3):
        return ORDINALS[m.group(4).lower()], int(m.group(3))
    y = int(m.group(6))
    return int(m.group(5)), y + 2000 if y < 100 else y


def label_agrees(label: str, entries: list[dict]) -> bool:
    """False only when the transcript's opening clearly names a different quarter or year."""
    st = stated_quarter(entries)
    if st is None:
        return True
    q, y = st
    return q == int(label[-1]) and (y is None or y == int(label[:4]))


ANALYST_TITLE = ("analyst", "research", "securities", "capital", "partners", "bank", "llc", "& co")
EXEC_TITLE = ("chief", "ceo", "cfo", "president", "officer", "vice", "head", "director", "chair",
              "investor relations", "treasurer", "founder", "general manager", "evp", "svp")


def to_transcript(ticker: str, call_date: pd.Timestamp, after_close: bool, entries: list[dict]) -> Transcript | None:
    """Turn Alpha Vantage's [{speaker, title, content, sentiment}] list into a labelled Transcript.

    The shared parser finds where Q&A starts and labels roles; titles then correct roles
    where they are explicit (an "Analyst" title, or a C-suite title).
    """
    turns = [Turn(str(e.get("speaker") or "").strip(), str(e.get("content") or "")) for e in entries]
    turns = [t for t in turns if t.text.strip()]
    if len(turns) < 4:
        return None
    turns = label_turns(turns)
    titles = [str(e.get("title") or "").lower() for e in entries if str(e.get("content") or "").strip()]
    for t, title in zip(turns, titles):
        if t.role == "operator" or "operator" in title:
            continue
        if any(k in title for k in EXEC_TITLE):
            t.role = "exec"
        elif any(k in title for k in ANALYST_TITLE) and t.section == "qa":
            t.role = "analyst"
    sent = [_num(e.get("sentiment")) for e in entries]
    sent = [s for s in sent if s is not None]
    meta = {"av_sentiment": sum(sent) / len(sent) if sent else None}
    return Transcript(ticker.upper(), pd.Timestamp(call_date).normalize(), turns, after_close, meta)
