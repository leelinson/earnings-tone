"""Read-only API over the SQLite database built by pipeline/scripts/build_db.py.

Run locally:  EARNINGS_TONE_DB=../data/earnings_tone.sqlite uvicorn app.main:app --reload
"""
import json
import os
import sqlite3
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Earnings Tone API", version="0.1.0",
              description="Tone of earnings-call Q&A and the stock's reaction, for 64 US tech and communication services firms.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


@lru_cache
def db_path() -> str:
    return os.environ.get("EARNINGS_TONE_DB", "../data/earnings_tone.sqlite")


def rows(sql: str, *args) -> list[dict]:
    con = sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def one(sql: str, *args) -> dict:
    r = rows(sql, *args)
    if not r:
        raise HTTPException(404, "not found")
    return r[0]


CALL_COLS = """c.call_id, c.ticker, c.call_date, c.transcript_date, c.date_fixed, c.call_hour, c.after_close,
    c.quarter, c.reaction_day, c.n_questions, c.in_study,
    f.hedging_per1k, f.net_tone, f.tone_gap, f.relevance, f.non_answer_rate,
    f.hedging_pct, f.evasion_pct, f.net_tone_pct, f.tone_group,
    e.beat, e.surprise_pct, e.sources_disagree, k.car_0_1, k.car_2_20"""
CALL_JOIN = """calls c LEFT JOIN call_features f USING (call_id) LEFT JOIN eps e USING (call_id)
    LEFT JOIN car k USING (call_id)"""


@app.get("/companies")
def companies():
    return rows("SELECT * FROM companies ORDER BY ticker")


@app.get("/companies/{ticker}")
def company(ticker: str):
    c = one("SELECT * FROM companies WHERE ticker = ?", ticker.upper())
    c["summary"] = one(f"""SELECT COUNT(k.car_0_1) AS calls_with_reaction, AVG(f.hedging_pct) AS avg_hedging_pct,
        AVG(e.beat = 'Beat') AS beat_rate, AVG(k.car_0_1) AS avg_car_0_1, AVG(ABS(k.car_0_1)) AS avg_abs_car_0_1
        FROM {CALL_JOIN} WHERE c.ticker = ?""", c["ticker"])
    return c


@app.get("/companies/{ticker}/calls")
def company_calls(ticker: str):
    one("SELECT 1 FROM companies WHERE ticker = ?", ticker.upper())
    return rows(f"SELECT {CALL_COLS} FROM {CALL_JOIN} WHERE c.ticker = ? ORDER BY c.call_date", ticker.upper())


@app.get("/companies/{ticker}/prices")
def company_prices(ticker: str, start: str = "1900-01-01", end: str = "9999-12-31",
                   freq: str = Query("week", pattern="^(day|week)$")):
    t = ticker.upper()
    one("SELECT 1 FROM companies WHERE ticker = ?", t)
    if freq == "day":
        return rows("SELECT date, adj_close FROM prices WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date",
                    t, start, end)
    # last close of each Friday-ending week
    return rows("""SELECT MAX(date) AS date, adj_close FROM prices WHERE ticker = ? AND date BETWEEN ? AND ?
        GROUP BY date(date, 'weekday 5') ORDER BY date""", t, start, end)


@app.get("/calls/{call_id}")
def call(call_id: str):
    return one(f"SELECT {CALL_COLS} FROM {CALL_JOIN} WHERE c.call_id = ?", call_id)


@app.get("/calls/{call_id}/window")
def call_window(call_id: str, before: int = Query(5, ge=0, le=20), after: int = Query(20, ge=0, le=60)):
    """Stock and S&P 500 (SPY) % change from the close before day 0, trading days -before..+after."""
    c = one("SELECT ticker, reaction_day FROM calls WHERE call_id = ?", call_id)
    if not c["reaction_day"]:
        return []
    px = rows("""SELECT s.date, s.adj_close AS stock, m.adj_close AS market FROM prices s
        JOIN prices m ON m.ticker = 'SPY' AND m.date = s.date WHERE s.ticker = ? ORDER BY s.date""", c["ticker"])
    dates = [p["date"] for p in px]
    if c["reaction_day"] not in dates:
        return []
    d0 = dates.index(c["reaction_day"])
    if d0 == 0:
        return []
    base = px[d0 - 1]
    return [{"day": k, "date": px[d0 + k]["date"],
             "stock_pct": 100 * (px[d0 + k]["stock"] / base["stock"] - 1),
             "market_pct": 100 * (px[d0 + k]["market"] / base["market"] - 1)}
            for k in range(-before, after + 1) if 0 <= d0 + k < len(px)]


@app.get("/calls/{call_id}/qa")
def call_qa(call_id: str, sort: str = Query("order", pattern="^(order|hedging|relevance)$"), limit: int = Query(100, ge=1, le=200)):
    one("SELECT 1 FROM calls WHERE call_id = ?", call_id)
    order = {"order": "pair_no", "hedging": "hedging_per1k DESC", "relevance": "relevance ASC"}[sort]
    return rows(f"SELECT * FROM qa_pairs WHERE call_id = ? ORDER BY {order} LIMIT ?", call_id, limit)


@app.get("/study/runs")
def study_runs():
    return rows("SELECT run_id, run_at, label, n_calls FROM study_runs ORDER BY run_at DESC")


@app.get("/study/runs/{run_id}")
def study_run(run_id: str, section: str | None = None):
    r = one("SELECT * FROM study_runs WHERE run_id = ?", run_id)
    res = json.loads(r.pop("results"))
    if section is not None:
        if section not in res:
            raise HTTPException(404, f"no section {section!r}; have {sorted(res)}")
        return res[section]
    return {**r, "sections": sorted(res)}


@app.get("/search")
def search(q: str = Query(min_length=1, max_length=40)):
    like = f"%{q}%"
    return rows("""SELECT ticker, name, n_calls FROM companies WHERE ticker LIKE ? OR name LIKE ?
        ORDER BY ticker = ? DESC, ticker LIMIT 10""", like, like, q.upper())
