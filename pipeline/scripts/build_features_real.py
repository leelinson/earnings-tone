"""Build tone features for the real sample (patched parser + full LM dictionary)."""
import sys, json, collections
import pandas as pd
from earnings_tone import data, features

TRANSCRIPTS, LM, OUT = sys.argv[1:4]
COMM = {"GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA", "TTWO"}
log = collections.Counter()
ts = []
for line in open(TRANSCRIPTS):
    r = json.loads(line)
    t = data._row_to_transcript(r)
    if t is None:
        log["unparseable"] += 1; continue
    if t.ticker == "WDC" and str(t.call_date.date()) == "2020-08-06":
        log["dropped_wdc_duplicate"] += 1; continue
    if not t.qa_pairs():
        log["dropped_no_qa"] += 1; log[f"no_qa_{t.ticker}"] += 1; continue
    t.meta["sector"] = "Communication Services" if t.ticker in COMM else "Information Technology"
    t.meta["call_hour"] = int(pd.Timestamp(r["date"]).hour)
    ts.append(t)
lex = features.load_lm_dictionary(LM)
f = features.build_features(ts, lex)
f.to_parquet(OUT)
print(dict(log)); print(len(f), "rows ->", OUT)
