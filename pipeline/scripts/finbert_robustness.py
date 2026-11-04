"""Rerun the study's tone tests with FinBERT scores in place of (and next to) word counts.

Usage: python finbert_robustness.py PANEL FINBERT OUT.json
PANEL is the study panel (run_real_study.py output); FINBERT is build_finbert_real.py output,
keyed by the transcript date, which the panel keeps as transcript_date.
Same specification as the main study: sector x quarter fixed effects, firm-clustered errors,
FinBERT measures standardized within quarter, effects in bps per 1 SD.
"""
import json
import sys

import numpy as np
import pandas as pd

from earnings_tone import study
from earnings_tone.features import zscore_within

PANEL, FB, OUT = sys.argv[1:4]
SPLIT = "2023Q1"
panel = pd.read_parquet(PANEL)
fb = pd.read_parquet(FB).rename(columns={"call_date": "transcript_date"})
panel["transcript_date"] = pd.to_datetime(panel["transcript_date"]).astype("datetime64[ns]")
fb["transcript_date"] = pd.to_datetime(fb["transcript_date"]).astype("datetime64[ns]")
fb_cols = [c for c in fb.columns if c.startswith("fb_") and not c.endswith("_n_sent")]
p = panel.merge(fb[["ticker", "transcript_date", *fb_cols]], on=["ticker", "transcript_date"], how="left")
print(f"FinBERT scores matched for {p['fb_qa_net'].notna().sum()} of {len(p)} panel calls")
p = zscore_within(p, fb_cols)
CTRL = " + z_sue + pre_ret_m20_m1"


def row(label, df, f, v, note=""):
    r = study.run_spec(df, f)
    return {"check": label, "variable": v, "coef_bps": round(1e4 * r.params[v], 1), "se_bps": round(1e4 * r.bse[v], 1),
            "t_stat": round(float(r.tvalues[v]), 2), "n": int(r.nobs), "note": note}


rows = [
    row("Dictionary Q&A net tone (main study, for comparison)", p, "car_0_1 ~ z_qa_net_tone" + CTRL, "z_qa_net_tone"),
    row("FinBERT tone in answers", p, "car_0_1 ~ z_fb_qa_net" + CTRL, "z_fb_qa_net"),
    row("FinBERT tone in answers, before 2023", p[p["quarter"] < SPLIT], "car_0_1 ~ z_fb_qa_net" + CTRL, "z_fb_qa_net"),
    row("FinBERT tone in answers, 2023 onward", p[p["quarter"] >= SPLIT], "car_0_1 ~ z_fb_qa_net" + CTRL, "z_fb_qa_net"),
    row("FinBERT share of negative answer sentences", p, "car_0_1 ~ z_fb_qa_neg_share" + CTRL, "z_fb_qa_neg_share"),
    row("FinBERT tone in prepared remarks", p, "car_0_1 ~ z_fb_prep_net" + CTRL, "z_fb_prep_net"),
    row("FinBERT tone of analyst questions", p, "car_0_1 ~ z_fb_q_net" + CTRL, "z_fb_q_net"),
    row("FinBERT tone gap, drift days +2 to +20", p, "car_2_20 ~ z_fb_tone_gap" + CTRL, "z_fb_tone_gap"),
    row("FinBERT tone gap drift, before 2023", p[p["quarter"] < SPLIT], "car_2_20 ~ z_fb_tone_gap" + CTRL, "z_fb_tone_gap"),
    row("FinBERT tone gap drift, 2023 onward", p[p["quarter"] >= SPLIT], "car_2_20 ~ z_fb_tone_gap" + CTRL, "z_fb_tone_gap"),
    row("Dictionary tone gap drift (main study H3)", p, "car_2_20 ~ z_tone_gap" + CTRL, "z_tone_gap"),
    row("Analyst question tone, 2023 onward", p[p["quarter"] >= SPLIT], "car_0_1 ~ z_fb_q_net" + CTRL, "z_fb_q_net"),
    row("Negative answer share, 2023 onward", p[p["quarter"] >= SPLIT], "car_0_1 ~ z_fb_qa_neg_share" + CTRL, "z_fb_qa_neg_share"),
    row("Horse race: FinBERT answers tone", p, "car_0_1 ~ z_fb_qa_net + z_qa_net_tone" + CTRL, "z_fb_qa_net",
        "both tone measures in one regression"),
    row("Horse race: dictionary net tone", p, "car_0_1 ~ z_fb_qa_net + z_qa_net_tone" + CTRL, "z_qa_net_tone",
        "both tone measures in one regression"),
]
corr = p[["fb_qa_net", "qa_net_tone", "fb_prep_net", "prep_net_tone", "fb_tone_gap", "tone_gap"]].corr(method="spearman")
out = {
    "model": "ProsusAI/finbert (ONNX export Xenova/finbert, fp32)",
    "n_matched": int(p["fb_qa_net"].notna().sum()),
    "rows": rows,
    "spearman": {"answers": float(round(corr.loc["fb_qa_net", "qa_net_tone"], 3)),
                 "prepared": float(round(corr.loc["fb_prep_net", "prep_net_tone"], 3)),
                 "tone_gap": float(round(corr.loc["fb_tone_gap", "tone_gap"], 3))},
    "mean_fb_qa_net": round(float(p["fb_qa_net"].mean()), 3),
    "mean_fb_prep_net": round(float(p["fb_prep_net"].mean()), 3),
}
json.dump(out, open(OUT, "w"), indent=1)
for r in rows:
    print(f"{r['check']:<55} {r['coef_bps']:>7} bps  t={r['t_stat']:>5}  n={r['n']}")
print("Spearman:", out["spearman"])
