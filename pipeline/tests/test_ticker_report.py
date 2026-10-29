import pandas as pd

from earnings_tone import cli, data, features, prices, study, surprise, synthetic, ticker_report


def _synthetic(tmp_path):
    d = synthetic.make_synthetic(tmp_path, n_firms=6, n_quarters=10)
    feats = features.build_features(data.load_transcripts(d / "transcripts.jsonl"))
    cars = prices.compute_cars(pd.read_parquet(d / "prices.parquet"), feats)
    panel = study.build_panel(feats, cars, surprise.load_surprise(d / "eps_surprise.csv"))
    return d, panel


def test_loads_only_the_chosen_ticker(tmp_path):
    d, _ = _synthetic(tmp_path)
    ts = ticker_report.load_ticker_transcripts(d / "transcripts.jsonl", "t001")
    assert len(ts) == 10 and {t.ticker for t in ts} == {"T001"}
    assert list(pd.Series([t.call_date for t in ts]).sort_values()) == [t.call_date for t in ts]


def test_qa_exchanges_keep_speakers():
    t = data.Transcript("X", pd.Timestamp("2024-01-01"), data.label_turns(data.parse_raw_text(
        "Operator: Welcome.\nJane Doe -- CEO: Revenue grew.\n"
        "Operator: We will now begin the question-and-answer session.\n"
        "Sam Lee -- Big Bank: What drove margin?\nJane Doe: Pricing.\nJohn Roe: And mix.\n")))
    ex = ticker_report.qa_exchanges(t)
    assert ex == [{"analyst": "Sam Lee", "question": "What drove margin?",
                   "answer": "Pricing. And mix.", "answered_by": ["Jane Doe", "John Roe"]}]


def test_analysis_with_panel(tmp_path):
    d, panel = _synthetic(tmp_path)
    ts = ticker_report.load_ticker_transcripts(d / "transcripts.jsonl", "T002")
    res = ticker_report.analyze_ticker(ts, panel=panel, recent=3)
    c = res["calls"]
    assert len(c) == 10 and len(res["answers"]) == 50
    assert c["car_0_1"].notna().sum() >= 8
    assert c["pct_qa_hedging"].dropna().between(0, 100).all()
    assert c["own_z_qa_hedging"].iloc[:4].isna().all() and c["own_z_qa_hedging"].iloc[5:].notna().all()
    assert res["keywords"]["per_call"] and set(res["returns_link"]["return"]) == {"car_0_1", "car_2_20"}


def test_cli_writes_report(tmp_path):
    d, panel = _synthetic(tmp_path)
    panel.to_parquet(tmp_path / "panel.parquet")
    out = tmp_path / "rep"
    cli.main(["ticker", "--ticker", "T003", "--transcripts", str(d / "transcripts.jsonl"),
              "--panel", str(tmp_path / "panel.parquet"), "--out", str(out)])
    for f in ["report.md", "tone_trend.png", "calls.csv", "answers.csv", "analysis.json"]:
        assert (out / f).exists(), f
    md = (out / "report.md").read_text()
    assert "# T003 earnings call NLP analysis" in md and "CAR[0,+1]" in md
