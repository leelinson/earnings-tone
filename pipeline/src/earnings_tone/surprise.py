"""EPS surprise. Input CSV columns: ticker, date, eps_actual, eps_estimate [, price]."""
from __future__ import annotations

import numpy as np
import pandas as pd


def load_surprise(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df["ticker"] = df["ticker"].str.upper()
    return add_sue(df)


def add_sue(df: pd.DataFrame) -> pd.DataFrame:
    """Price-scaled surprise when price is available, else scaled by |estimate|. Winsorized 1/99."""
    df = df.copy()
    diff = df["eps_actual"] - df["eps_estimate"]
    if "price" in df and df["price"].notna().any():
        sue = diff / df["price"]
    else:
        sue = diff / df["eps_estimate"].abs().clip(lower=0.01)
    lo, hi = sue.quantile([0.01, 0.99])
    df["sue"] = sue.clip(lo, hi)
    df["beat"] = (diff > 0).astype(int)
    return df


def merge_surprise(panel: pd.DataFrame, surprise: pd.DataFrame, tol_days: int = 3) -> pd.DataFrame:
    """Match each call to the surprise reported within +/- tol_days of the call date."""
    s = surprise.rename(columns={"date": "surprise_date"}).sort_values("surprise_date")
    p = panel.sort_values("call_date")
    out = pd.merge_asof(p, s, left_on="call_date", right_on="surprise_date", by="ticker",
                        direction="nearest", tolerance=pd.Timedelta(days=tol_days))
    return out
