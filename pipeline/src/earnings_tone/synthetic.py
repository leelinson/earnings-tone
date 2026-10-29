"""Synthetic transcripts and prices with a known, planted tone effect.

Used to prove that the pipeline (parsing, timing, CARs, regressions) recovers
an effect that we know exists before running it on real data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

TOPICS = [
    ("gross margin", "gross margin expanded on mix and pricing in the quarter"),
    ("cloud revenue", "cloud revenue grew on new enterprise contracts and higher usage"),
    ("capex", "capex will rise to support data center capacity next year"),
    ("china demand", "china demand improved with channel inventory now normalized"),
    ("buyback", "buyback pace will continue with free cash flow funding repurchases"),
    ("guidance", "guidance assumes steady demand and stable pricing through the year"),
]
EVASIVE_FILLER = [
    "we don't break that out but we feel good about the business overall",
    "it's too early to tell and we'll see how things develop, it really depends",
    "we're not going to comment on that, there's a lot of uncertainty and it could vary",
    "I wouldn't want to speculate, perhaps we can take that offline",
]

TRUE_EFFECT_BPS_PER_SD = -60  # planted: 1 SD more evasive -> -60 bps CAR[0,+1]
SUE_EFFECT_BPS_PER_SD = 250


def _transcript(rng, ticker: str, evas: float) -> str:
    lines = [
        "Operator: Good afternoon and welcome to the earnings call.",
        f"Jane Doe -- Chief Executive Officer: Thanks everyone. Revenue showed strong growth and record demand for {ticker}.",
        "John Roe -- Chief Financial Officer: Gross margin improved and we delivered robust free cash flow.",
        "Operator: We will now begin the question-and-answer session. Our first question comes from Analyst One.",
    ]
    p_evade = 1 / (1 + np.exp(-1.5 * evas))
    for i, (topic, direct) in enumerate(rng.permutation(np.array(TOPICS, dtype=object))[:5]):
        lines.append(f"Analyst {i + 1} -- Bank {i + 1}: Can you talk about {topic} and what drove {topic} this quarter?")
        ans = rng.choice(EVASIVE_FILLER) if rng.random() < p_evade else f"Sure. On {topic}, {direct}."
        lines.append(f"{'Jane Doe' if i % 2 == 0 else 'John Roe'}: {ans}")
        if i < 4:
            lines.append("Operator: Next question.")
    return "\n".join(lines)


def make_synthetic(out_dir: str | Path, n_firms: int = 60, n_quarters: int = 24, seed: int = 7):
    rng = np.random.default_rng(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2017-01-02", periods=300 + 63 * n_quarters + 40)
    tickers = [f"T{i:03d}" for i in range(n_firms)]
    sectors = rng.choice(["Software", "Semis", "Internet"], n_firms)

    mkt = rng.normal(0.0003, 0.01, len(dates))
    betas = rng.uniform(0.7, 1.5, n_firms)
    rets = mkt[:, None] * betas[None, :] + rng.normal(0, 0.015, (len(dates), n_firms))

    rows, surprise = [], []
    firm_evas = rng.normal(0, 0.7, n_firms)  # persistent firm trait
    for q in range(n_quarters):
        base = 300 + 63 * q
        for j, tk in enumerate(tickers):
            d = base + int(rng.integers(0, 20))
            evas = firm_evas[j] + rng.normal(0, 0.7)
            sue = rng.normal(0, 1)
            # call after close on date d -> reaction hits day d+1
            rets[d + 1, j] += 1e-4 * (TRUE_EFFECT_BPS_PER_SD * evas + SUE_EFFECT_BPS_PER_SD * sue)
            rows.append({"ticker": tk, "date": f"{dates[d].date()} 16:30", "sector": sectors[j],
                         "transcript": _transcript(rng, tk, evas)})
            surprise.append({"ticker": tk, "date": dates[d].date(), "eps_estimate": 1.0,
                             "eps_actual": 1.0 + 0.05 * sue})

    with (out / "transcripts.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    px = pd.DataFrame(100 * np.exp(np.cumsum(np.c_[rets, mkt], axis=0)), index=dates, columns=tickers + ["SPY"])
    px.to_parquet(out / "prices.parquet")
    pd.DataFrame(surprise).to_csv(out / "eps_surprise.csv", index=False)
    return out
