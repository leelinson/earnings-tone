"""Export per-company explorer datasets for the dashboard.

Usage: python export_explorer.py PANEL PRICES TRANSCRIPTS LM_DICT OUT_DIR
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from earnings_tone import data, features, prices as P

PANEL, PX, TR, LM, OUT = sys.argv[1:6]
out = Path(OUT); out.mkdir(parents=True, exist_ok=True)
p = pd.read_parquet(PANEL).dropna(subset=["car_0_1"])
p["company_name"] = p.groupby("ticker")["company_name"].transform(lambda s: s.ffill().bfill()).fillna(p["ticker"])
px = pd.read_parquet(PX)

def pct_rank(col):
    return p.groupby("quarter")[col].rank(pct=True)

p["hedging_pct"] = pct_rank("qa_hedging")
p["evasion_pct"] = pct_rank("z_evasion")
p["net_tone_pct"] = pct_rank("qa_net_tone")
p["tone_group"] = p.groupby("quarter")["z_composite"].transform(
    lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1 if len(s) >= 5 else np.nan)
calls = pd.DataFrame({
    "ticker": p.ticker, "company": p.company_name, "call_date": p.call_date.dt.strftime("%Y-%m-%d"),
    "call_hour": p.call_hour, "quarter": p["quarter"],
    "after_close": p.call_after_close.astype(bool), "reaction_day": pd.to_datetime(p.event_day0).dt.strftime("%Y-%m-%d"),
    "eps_actual": p.eps_actual, "eps_estimate": p.eps_estimate, "surprise_pct_price": 100 * p.sue,
    "beat": np.where(p.eps_actual > p.eps_estimate, "Beat", np.where(p.eps_actual < p.eps_estimate, "Miss", "In line")),
    "car_0_1_pct": 100 * p.car_0_1, "car_2_20_pct": 100 * p.car_2_20,
    "hedging_per1k": p.qa_hedging, "hedging_pct": 100 * p.hedging_pct, "evasion_pct": 100 * p.evasion_pct,
    "net_tone": p.qa_net_tone, "net_tone_pct": 100 * p.net_tone_pct, "relevance": p.qa_relevance,
    "tone_group": p.tone_group, "date_fixed": p.date_fixed.astype(int), "n_questions": p.n_questions, "eps_flag": ((p.actual_disagree == 1) | (p.estimate_disagree == 1)).astype(int),
})
calls = calls.sort_values(["ticker", "call_date"])
calls = calls.round({"eps_actual": 2, "eps_estimate": 2, "surprise_pct_price": 3, "car_0_1_pct": 2, "car_2_20_pct": 2,
                     "hedging_per1k": 1, "hedging_pct": 0, "evasion_pct": 0, "net_tone": 1, "net_tone_pct": 0, "relevance": 3})
calls.replace({np.nan: None}).to_json(out / "company_calls.json", orient="records", indent=0)

# weekly closes
wk = px.resample("W-FRI").last().loc["2017-06-01":]
tick = sorted(calls.ticker.unique())
rows = []
for t in tick:
    s = wk[t].dropna()
    rows += [{"ticker": t, "week": d.strftime("%Y-%m-%d"), "close": round(float(v), 2)} for d, v in s.items()]
json.dump(rows, open(out / "company_prices.json", "w"), separators=(",", ":"))

# stock vs market path around each call, days -5..+20, % change from the close before day 0
win = []
dates = px.index
for ev in p.itertuples(index=False):
    d0 = dates.get_loc(pd.Timestamp(ev.event_day0))
    base_s, base_m = px[ev.ticker].iloc[d0 - 1], px["SPY"].iloc[d0 - 1]
    for k in range(-5, 21):
        if d0 + k >= len(dates):
            break
        sv, mv = px[ev.ticker].iloc[d0 + k], px["SPY"].iloc[d0 + k]
        if pd.isna(sv):
            continue
        win.append({"ticker": ev.ticker, "call_date": ev.call_date.strftime("%Y-%m-%d"), "day": k,
                    "stock_pct": round(100 * (sv / base_s - 1), 1), "market_pct": round(100 * (mv / base_m - 1), 1)})
w = pd.DataFrame(win)
json.dump(w.to_dict("records"), open(out / "call_windows.json", "w"), separators=(",", ":"))

# one Q&A exchange per call: the answer with the most hedging language
lex = features.load_lm_dictionary(LM)
keep = {(t, td.strftime("%Y-%m-%d")): cd.strftime("%Y-%m-%d") for t, td, cd in zip(p.ticker, p.transcript_date, p.call_date)}
ex = []
def clip(s, n):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"
for line in open(TR):
    t = data._row_to_transcript(json.loads(line))
    if t is None or (t.ticker, t.call_date.strftime("%Y-%m-%d")) not in keep:
        continue
    best = None
    for q, a in t.qa_pairs():
        r = features.lexicon_rates(a, lex)
        if r["n_words"] < 60:
            continue
        score = r.get("uncertainty_per1k", 0) + r.get("weak_modal_per1k", 0) + r["hedge_phrases_per1k"]
        if best is None or score > best[0]:
            best = (score, q, a)
    if best:
        ex.append({"ticker": t.ticker, "call_date": keep[(t.ticker, t.call_date.strftime("%Y-%m-%d"))], "hedging_per1k": round(best[0], 1),
                   "question": clip(best[1], 320), "answer": clip(best[2], 600)})
json.dump(ex, open(out / "call_excerpts.json", "w"), separators=(",", ":"))
print(len(calls), len(rows), len(w), len(ex))
for f in ["company_calls", "company_prices", "call_windows", "call_excerpts"]:
    print(f, (out / f"{f}.json").stat().st_size)
