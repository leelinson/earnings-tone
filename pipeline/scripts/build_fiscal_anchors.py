"""Anchor each S&P 500 member's fiscal quarter labels to its last Hugging Face call.

Alpha Vantage asks for transcripts by fiscal quarter (NVDA's April 2026 quarter is
2027Q1), but its EARNINGS endpoint gives only period-end and report dates, and fiscal
calendars vary (52/53-week years, Costco's 16-week fourth quarter). The Hugging Face set
labels every call with its fiscal year and quarter, so we record each company's latest
labelled call; the feed then counts quarters forward from it (see alphavantage.parse_earnings).

Usage: python build_fiscal_anchors.py universe/fiscal_anchors.csv
"""
import sys
import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from earnings_tone.universe import load_members

path = hf_hub_download("kurry/sp500_earnings_transcripts", "parquet_files/part-0.parquet", repo_type="dataset")
t = pq.read_table(path, columns=["symbol", "year", "quarter", "date"]).to_pandas()
t["call_date"] = pd.to_datetime(t["date"]).dt.normalize()
t = t[t["symbol"].isin(load_members())].sort_values("call_date")
# Duplicate labels (a company relabelled, or two calls one quarter) make an anchor unreliable.
last = t.groupby("symbol").tail(1)
dup = t.duplicated(["symbol", "year", "quarter"], keep=False) & t.index.isin(last.index)
out = last.loc[~dup, ["symbol", "call_date", "year", "quarter"]].rename(columns={"symbol": "ticker"})
out["fiscal_quarter"] = out["year"].astype(str) + "Q" + out["quarter"].astype(str)
out[["ticker", "call_date", "fiscal_quarter"]].sort_values("ticker").to_csv(sys.argv[1], index=False, date_format="%Y-%m-%d")
print(len(out), "anchors;", int(dup.sum()), "skipped as duplicates")
print(out.set_index("ticker").loc[["NVDA", "AAPL", "MSFT", "COST", "JPM"], ["call_date", "fiscal_quarter"]])
