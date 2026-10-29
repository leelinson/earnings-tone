"""Fallback price fetch: Yahoo chart API on query1 only (yfinance needs fc.yahoo.com, which is blocked).
Writes a wide DataFrame of split/dividend-adjusted closes, same shape as prices.fetch_prices."""
import sys, time, json, urllib.request
import pandas as pd

def one(t, p1=1480550400):  # 2016-12-01
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={int(time.time())}&interval=1d&events=div,split"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    idx = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(r["meta"]["exchangeTimezoneName"]).tz_localize(None).normalize()
    return pd.Series(r["indicators"]["adjclose"][0]["adjclose"], index=idx, name=t, dtype=float)

tickers, out = open(sys.argv[1]).read().split(), sys.argv[2]
cols, fail = [], []
for t in sorted(set(tickers) | {"SPY"}):
    for k in range(3):
        try:
            cols.append(one(t)); break
        except Exception as e:
            if k == 2: fail.append((t, repr(e)[:80]))
            time.sleep(2 ** k)
    time.sleep(0.3)
px = pd.concat(cols, axis=1).sort_index()
px = px[~px.index.duplicated()].dropna(how="all")
px.to_parquet(out)
print(px.shape, px.index.min().date(), px.index.max().date(), "failed:", fail)
print(px.notna().sum().sort_values().head(6).to_dict())
