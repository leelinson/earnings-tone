"""Score the real sample with FinBERT (same call filter as build_features_real.py).

Usage: python build_finbert_real.py TRANSCRIPTS OUT.parquet
Rows are keyed by ticker + transcript call_date; join to the panel on transcript_date.
About 2 to 3 seconds a call on 4 CPU cores.
"""
import sys, json, time
from earnings_tone import data, nlp

TRANSCRIPTS, OUT = sys.argv[1:3]
ts = []
for line in open(TRANSCRIPTS):
    t = data._row_to_transcript(json.loads(line))
    if t is None or not t.qa_pairs():
        continue
    if t.ticker == "WDC" and str(t.call_date.date()) == "2020-08-06":
        continue
    ts.append(t)
t0 = time.time()
df = nlp.build_scores(ts, progress=True)
df.to_parquet(OUT)
print(f"{len(df)} calls scored in {time.time() - t0:.0f}s -> {OUT}")
