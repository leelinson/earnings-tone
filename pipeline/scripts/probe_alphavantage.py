"""Check how Alpha Vantage labels transcript quarters (fiscal vs calendar). Uses 5 requests.

For NVDA (fiscal year ends in January) and AAPL (September), asks for the call the
Hugging Face set dates 2025-02-26 / 2025-01-30 under both labels and reports which label
returns the same call (word overlap of the opening remarks). Prints metadata only.
Usage: ALPHAVANTAGE_API_KEY=... python probe_alphavantage.py
"""
import os
import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from earnings_tone import alphavantage as av

c = av.Client(os.environ["ALPHAVANTAGE_API_KEY"], budget=5)
e = c.earnings("NVDA")
print("EARNINGS NVDA rows:", len(e), "latest:", e.tail(2).drop(columns=["ticker"]).to_dict("records"))
path = hf_hub_download("kurry/sp500_earnings_transcripts", "parquet_files/part-0.parquet", repo_type="dataset")
hf = pq.read_table(path, columns=["symbol", "date", "content"], filters=[("year", "==", 2025)]).to_pandas()
words = lambda s: set(str(s).lower().split()[:400])
for sym, date, labels in [("NVDA", "2025-02-26", ["2025Q4", "2024Q4"]), ("AAPL", "2025-01-30", ["2025Q1", "2024Q4"])]:
    ref = hf[(hf.symbol == sym) & (hf.date.str[:10] == date)]
    ref_w = words(ref.content.iloc[0]) if len(ref) else set()
    for q in labels:
        tr = c.transcript(sym, q)
        text = " ".join(x.get("content", "") for x in tr[:6])
        w = words(text)
        overlap = len(w & ref_w) / max(len(w | ref_w), 1)
        print(f"{sym} {q}: {len(tr)} entries, keys={sorted(tr[0]) if tr else []}, "
              f"overlap with HF {date} call = {overlap:.2f}, titles={[x.get('title') for x in tr[:4]]}")
print("requests used:", c.used)
