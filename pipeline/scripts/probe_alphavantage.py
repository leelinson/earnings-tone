"""Check the key and the fiscal quarter labels end to end. Uses 6 requests.

For NVDA (fiscal year ends in January), AAPL (September) and MSFT (June): fetch EARNINGS,
label quarters by counting from the Hugging Face anchor, request the newest reported
quarter's transcript, and check that its opening names that quarter. Prints metadata only.
(The first probe, 2026-11-04, confirmed Alpha Vantage labels transcripts by fiscal quarter:
NVDA 2025Q4 and AAPL 2025Q1 matched the Hugging Face calls with 0.90 and 0.96 word overlap.)
Usage: ALPHAVANTAGE_API_KEY=... python probe_alphavantage.py
"""
import os
import pandas as pd
from earnings_tone import alphavantage as av

c = av.Client(os.environ["ALPHAVANTAGE_API_KEY"], budget=6)
anchors = av.load_anchors()
today = pd.Timestamp.now().normalize()
ok = True
for sym in ("NVDA", "AAPL", "MSFT"):
    e = c.earnings(sym, anchors.get(sym))
    done = e[e["report_date"] < today]
    last = done.iloc[-1]
    print(f"{sym}: anchor {anchors.get(sym)}, labels from {last['label_source']}; newest reported quarters:")
    print(done.tail(3)[["fiscal_period_end", "report_date", "fiscal_quarter"]].to_string(index=False))
    tr = c.transcript(sym, last["fiscal_quarter"])
    st = av.stated_quarter(tr)
    agree = bool(tr) and av.label_agrees(last["fiscal_quarter"], tr)
    ok &= agree
    print(f"  transcript {last['fiscal_quarter']}: {len(tr)} entries, opening names {st}, agrees={agree}")
print("requests used:", c.used)
if not ok:
    raise SystemExit("Label check failed: do not run update or history until fixed")
