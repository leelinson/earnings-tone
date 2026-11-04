import json
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

from earnings_tone import alphavantage as av, feed, universe
from test_nlp import fake_scorer

TODAY = pd.Timestamp("2025-08-01")

ENTRIES = [
    {"speaker": "Operator", "title": "Operator", "content": "Welcome to the second quarter call.", "sentiment": "0.1"},
    {"speaker": "Jane Doe", "title": "Chief Executive Officer", "content": "Revenue grew strongly this quarter. Margins grew in every region.", "sentiment": "0.8"},
    {"speaker": "John Roe", "title": "Chief Financial Officer", "content": "Cash flow grew to a record level for the year.", "sentiment": "0.7"},
    {"speaker": "Operator", "title": "Operator", "content": "We will now begin the question-and-answer session. Our first question comes from Sam Lee with Big Bank.", "sentiment": "0.0"},
    {"speaker": "Sam Lee", "title": "Analyst", "content": "Why did sales in China slow down this quarter?", "sentiment": "-0.2"},
    {"speaker": "Jane Doe", "title": "Chief Executive Officer", "content": "China sales declined on weaker demand. We expect the region to stay about the same.", "sentiment": "-0.3"},
    {"speaker": "Operator", "title": "Operator", "content": "Our next question comes from Ann Kim with Other Bank.", "sentiment": "0.0"},
    {"speaker": "Ann Kim", "title": "Analyst", "content": "How should we think about margins for next year?", "sentiment": "0.0"},
    {"speaker": "John Roe", "title": "Chief Financial Officer", "content": "Margins grew this year and we see that holding next year too.", "sentiment": "0.5"},
]


def earnings_json(sym):
    return {"symbol": sym, "annualEarnings": [{"fiscalDateEnding": "2024-12-31"}],
            "quarterlyEarnings": [
                {"fiscalDateEnding": "2025-06-30", "reportedDate": "2025-07-29", "reportedEPS": "1.1",
                 "estimatedEPS": "1.0", "surprisePercentage": "10", "reportTime": "post-market"},
                {"fiscalDateEnding": "2025-03-31", "reportedDate": "2025-04-29", "reportedEPS": "0.9",
                 "estimatedEPS": "1.0", "surprisePercentage": "-10", "reportTime": "pre-market"},
                {"fiscalDateEnding": "2024-12-31", "reportedDate": "2025-01-28", "reportedEPS": "1.0",
                 "estimatedEPS": "1.0", "surprisePercentage": "0", "reportTime": "post-market"}]}


class FakeAV:
    """Serves EARNINGS for any symbol and transcripts except the ones listed as missing."""
    def __init__(self, missing=(), limit_after=None):
        self.calls, self.missing, self.limit_after = [], set(missing), limit_after

    def __call__(self, url):
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        self.calls.append((q["function"], q["symbol"], q.get("quarter")))
        if self.limit_after is not None and len(self.calls) > self.limit_after:
            return json.dumps({"Information": "Our standard API rate limit is 25 requests per day."})
        if q["function"] == "EARNINGS":
            return json.dumps(earnings_json(q["symbol"]))
        if (q["symbol"], q["quarter"]) in self.missing:
            return json.dumps({"symbol": q["symbol"], "quarter": q["quarter"], "transcript": []})
        return json.dumps({"symbol": q["symbol"], "quarter": q["quarter"], "transcript": ENTRIES})


def uni(tickers=("AAA", "BBB")):
    return pd.DataFrame({"rank": range(1, len(tickers) + 1), "ticker": list(tickers), "name": [t + " Inc" for t in tickers],
                         "market_cap": [1e12 / (i + 1) for i in range(len(tickers))],
                         "earnings_at": [pd.Timestamp("2025-07-29 16:05")] + [pd.Timestamp("2025-10-28")] * (len(tickers) - 1),
                         "earnings_call_at": [None] * len(tickers), "earnings_date_estimate": [False] * len(tickers)})


LEX = {"positive": {"grew", "record", "strongly"}, "negative": {"declined", "weaker"},
       "uncertainty": {"expect"}, "weak_modal": set()}


@pytest.mark.parametrize("end,fy,label", [
    ("2025-07-27", 1, "2026Q2"),   # NVDA, fiscal year ends late January
    ("2024-12-28", 9, "2025Q1"),   # AAPL, fiscal year ends late September
    ("2025-09-30", 6, "2026Q1"),   # MSFT, June year end
    ("2025-09-30", 12, "2025Q3"),  # calendar year
    ("2025-01-04", 9, "2025Q1"),   # 53-week quarter ending in the first days of a month
])
def test_fiscal_quarter(end, fy, label):
    assert av.fiscal_quarter(pd.Timestamp(end), fy) == label


def test_parse_earnings_reads_fiscal_year_end():
    e = av.parse_earnings({"symbol": "nvda", "annualEarnings": [{"fiscalDateEnding": "2025-01-26"}],
                           "quarterlyEarnings": [{"fiscalDateEnding": "2025-07-27", "reportedDate": "2025-08-27",
                                                  "reportedEPS": "1.05", "estimatedEPS": "1.01",
                                                  "surprisePercentage": "3.96", "reportTime": "post-market"}]})
    assert e.loc[0, "fiscal_quarter"] == "2026Q2" and e.loc[0, "ticker"] == "NVDA" and e.loc[0, "surprise_pct"] == 3.96


