"""Build the web app's SQLite database from the pipeline outputs.

Usage: python build_db.py FEATURES PANEL PRICES TRANSCRIPTS LM_DICT RESULTS_DIR OUT_DB

  FEATURES     data/processed/features_real.parquet (one row per call with features)
  PANEL        data/processed/panel.parquet (study panel: features + CARs + surprise, fixed event dates)
  PRICES       data/raw/prices_tech.parquet (wide adjusted closes, includes SPY)
  TRANSCRIPTS  data/raw/transcripts_tech.jsonl
  LM_DICT      data/reference/lm_dictionary_pysentiment2.csv
  RESULTS_DIR  results/real-study-2026-10-26 (JSON outputs of run_real_study.py)
  OUT_DB       e.g. data/earnings_tone.sqlite (overwritten)

Only derived values go in: EPS beat or miss and a surprise percentile instead of raw
estimates, and short Q&A excerpts instead of full transcripts.
"""
import json, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from earnings_tone import data, features

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
STUDY_FILES = ["summary", "sample_flow", "regressions", "robustness", "placebo", "quintiles", "long_short",
               "spread_by_quarter", "car_path", "evasion_bins", "sue_bins", "tone_by_quarter", "project_steps"]


def ymd(s):
    return pd.to_datetime(s).dt.strftime("%Y-%m-%d")


def clip(s, n):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def build_calls(feats, panel):
    """One row per call with features; study calls take the panel's fixed event date."""
    f = feats.copy()
    f["transcript_date"] = ymd(f.call_date)
    p = panel.copy()
    p["transcript_date"] = ymd(p.transcript_date)
    p["study_date"] = ymd(p.call_date)
    p["reaction_day"] = ymd(p.event_day0)
    f = f.merge(p[["ticker", "transcript_date", "study_date", "reaction_day", "date_fixed"]],
                on=["ticker", "transcript_date"], how="left")
    f["call_date"] = f.study_date.fillna(f.transcript_date)
    f["call_id"] = f.ticker + "_" + f.call_date
    f["date_fixed"] = f.date_fixed.fillna(0).astype(int)
    f["in_study"] = f.study_date.notna().astype(int)
    f["company_name"] = f.groupby("ticker")["company_name"].transform(lambda s: s.ffill().bfill()).fillna(f.ticker)
    return f


def study_scores(panel):
    """Within-quarter percentiles and tone groups, as on the dashboard."""
    p = panel.dropna(subset=["car_0_1"]).copy()
    p["call_id"] = p.ticker + "_" + ymd(p.call_date)
    rank = lambda c: 100 * p.groupby("quarter")[c].rank(pct=True)
    p["hedging_pct"], p["evasion_pct"], p["net_tone_pct"] = rank("qa_hedging"), rank("z_evasion"), rank("qa_net_tone")
    p["surprise_pct"] = rank("sue")
    p["tone_group"] = p.groupby("quarter")["z_composite"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1 if len(s) >= 5 else np.nan)
    p["beat"] = np.select([p.eps_actual > p.eps_estimate, p.eps_actual < p.eps_estimate], ["Beat", "Miss"], None)
    p.loc[p.eps_actual.notna() & p.eps_estimate.notna() & p.beat.isna(), "beat"] = "In line"
    p["sources_disagree"] = ((p.actual_disagree == 1) | (p.estimate_disagree == 1)).astype(int)
    return p


def qa_rows(transcripts_path, lex, call_ids):
    """Per-pair scores and excerpts for every call in the database."""
    rows = []
    for line in open(transcripts_path):
        t = data._row_to_transcript(json.loads(line))
        if t is None:
            continue
        cid = call_ids.get((t.ticker, t.call_date.strftime("%Y-%m-%d")))
        if cid is None:
            continue
        pairs = t.qa_pairs()
        if not pairs:
            continue
        try:
            vec = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit([x for qa in pairs for x in qa])
            Q, A = vec.transform([q for q, _ in pairs]), vec.transform([a for _, a in pairs])
            sims = [float(cosine_similarity(Q[i], A[i])[0, 0]) for i in range(len(pairs))]
        except ValueError:  # empty vocabulary
            sims = [None] * len(pairs)
        for i, (q, a) in enumerate(pairs):
            r = features.lexicon_rates(a, lex)
            rows.append({
                "call_id": cid, "pair_no": i + 1, "question": clip(q, 320), "answer": clip(a, 600),
                "answer_words": r["n_words"],
                "hedging_per1k": r.get("uncertainty_per1k", 0) + r.get("weak_modal_per1k", 0) + r["hedge_phrases_per1k"],
                "net_tone": r["net_tone"], "relevance": sims[i],
                "non_answer": int(any(p in a.lower() for p in features.NON_ANSWER_PHRASES)),
            })
    return pd.DataFrame(rows)


def main(feat_path, panel_path, px_path, tr_path, lm_path, results_dir, out_db):
    feats, panel = pd.read_parquet(feat_path), pd.read_parquet(panel_path)
    px = pd.read_parquet(px_path)
    calls = build_calls(feats, panel)
    sc = study_scores(panel)

    out = Path(out_db)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    con = sqlite3.connect(out)
    con.executescript(SCHEMA.read_text())

    def put(table, df):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        df = df[[c for c in cols if c in df.columns]].astype(object).where(df.notna(), None)
        con.executemany(f"INSERT INTO {table} ({','.join(df.columns)}) VALUES ({','.join('?' * df.shape[1])})",
                        df.itertuples(index=False, name=None))
        print(f"{table}: {len(df)} rows")

    comp = calls.groupby("ticker").agg(name=("company_name", "first"), sector=("sector", "first"),
                                       n_calls=("call_id", "size"), first_call=("call_date", "min"),
                                       last_call=("call_date", "max")).reset_index()
    put("companies", comp)
    put("calls", calls.assign(after_close=calls.call_after_close.astype(int), qa_exec_words=calls.qa_n_words))
    cf = calls.rename(columns={"qa_hedging": "hedging_per1k", "qa_uncertainty_per1k": "uncertainty_per1k",
                               "qa_weak_modal_per1k": "weak_modal_per1k", "qa_hedge_phrases_per1k": "hedge_phrases_per1k",
                               "qa_net_tone": "net_tone", "qa_relevance": "relevance"})
    cf = cf.merge(sc[["call_id", "hedging_pct", "evasion_pct", "net_tone_pct", "tone_group"]], on="call_id", how="left")
    put("call_features", cf)
    put("eps", sc.loc[sc.beat.notna(), ["call_id", "beat", "surprise_pct", "sources_disagree"]])
    put("car", sc[["call_id", "car_0_1", "car_2_20", "pre_ret_m20_m1", "beta"]])

    long = px.loc[:, [c for c in px.columns if px[c].notna().any()]].stack().dropna().rename("adj_close").reset_index()
    long.columns = ["date", "ticker", "adj_close"]
    put("prices", long.assign(date=ymd(long.date)))

    lex = features.load_lm_dictionary(lm_path)
    ids = {(t, d): c for t, d, c in zip(calls.ticker, calls.transcript_date, calls.call_id)}
    put("qa_pairs", qa_rows(tr_path, lex, ids))

    res = {n: json.loads((Path(results_dir) / f"{n}.json").read_text())
           for n in STUDY_FILES if (Path(results_dir) / f"{n}.json").exists()}
    n = res.get("summary", [{}])[0].get("calls")
    con.execute("INSERT INTO study_runs VALUES (?,?,?,?,?)",
                ("2026-10-27", "2026-10-27", "Real data, event dates fixed", n, json.dumps(res)))
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:8])
