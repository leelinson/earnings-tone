"""Market-model abnormal returns and CARs around earnings calls."""
from __future__ import annotations

import numpy as np
import pandas as pd

EST_WINDOW = (-250, -30)  # trading days relative to day 0
MIN_EST_OBS = 120
WINDOWS = {"car_0_1": (0, 1), "car_2_20": (2, 20), "pre_ret_m20_m1": (-20, -1)}


def fetch_prices(tickers: list[str], start: str, end: str | None = None, market: str = "SPY") -> pd.DataFrame:
    """Download adjusted closes with yfinance (needs internet). Columns are tickers."""
    import yfinance as yf

    px = yf.download(sorted(set(tickers) | {market}), start=start, end=end,
                     auto_adjust=True, progress=False)["Close"]
    return px.dropna(how="all")


def fetch_prices_yahoo(tickers: list[str], start: str = "2016-12-01", market: str = "SPY",
                       pause: float = 0.3) -> pd.DataFrame:
    """Adjusted closes from Yahoo's chart API (query1 only; yfinance also needs fc.yahoo.com).

    Same wide shape as fetch_prices. Tickers that fail three times are left out.
    """
    import json
    import time
    import urllib.request

    p1, p2 = int(pd.Timestamp(start).timestamp()), int(time.time())
    cols = []
    for t in sorted(set(tickers) | {market}):
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{t.replace('.', '-')}"
               f"?period1={p1}&period2={p2}&interval=1d&events=div,split")
        for k in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                r = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
                idx = (pd.to_datetime(r["timestamp"], unit="s", utc=True)
                       .tz_convert(r["meta"]["exchangeTimezoneName"]).tz_localize(None).normalize())
                cols.append(pd.Series(r["indicators"]["adjclose"][0]["adjclose"], index=idx, name=t, dtype=float))
                break
            except Exception:
                time.sleep(2 ** k)
        time.sleep(pause)
    px = pd.concat(cols, axis=1).sort_index()
    return px[~px.index.duplicated(keep="last")].dropna(how="all")


def event_day0(dates: pd.DatetimeIndex, call_date: pd.Timestamp, after_close: bool) -> int | None:
    """Index of day 0: the call date if it was during market hours, else the next trading day."""
    pos = dates.searchsorted(call_date, side="right" if after_close else "left")
    return int(pos) if pos < len(dates) else None


def compute_cars(prices: pd.DataFrame, events: pd.DataFrame, market: str = "SPY") -> pd.DataFrame:
    """events needs ticker, call_date, call_after_close. Returns one row per event with CARs."""
    rets = np.log(prices).diff()
    dates = rets.index
    mkt = rets[market]
    rows = []
    for ev in events.itertuples(index=False):
        if ev.ticker not in rets:
            continue
        d0 = event_day0(dates, pd.Timestamp(ev.call_date), bool(ev.call_after_close))
        if d0 is None or d0 + EST_WINDOW[0] < 1:
            continue
        lo, hi = d0 + EST_WINDOW[0], d0 + EST_WINDOW[1]
        est = pd.concat([rets[ev.ticker].iloc[lo:hi], mkt.iloc[lo:hi]], axis=1).dropna()
        if len(est) < MIN_EST_OBS:
            continue
        beta, alpha = np.polyfit(est.iloc[:, 1], est.iloc[:, 0], 1)
        resid_sd = float(np.std(est.iloc[:, 0] - (alpha + beta * est.iloc[:, 1]), ddof=2))
        ar = rets[ev.ticker] - (alpha + beta * mkt)
        row = {"ticker": ev.ticker, "call_date": pd.Timestamp(ev.call_date),
               "event_day0": dates[d0], "beta": beta, "resid_sd": resid_sd}
        for name, (a, b) in WINDOWS.items():
            seg = ar.iloc[d0 + a : d0 + b + 1]
            row[name] = float(seg.sum()) if len(seg) == b - a + 1 and seg.notna().all() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
