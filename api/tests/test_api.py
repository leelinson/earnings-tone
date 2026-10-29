import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "t.sqlite"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA.read_text())
    con.execute("INSERT INTO companies VALUES ('AAPL','Apple Inc.','Information Technology',2,'2024-01-01','2024-04-01')")
    con.execute("INSERT INTO calls VALUES ('AAPL_2024-01-03','AAPL','2024-01-03','2024-01-03',0,17,1,'2024Q1','2024-01-04',10,4000,1)")
    con.execute("INSERT INTO calls VALUES ('AAPL_2024-04-01','AAPL','2024-04-01','2024-04-01',0,17,1,'2024Q2',NULL,8,3000,0)")
    con.execute("INSERT INTO call_features (call_id, hedging_per1k, net_tone, hedging_pct) VALUES ('AAPL_2024-01-03', 12.5, 3.0, 80)")
    con.execute("INSERT INTO eps VALUES ('AAPL_2024-01-03','Beat',70,0)")
    con.execute("INSERT INTO car VALUES ('AAPL_2024-01-03',0.02,-0.01,0.0,1.1)")
    days = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
    for i, d in enumerate(days):
        con.execute("INSERT INTO prices VALUES ('AAPL',?,?)", (d, 100 + i))
        con.execute("INSERT INTO prices VALUES ('SPY',?,?)", (d, 400.0))
    con.execute("INSERT INTO qa_pairs VALUES ('AAPL_2024-01-03',1,'Q one','A one',50,5.0,1.0,0.3,0)")
    con.execute("INSERT INTO qa_pairs VALUES ('AAPL_2024-01-03',2,'Q two','A two',60,20.0,0.0,0.1,1)")
    con.execute("INSERT INTO study_runs VALUES ('r1','2026-10-27','test',1,?)",
                (json.dumps({"summary": [{"calls": 1}], "quintiles": [1, 2]}),))
    con.commit()
    con.close()
    import os
    os.environ["EARNINGS_TONE_DB"] = str(db)
    from app.main import app, db_path
    db_path.cache_clear()
    return TestClient(app)


def test_companies(client):
    r = client.get("/companies").json()
    assert [c["ticker"] for c in r] == ["AAPL"]


def test_company_summary_and_404(client):
    s = client.get("/companies/aapl").json()["summary"]
    assert s["calls_with_reaction"] == 1 and s["beat_rate"] == 1
    assert client.get("/companies/ZZZZ").status_code == 404


def test_calls_include_calls_without_returns(client):
    r = client.get("/companies/AAPL/calls").json()
    assert [c["call_id"] for c in r] == ["AAPL_2024-01-03", "AAPL_2024-04-01"]
    assert r[0]["car_0_1"] == 0.02 and r[1]["car_0_1"] is None


def test_weekly_prices_take_last_close_of_week(client):
    r = client.get("/companies/AAPL/prices").json()
    assert r == [{"date": "2024-01-05", "adj_close": 104.0}, {"date": "2024-01-08", "adj_close": 105.0}]


def test_window_is_relative_to_close_before_day0(client):
    r = client.get("/calls/AAPL_2024-01-03/window").json()
    day0 = next(p for p in r if p["day"] == 0)
    assert day0["date"] == "2024-01-04"
    assert day0["stock_pct"] == pytest.approx(100 * (103 / 102 - 1))
    assert day0["market_pct"] == 0
    assert [p["day"] for p in r] == [-3, -2, -1, 0, 1, 2]
    assert client.get("/calls/AAPL_2024-04-01/window").json() == []


def test_qa_sorted_by_hedging(client):
    r = client.get("/calls/AAPL_2024-01-03/qa?sort=hedging").json()
    assert [p["pair_no"] for p in r] == [2, 1]
    assert client.get("/calls/AAPL_2024-01-03/qa?sort=bogus").status_code == 422


def test_study_run_sections(client):
    assert client.get("/study/runs/r1").json()["sections"] == ["quintiles", "summary"]
    assert client.get("/study/runs/r1?section=quintiles").json() == [1, 2]
    assert client.get("/study/runs/r1?section=nope").status_code == 404


def test_search(client):
    assert client.get("/search?q=app").json()[0]["ticker"] == "AAPL"
