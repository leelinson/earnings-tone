"""Score the real sample with FinBERT (same call filter as build_features_real.py).

Usage: python build_finbert_real.py TRANSCRIPTS OUT.parquet
Rows are keyed by ticker + transcript call_date; join to the panel on transcript_date.
Slow on CPU (several seconds a call), so it saves a checkpoint every 100 calls next to
OUT and resumes from it if restarted.
"""
import sys, json, time
from pathlib import Path
import pandas as pd
from earnings_tone import data, nlp

TRANSCRIPTS, OUT = sys.argv[1:3]
ckpt = Path(OUT).with_suffix(".partial.parquet")
ts = []
for line in open(TRANSCRIPTS):
    t = data._row_to_transcript(json.loads(line))
    if t is None or not t.qa_pairs():
        continue
    if t.ticker == "WDC" and str(t.call_date.date()) == "2020-08-06":
        continue
    ts.append(t)
done = pd.read_parquet(ckpt) if ckpt.exists() else pd.DataFrame(columns=["ticker", "call_date"])
seen = set(zip(done["ticker"], pd.to_datetime(done["call_date"])))
todo = [t for t in ts if (t.ticker, t.call_date) not in seen]
print(f"{len(ts)} calls, {len(seen)} already scored, {len(todo)} to go", flush=True)
fb, rows, t0 = nlp.FinBert(), [], time.time()
for k, t in enumerate(todo, 1):
    rows.append(nlp.transcript_scores(t, fb))
    if k % 100 == 0 or k == len(todo):
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True) if len(done) else pd.DataFrame(rows)
        done.to_parquet(ckpt)
        rows = []
        print(f"  scored {len(done)}/{len(ts)} calls ({(time.time() - t0) / k:.1f}s a call)", flush=True)
done.to_parquet(OUT)
print(f"{len(done)} calls scored -> {OUT}")
