"""Command line entry point: python -m earnings_tone.cli <command>."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import data, features, feed, nlp, prices, study, surprise, synthetic, ticker_report, universe


def cmd_demo(a):
    d = synthetic.make_synthetic(a.out)
    ts = data.load_transcripts(d / "transcripts.jsonl")
    feats = features.build_features(ts)
    cars = prices.compute_cars(pd.read_parquet(d / "prices.parquet"), feats)
    panel = study.build_panel(feats, cars, surprise.load_surprise(d / "eps_surprise.csv"))
    res = study.run_study(panel, d / "report", split_quarter="2020Q1")
    b = res["H2_evasion"].params["z_evasion"] * 1e4
    print(f"Parsed {len(ts)} transcripts, {len(cars)} CARs.")
    print(f"Evasion coef: {b:.1f} bps per SD (planted effect drives this negative; "
          f"exact size differs because the text measure is a noisy proxy).")
    print(f"Report: {d / 'report' / 'results.md'}")


def cmd_fetch(a):
    tickers = [t.strip() for t in Path(a.tickers_file).read_text().split() if t.strip()]
    n = data.fetch_hf_transcripts(tickers, a.out, start_year=a.start_year)
    print(f"Wrote {n} transcripts to {a.out}")


def cmd_features(a):
    lex = features.load_lm_dictionary(a.lm_dict) if a.lm_dict else None
    feats = features.build_features(data.load_transcripts(a.transcripts), lex)
    feats.to_parquet(a.out)
    print(f"{len(feats)} rows -> {a.out}")


def cmd_prices(a):
    feats = pd.read_parquet(a.features)
    start = (feats["call_date"].min() - pd.Timedelta(days=400)).date().isoformat()
    px = prices.fetch_prices(feats["ticker"].unique().tolist(), start=start)
    px.to_parquet(Path(a.out).with_name("prices.parquet"))
    cars = prices.compute_cars(px, feats)
    cars.to_parquet(a.out)
    print(f"{len(cars)} CARs -> {a.out}")


def cmd_study(a):
    panel = study.build_panel(pd.read_parquet(a.features), pd.read_parquet(a.car),
                              surprise.load_surprise(a.surprise) if a.surprise else None)
    study.run_study(panel, a.out, split_quarter=a.split)
    print(f"Report: {Path(a.out) / 'results.md'}")


def cmd_ticker(a):
    ts = ticker_report.load_ticker_transcripts(a.transcripts, a.ticker)
    if not ts:
        raise SystemExit(f"No parseable calls for {a.ticker.upper()} in {a.transcripts}")
    lex = features.load_lm_dictionary(a.lm_dict) if a.lm_dict else None
    panel = pd.read_parquet(a.panel) if a.panel else None
    res = ticker_report.analyze_ticker(ts, lex, panel, recent=a.recent)
    out = Path(a.out or f"reports/{res['ticker']}")
    path = ticker_report.save_outputs(res, out, a.call)
    print(f"{res['ticker']}: {len(ts)} calls, {len(res['answers'])} Q&A exchanges. Report: {path}")


def cmd_nlp(a):
    ts = data.load_transcripts(a.transcripts)
    scores = nlp.build_scores(ts, nlp.FinBert(onnx_file=a.onnx_file), progress=True)
    if a.features:  # append to an existing features table
        f = pd.read_parquet(a.features)
        scores = f.merge(scores, on=["ticker", "call_date"], how="left")
    scores.to_parquet(a.out)
    print(f"{len(scores)} rows with FinBERT tone -> {a.out}")


def _universe(a):
    uni = universe.top_companies(a.top)
    print(f"Universe: top {len(uni)} S&P 500 companies by market cap ({uni['ticker'].iloc[0]} first)")
    return uni


def cmd_feed_update(a):
    import os
    from . import alphavantage as av

    key = os.environ.get("ALPHAVANTAGE_API_KEY")
    state = feed.State.load(a.state)
    uni = _universe(a)
    if key:
        stats = feed.update(state, uni, av.Client(key, budget=a.budget), nlp.FinBert(),
                            features.load_lm_from_pysentiment2())
        print("Alpha Vantage:", stats)
    else:
        print("No ALPHAVANTAGE_API_KEY (free key: https://www.alphavantage.co/support/#api-key): "
              "skipping new transcripts, refreshing reactions and site data only")
    if not state.calls.empty:
        px = prices.fetch_prices_yahoo(sorted(set(state.calls["ticker"])),
                                       start=str((pd.to_datetime(state.calls["call_date"]).min()
                                                  - pd.Timedelta(days=400)).date()))
        feed.refresh_cars(state, px)
    state.save(a.state)
    print("Site data:", feed.export_site(state, uni, a.site_out))


def cmd_feed_history(a):
    """Score Hugging Face transcripts for the universe so every company has a baseline."""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    state = feed.State.load(a.state)
    uni = _universe(a)
    path = hf_hub_download("kurry/sp500_earnings_transcripts", "parquet_files/part-0.parquet", repo_type="dataset")
    tbl = pq.read_table(path, columns=["symbol", "year", "quarter", "date", "structured_content", "company_name"],
                        filters=[("year", ">=", pd.Timestamp(a.since).year)])
    tbl = tbl.filter(pc.is_in(tbl["symbol"], value_set=__import__("pyarrow").array(uni["ticker"].tolist())))
    ts = [t for t in (data._row_to_transcript(r) for r in tbl.to_pylist())
          if t is not None and t.call_date >= pd.Timestamp(a.since) and t.qa_pairs()]
    print(f"{len(ts)} Hugging Face calls since {a.since} for {len({t.ticker for t in ts})} companies")
    fb, lex = nlp.FinBert(), features.load_lm_from_pysentiment2()
    rows = []
    for k, t in enumerate(ts, 1):
        rows.append(feed.score_transcript(t, fb, lex, {"source": "huggingface"}))
        if k % 50 == 0:
            print(f"  scored {k}/{len(ts)}", flush=True)
    feed.add_history(state, pd.DataFrame(rows))
    state.save(a.state)
    print(f"State now holds {len(state.calls)} calls")


def main(argv=None):
    p = argparse.ArgumentParser(prog="earnings_tone")
    sub = p.add_subparsers(required=True)
    s = sub.add_parser("demo"); s.add_argument("--out", default="data/synthetic"); s.set_defaults(f=cmd_demo)
    s = sub.add_parser("fetch-transcripts"); s.add_argument("--tickers-file", required=True)
    s.add_argument("--out", required=True); s.add_argument("--start-year", type=int, default=2018); s.set_defaults(f=cmd_fetch)
    s = sub.add_parser("features"); s.add_argument("--transcripts", required=True); s.add_argument("--out", required=True)
    s.add_argument("--lm-dict"); s.set_defaults(f=cmd_features)
    s = sub.add_parser("prices"); s.add_argument("--features", required=True); s.add_argument("--out", required=True)
    s.set_defaults(f=cmd_prices)
    s = sub.add_parser("study"); s.add_argument("--features", required=True); s.add_argument("--car", required=True)
    s.add_argument("--surprise"); s.add_argument("--out", default="reports"); s.add_argument("--split", default="2023Q1")
    s.set_defaults(f=cmd_study)
    s = sub.add_parser("ticker", help="NLP analysis of every call for one ticker")
    s.add_argument("--ticker", required=True); s.add_argument("--transcripts", required=True)
    s.add_argument("--lm-dict"); s.add_argument("--panel", help="study panel parquet, adds returns and peer ranks")
    s.add_argument("--call", help="focus call date (default: latest)"); s.add_argument("--recent", type=int, default=4)
    s.add_argument("--out", help="output folder (default: reports/<TICKER>)"); s.set_defaults(f=cmd_ticker)
    s = sub.add_parser("nlp", help="FinBERT sentence tone for every call (fb_* columns)")
    s.add_argument("--transcripts", required=True); s.add_argument("--out", required=True)
    s.add_argument("--features", help="features parquet to merge the scores into")
    s.add_argument("--onnx-file", default=nlp.ONNX_FILE); s.set_defaults(f=cmd_nlp)
    for name, fn, h in (("feed-update", cmd_feed_update, "daily live feed run (Alpha Vantage + FinBERT)"),
                        ("feed-history", cmd_feed_history, "one-off: score Hugging Face history for the universe")):
        s = sub.add_parser(name, help=h); s.add_argument("--state", required=True); s.add_argument("--top", type=int, default=100)
        s.set_defaults(f=fn)
        if name == "feed-update":
            s.add_argument("--site-out", required=True); s.add_argument("--budget", type=int, default=25)
        else:
            s.add_argument("--since", default="2023-01-01")
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
