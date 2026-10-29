"""Panel construction, regressions, quintile portfolios, and the report."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from .features import zscore_within

Z_COLS = ["qa_hedging", "qa_relevance", "non_answer_rate", "tone_gap", "qa_net_tone"]


def build_panel(features: pd.DataFrame, cars: pd.DataFrame, surprise: pd.DataFrame | None = None) -> pd.DataFrame:
    from .surprise import merge_surprise

    p = features.merge(cars, on=["ticker", "call_date"], how="inner")
    if surprise is not None:
        p = merge_surprise(p, surprise)
    if "sue" not in p:
        p["sue"] = 0.0
    p = zscore_within(p, Z_COLS)
    # Evasion: low relevance plus non-answers. Composite adds hedging.
    p["z_evasion"] = (-p["z_qa_relevance"] + p["z_non_answer_rate"]) / 2
    p["z_composite"] = (p["z_qa_hedging"] + p["z_evasion"]) / 2
    p["z_sue"] = (p["sue"] - p["sue"].mean()) / p["sue"].std()
    p["low_sue"] = (p["sue"].abs() <= p["sue"].abs().median()).astype(int)
    p["fe"] = (p["sector"].astype(str) + "_" if "sector" in p else "") + p["quarter"]
    return p


SPECS = {
    "H1_hedging": "car_0_1 ~ z_qa_hedging + z_sue + pre_ret_m20_m1",
    "H2_evasion": "car_0_1 ~ z_evasion + z_sue + pre_ret_m20_m1",
    "H3_tone_gap_drift": "car_2_20 ~ z_tone_gap + z_sue + pre_ret_m20_m1",
    "H4_low_sue_interaction": "car_0_1 ~ z_composite * low_sue + z_sue + pre_ret_m20_m1",
}


def run_spec(panel: pd.DataFrame, formula: str, fe: bool = True):
    f = formula + (" + C(fe)" if fe and panel["fe"].nunique() > 1 else "")
    cols = [c for c in panel.columns if c in f]
    d = panel.dropna(subset=cols)
    groups = pd.factorize(d["ticker"])[0]
    return smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": groups})


def quintile_spread(panel: pd.DataFrame, score: str = "z_composite", ret: str = "car_0_1") -> pd.DataFrame:
    """Each quarter, sort into quintiles on score. Q1 = cleanest, Q5 = most evasive."""
    d = panel.dropna(subset=[score, ret]).copy()
    d["q"] = d.groupby("quarter")[score].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1 if len(s) >= 5 else np.nan
    )
    by_q = d.groupby(["quarter", "q"])[ret].mean().unstack()
    by_q["Q1_minus_Q5"] = by_q[1] - by_q[5]
    return by_q


def summarize_ls(ls: pd.Series) -> dict:
    ls = ls.dropna()
    t = ls.mean() / (ls.std(ddof=1) / np.sqrt(len(ls))) if len(ls) > 1 else np.nan
    return {"mean_bps": 1e4 * ls.mean(), "t_stat": t, "n_quarters": len(ls), "hit_rate": (ls > 0).mean()}


def run_study(panel: pd.DataFrame, out_dir: str | Path, split_quarter: str | None = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results, lines = {}, ["# Earnings Call Tone Study: Results", "",
                          f"Calls: **{len(panel):,}** | Firms: **{panel['ticker'].nunique()}** | "
                          f"Quarters: **{panel['quarter'].nunique()}**", ""]

    lines += ["## Regressions (firm-clustered SE, sector x quarter FE)", "",
              "| Spec | Variable | Coef (bps per 1 SD) | t-stat | N | R2 |", "|---|---|---|---|---|---|"]
    for name, f in SPECS.items():
        r = run_spec(panel, f)
        results[name] = r
        for v in [x for x in r.params.index if x.startswith("z_") or ":" in x]:
            if v == "z_sue" and name != "H1_hedging":
                continue
            lines.append(f"| {name} | `{v}` | {1e4 * r.params[v]:.1f} | {r.tvalues[v]:.2f} | {int(r.nobs)} | {r.rsquared:.3f} |")

    q = quintile_spread(panel)
    q.to_csv(out / "quintiles_by_quarter.csv")
    lines += ["", "## Quintile portfolio (Q1 cleanest minus Q5 most evasive, CAR[0,+1])", ""]
    periods = {"Full sample": q["Q1_minus_Q5"]}
    if split_quarter:
        periods["In sample (< %s)" % split_quarter] = q.loc[q.index < split_quarter, "Q1_minus_Q5"]
        periods["Out of sample (>= %s)" % split_quarter] = q.loc[q.index >= split_quarter, "Q1_minus_Q5"]
    lines += ["| Period | Mean spread (bps) | t-stat | Quarters | Hit rate |", "|---|---|---|---|---|"]
    for k, s in periods.items():
        m = summarize_ls(s)
        results[f"ls_{k}"] = m
        lines.append(f"| {k} | {m['mean_bps']:.1f} | {m['t_stat']:.2f} | {m['n_quarters']} | {m['hit_rate']:.0%} |")

    # Placebo: shuffle scores within quarter. The effect should vanish.
    rng = np.random.default_rng(0)
    plc = panel.copy()
    plc["z_composite"] = plc.groupby("quarter")["z_composite"].transform(lambda s: rng.permutation(s.values))
    pr = run_spec(plc, "car_0_1 ~ z_composite + z_sue + pre_ret_m20_m1")
    results["placebo"] = pr
    lines += ["", "## Placebo (tone shuffled within quarter)", "",
              f"`z_composite` coef: {1e4 * pr.params['z_composite']:.1f} bps, t = {pr.tvalues['z_composite']:.2f} "
              "(should be near zero)", ""]

    _plot(q, panel, out)
    lines += ["![Quintiles](quintile_returns.png)", "", "![Tone over time](tone_over_time.png)", ""]
    (out / "results.md").write_text("\n".join(lines))
    return results


def _plot(q: pd.DataFrame, panel: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3.5))
    means = 1e4 * q[[1, 2, 3, 4, 5]].mean()
    ax.bar([f"Q{i}" for i in means.index], means.values, color="#2b6cb0")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("Mean CAR[0,+1] (bps)")
    ax.set_title("Post-call abnormal return by evasiveness quintile")
    fig.tight_layout(); fig.savefig(out / "quintile_returns.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.5))
    panel.groupby("quarter")[["qa_hedging", "qa_net_tone"]].mean().plot(ax=ax)
    ax.set_title("Average Q&A tone by quarter (raw, per 1k words)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout(); fig.savefig(out / "tone_over_time.png", dpi=150); plt.close(fig)
