"""Run the real-data event study and export dashboard datasets.

Usage: python run_real_study.py FEATURES PRICES SURPRISE OUT_DIR
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from earnings_tone import prices as P, study, surprise as S

FEAT, PX, SUR, OUT = sys.argv[1:5]
out = Path(OUT); out.mkdir(parents=True, exist_ok=True)
SPLIT = "2023Q1"

feats = pd.read_parquet(FEAT)
px = pd.read_parquet(PX)
sur = S.load_surprise(SUR)

# Fix event dates. About 10% of transcripts are dated 1 to 3 days after the earnings release
# (for example GOOGL 2018-04-23 is stored as 2018-04-24), which pushes day 0 past the reaction.
# When the EPS source's announcement date is a weekday 1 to 3 days earlier, use it instead.
ann = sur[["ticker", "date", "announce_date"]].rename(columns={"date": "surprise_date"}).sort_values("surprise_date")
f = pd.merge_asof(feats.sort_values("call_date"), ann, left_on="call_date", right_on="surprise_date", by="ticker",
                  direction="nearest", tolerance=pd.Timedelta(days=3))
a_d = pd.to_datetime(f["announce_date"])
lag = (f["call_date"] - a_d).dt.days
fix = lag.between(1, 3) & (a_d.dt.weekday < 5)
f["transcript_date"] = f["call_date"]
f.loc[fix, "call_date"] = a_d[fix]
f["date_fixed"] = fix.astype(int)
print("event dates moved to the EPS announcement date:", int(fix.sum()))
feats = f.drop(columns=["surprise_date", "announce_date"])
cars = P.compute_cars(px, feats)
cars.to_parquet(out / "cars.parquet")
panel = study.build_panel(feats, cars, sur)
panel.to_parquet(out / "panel.parquet")
res = study.run_study(panel, out / "report", split_quarter=SPLIT)

def dump(name, rows):
    if isinstance(rows, pd.DataFrame):
        rows = rows.replace({np.nan: None}).to_dict("records")
    (out / f"{name}.json").write_text(json.dumps(rows, indent=1, default=str))

# ---- sample flow
n_cars = cars[["car_0_1"]].notna().sum().iloc[0]
final = panel.dropna(subset=["car_0_1", "z_composite", "sue", "pre_ret_m20_m1"])
flow = [
    {"step": 1, "stage": "Calls in the transcript file", "calls": 1845},
    {"step": 2, "stage": "After dropping the WDC duplicate and calls with no Q&A", "calls": int(len(feats))},
    {"step": 3, "stage": "With a stock-price reaction we can measure", "calls": int(n_cars)},
    {"step": 4, "stage": "With an EPS surprise as well (final sample)", "calls": int(len(final))},
]
dump("sample_flow", flow)

# ---- regressions
LAB = {"z_qa_hedging": "Hedging in answers", "z_evasion": "Evasiveness", "z_tone_gap": "Tone gap (scripted minus Q&A)",
       "z_composite": "Hedging + evasiveness combined", "z_composite:low_sue": "Extra effect when the surprise is small",
       "z_sue": "EPS surprise (SUE)", "pre_ret_m20_m1": "Stock return in the month before", "low_sue": "Small-surprise call"}
HYP = {"H1_hedging": ("H1", "Hedging lowers the 2-day return"), "H2_evasion": ("H2", "Evasion lowers the 2-day return"),
       "H3_tone_gap_drift": ("H3", "Tone gap predicts drift over the next month"),
       "H4_low_sue_interaction": ("H4", "Tone matters more when the surprise is small")}
WIN = {"H3_tone_gap_drift": "Days +2 to +20"}
sd_pre = panel["pre_ret_m20_m1"].std()
regs = []
for name, r in ((k, res[k]) for k in study.SPECS):
    h, desc = HYP[name]
    for v in r.params.index:
        if v == "Intercept" or v.startswith("C(fe)"):
            continue
        scale = sd_pre if v == "pre_ret_m20_m1" else 1.0  # report the control per 1 SD too
        test = v in {"z_qa_hedging", "z_evasion", "z_tone_gap", "z_composite:low_sue"}
        regs.append({"id": f"{h}:{v}", "hypothesis": h, "question": desc, "variable": v, "label": LAB.get(v, v),
                     "window": WIN.get(name, "Days 0 to +1"), "coef_bps": 1e4 * r.params[v] * scale,
                     "se_bps": 1e4 * r.bse[v] * scale, "t_stat": float(r.tvalues[v]), "p_value": float(r.pvalues[v]),
                     "n": int(r.nobs), "r2": float(r.rsquared), "is_test": test})
dump("regressions", regs)

# ---- quintiles and long-short
q = study.quintile_spread(panel)
periods = {"Full sample": q.index, "In sample": q.index[q.index < SPLIT], "Out of sample": q.index[q.index >= SPLIT]}
qrows, ls = [], []
for p, idx in periods.items():
    for k in range(1, 6):
        qrows.append({"period": p, "quintile": f"Q{k}", "mean_car_bps": 1e4 * q.loc[idx, k].mean()})
    m = study.summarize_ls(q.loc[idx, "Q1_minus_Q5"])
    ls.append({"period": p, "mean_spread_bps": m["mean_bps"], "t_stat": m["t_stat"], "n_quarters": m["n_quarters"],
               "hit_rate": m["hit_rate"], "first_quarter": idx.min(), "last_quarter": idx.max()})
dump("quintiles", qrows); dump("long_short", ls)
dump("spread_by_quarter", [{"quarter": i, "spread_bps": 1e4 * v, "sample": "Out of sample" if i >= SPLIT else "In sample"}
                            for i, v in q["Q1_minus_Q5"].dropna().items()])

# ---- daily CAR path by quintile, days -5..+20
rets = np.log(px).diff(); mkt = rets["SPY"]; dates = rets.index
d = final.copy()
d["q"] = d.groupby("quarter")["z_composite"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
paths = []
for ev in d.itertuples(index=False):
    d0 = dates.get_loc(pd.Timestamp(ev.event_day0))
    if d0 - 5 < 1 or d0 + 20 >= len(dates):
        continue
    lo, hi = d0 + P.EST_WINDOW[0], d0 + P.EST_WINDOW[1]
    est = pd.concat([rets[ev.ticker].iloc[lo:hi], mkt.iloc[lo:hi]], axis=1).dropna()
    beta, alpha = np.polyfit(est.iloc[:, 1], est.iloc[:, 0], 1)
    ar = (rets[ev.ticker] - (alpha + beta * mkt)).iloc[d0 - 5:d0 + 21].fillna(0).values
    paths.append((int(ev.q), np.cumsum(ar) - (np.cumsum(ar)[4])))  # 0 at day -1 close
arr = pd.DataFrame([dict(q=qq, **{str(i - 5): v for i, v in enumerate(p)}) for qq, p in paths])
cp = []
for qq, g in arr.groupby("q"):
    for day in range(-5, 21):
        cp.append({"quintile": f"Q{qq}", "day": day, "car_bps": 1e4 * g[str(day)].mean(), "n_calls": len(g)})
dump("car_path", cp)

# ---- deciles of evasion and of SUE (sanity check)
def bins(col, n=10):
    x = final.dropna(subset=[col]).copy()
    x["b"] = pd.qcut(x[col].rank(method="first"), n, labels=False) + 1
    return x.groupby("b").agg(mean_x=(col, "mean"), mean_car_bps=("car_0_1", lambda s: 1e4 * s.mean()),
                              n_calls=("car_0_1", "size")).reset_index().rename(columns={"b": "decile"})
eb = bins("z_evasion").rename(columns={"mean_x": "mean_z_evasion"}); dump("evasion_bins", eb)
sb = bins("sue").rename(columns={"mean_x": "mean_sue"})
sb["mean_sue_pct_price"] = 100 * sb["mean_sue"]; dump("sue_bins", sb.drop(columns="mean_sue"))

# ---- placebo, 100 shuffles
rng = np.random.default_rng(0); pl = []
for i in range(100):
    x = panel.copy()
    x["z_composite"] = x.groupby("quarter")["z_composite"].transform(lambda s: rng.permutation(s.values))
    r = study.run_spec(x, "car_0_1 ~ z_composite + z_sue + pre_ret_m20_m1")
    pl.append({"shuffle": i + 1, "coef_bps": 1e4 * r.params["z_composite"], "t_stat": float(r.tvalues["z_composite"])})
dump("placebo", pl)
real = study.run_spec(panel, "car_0_1 ~ z_composite + z_sue + pre_ret_m20_m1")

# ---- robustness for the composite on CAR[0,+1]
def rob(label, df, f="car_0_1 ~ z_composite + z_sue + pre_ret_m20_m1", v="z_composite", note=""):
    r = study.run_spec(df, f)
    return {"check": label, "coef_bps": 1e4 * r.params[v], "se_bps": 1e4 * r.bse[v], "t_stat": float(r.tvalues[v]),
            "n": int(r.nobs), "note": note}
cut = panel["sue"].abs().quantile(0.95)
robs = [
    rob("Main result", panel, note="All calls, hedging + evasiveness combined"),
    rob("Drop calls where EPS sources disagree", panel[(panel.actual_disagree != 1) & (panel.estimate_disagree != 1)]),
    rob("Drop the 5% biggest surprises", panel[panel["sue"].abs() <= cut]),
    rob("Tech companies only", panel[panel["sector"] == "Information Technology"]),
    rob("Communication services only", panel[panel["sector"] == "Communication Services"]),
    rob("Before 2023 (in sample)", panel[panel["quarter"] < SPLIT]),
    rob("2023 onward (out of sample)", panel[panel["quarter"] >= SPLIT]),
    rob("Without sector x quarter controls", panel.assign(fe="all")),
    rob("Hedging alone", panel, "car_0_1 ~ z_qa_hedging + z_sue + pre_ret_m20_m1", "z_qa_hedging"),
    rob("Evasiveness alone", panel, "car_0_1 ~ z_evasion + z_sue + pre_ret_m20_m1", "z_evasion"),
    rob("Q&A net tone (positive minus negative words)", panel, "car_0_1 ~ z_qa_net_tone + z_sue + pre_ret_m20_m1", "z_qa_net_tone"),
    rob("Drift: combined score on days +2 to +20", panel, "car_2_20 ~ z_composite + z_sue + pre_ret_m20_m1"),
]
dump("robustness", robs)

# ---- tone over time (raw)
tq = panel.groupby("quarter").agg(qa_hedging=("qa_hedging", "mean"), qa_net_tone=("qa_net_tone", "mean"),
                                  prep_net_tone=("prep_net_tone", "mean"), tone_gap=("tone_gap", "mean"),
                                  qa_relevance=("qa_relevance", "mean"), non_answer_rate=("non_answer_rate", "mean"),
                                  n_calls=("ticker", "size")).reset_index()
dump("tone_by_quarter", tq)

# ---- summary
sue_r = res["H1_hedging"]
summ = [{"calls": int(len(final)), "firms": int(final.ticker.nunique()), "quarters": int(final.quarter.nunique()),
         "first_call": str(final.call_date.min().date()), "last_call": str(final.call_date.max().date()),
         "oos_split": SPLIT, "placebo_mean_t": float(np.mean([p["t_stat"] for p in pl])),
         "placebo_share_sig": float(np.mean([abs(p["t_stat"]) > 1.96 for p in pl])),
         "real_composite_t": float(real.tvalues["z_composite"]), "real_composite_bps": 1e4 * float(real.params["z_composite"]),
         "sue_coef_bps": 1e4 * float(sue_r.params["z_sue"]), "sue_t": float(sue_r.tvalues["z_sue"]),
         "median_qa_pairs": float(final.n_questions.median()), "median_qa_exec_words": float(final.qa_n_words.median()),
         "mean_abs_car_0_1_bps": 1e4 * float(final.car_0_1.abs().mean())}]
dump("summary", summ)
print(json.dumps(summ, indent=1)); print(pd.DataFrame(regs)[["id", "coef_bps", "t_stat", "n"]]); print(pd.DataFrame(ls)); print(pd.DataFrame(robs))