def test_to_transcript_labels_sections_and_roles():
    t = av.to_transcript("AAA", pd.Timestamp("2025-07-29"), True, ENTRIES)
    assert len(t.qa_pairs()) == 2
    assert {x.role for x in t.turns if x.speaker == "Sam Lee"} == {"analyst"}
    assert np.isclose(t.meta["av_sentiment"], np.mean([float(e["sentiment"]) for e in ENTRIES]))


def test_rank_universe_filters_members_and_share_classes():
    q = [{"symbol": s, "marketCap": m, "displayName": s, "earningsTimestamp": 1753819200}
         for s, m in [("NVDA", 5e12), ("TSM", 2e12), ("GOOGL", 3e12), ("GOOG", 3e12), ("BRK-B", 1e12), ("BF-B", 1e10)]]
    u = universe.rank_universe(q, {"NVDA", "GOOGL", "GOOG", "BF.B"}, n=10)
    assert u["ticker"].tolist() == ["NVDA", "GOOGL", "BF.B"] and u["rank"].tolist() == [1, 2, 3]
    assert u.loc[0, "earnings_at"] == pd.Timestamp("2025-07-29 16:00")


def test_update_scores_new_and_backfill_and_respects_budget():
    fake = FakeAV(missing={("BBB", "2025Q2")})
    state = feed.State()
    client = av.Client("k", budget=8, min_interval=0, opener=fake)
    stats = feed.update(state, uni(), client, fake_scorer, LEX, today=TODAY, log=lambda *_: None)
    # AAA reported 3 days ago so goes first: EARNINGS then newest quarter first.
    assert fake.calls[:4] == [("EARNINGS", "AAA", None), ("EARNINGS_CALL_TRANSCRIPT", "AAA", "2025Q2"),
                              ("EARNINGS_CALL_TRANSCRIPT", "AAA", "2025Q1"), ("EARNINGS_CALL_TRANSCRIPT", "AAA", "2024Q4")]
    assert stats["requests_used"] == 8 and stats["scored"] == 5 and stats["transcripts_empty"] == 1
    assert state.attempts["BBB|2025Q2"]["tries"] == 1
    row = state.calls.iloc[0]
    assert row["fiscal_quarter"] == "2025Q2" and row["surprise_pct"] == 10 and bool(row["call_after_close"])
    assert row["fb_prep_net"] > 0 and "declined" in json.loads(row["excerpts"])["negative"][0]["text"]
    assert not bool(state.calls.set_index("fiscal_quarter").loc["2025Q1"].iloc[0]["call_after_close"])

    # Next day: nothing new to fetch for AAA; BBB's missing quarter waits RETRY_DAYS.
    fake2 = FakeAV()
    stats2 = feed.update(state, uni(), av.Client("k", budget=25, min_interval=0, opener=fake2), fake_scorer, LEX,
                         today=TODAY + pd.Timedelta(days=1), log=lambda *_: None)
    assert stats2["requests_used"] == 0
    stats3 = feed.update(state, uni(), av.Client("k", budget=25, min_interval=0, opener=fake2), fake_scorer, LEX,
                         today=TODAY + pd.Timedelta(days=3), log=lambda *_: None)
    assert fake2.calls == [("EARNINGS_CALL_TRANSCRIPT", "BBB", "2025Q2")] and stats3["scored"] == 1
    assert "BBB|2025Q2" not in state.attempts


def test_rate_limit_message_stops_cleanly():
    state = feed.State()
    stats = feed.update(state, uni(), av.Client("k", budget=25, min_interval=0, opener=FakeAV(limit_after=2)),
                        fake_scorer, LEX, today=TODAY, log=lambda *_: None)
    assert stats["scored"] == 1 and stats["requests_used"] == 3


def test_state_round_trip_history_and_export(tmp_path):
    state = feed.State()
    feed.update(state, uni(["AAA"]), av.Client("k", budget=4, min_interval=0, opener=FakeAV()), fake_scorer, LEX,
                today=TODAY, log=lambda *_: None)
    hist = state.calls.copy()
    hist["call_date"] = [pd.Timestamp("2024-01-30") - pd.DateOffset(months=3 * i) for i in range(len(hist))]
    hist["qa_net_tone"] = [1.0, 2.0, 3.0]
    more = hist.copy(); more["call_date"] = more["call_date"] - pd.DateOffset(years=1)
    feed.add_history(state, pd.concat([hist, more]).drop(columns=["source"]))
    feed.add_history(state, hist.drop(columns=["source"]))  # duplicates are skipped
    assert len(state.calls) == 9 and (state.calls["source"] == "huggingface").sum() == 6
    state.save(tmp_path / "s")
    again = feed.State.load(tmp_path / "s")
    assert len(again.calls) == 9 and again.attempts == state.attempts
    p = feed.export_site(again, uni(["AAA"]), tmp_path / "site", today=TODAY)
    d = json.loads(p.read_text())
    assert len(d["calls"]) == 3 and d["calls"][0]["call_date"] == "2025-07-29"
    assert d["calls"][0]["own_z_qa_net_tone"] is not None and d["calls"][0]["name"] == "AAA Inc"
    assert d["calls"][0]["excerpts"]["positive"] and d["upcoming"] == []
