"""Command line entry point: python -m earnings_tone.cli <command>."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import data, features, prices, study, surprise, synthetic


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
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
