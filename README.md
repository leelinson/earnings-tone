# Earnings Tone

Does *how* management talks in the Q&A of an earnings call (hedging, uncertainty, evasive answers) predict the stock's abnormal return after the call, beyond the EPS surprise?

This repo holds the research pipeline and a portfolio web app built on top of it.

## Findings so far

1,735 calls from 64 S&P 500 tech and communication services firms, November 2017 to May 2025. Effects are per one standard deviation, on the two-day abnormal return CAR[0,+1]:

| Signal | Effect | t-stat |
| --- | --- | --- |
| EPS surprise (SUE) | +145 bps | 5.7 |
| Q&A net tone | +45 bps | 2.15 |
| Q&A hedging | -26 bps | -1.50 |
| Evasiveness | +7 bps | 0.27 |

Bottom line: the EPS surprise dominates. Hedging and evasiveness add no reliable signal; Q&A net tone is the one lead worth following up.

## Layout

| Folder | What it holds | Status |
| --- | --- | --- |
| `pipeline/` | `earnings_tone` Python package (parse transcripts, score tone, event study), scripts for the real-data run, tests | Done |
| `db/` | SQLite schema for the web app | Done |
| `api/` | Read-only FastAPI service over the SQLite file built by `pipeline/scripts/build_db.py` | Done (runs locally) |
| `web/` | Static Next.js site: explore a company, results, robustness, glossary | Planned |

## Running the pipeline

```bash
cd pipeline
pip install -r requirements.txt -e .
python -m pytest -q                         # 12 tests
python -m earnings_tone.cli demo            # synthetic end-to-end run, no downloads
```

To build the app's database from the real-data outputs, see the usage line in `pipeline/scripts/build_db.py`; then run the API as described in [api/README.md](api/README.md).

The real-data run and its scripts are described in [pipeline/README.md](pipeline/README.md) and the docstrings in `pipeline/scripts/`.

## Data

No data is committed. Transcripts come from the Hugging Face dataset `kurry/sp500_earnings_transcripts`, prices from Yahoo Finance, and EPS surprise from public Hugging Face datasets, one of which (`sovai/earnings_surprise`) is licensed for academic research only. The web app will show derived values (tone scores, abnormal returns, beat or miss) and short excerpts, not raw licensed data or full transcripts.
