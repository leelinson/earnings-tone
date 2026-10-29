# API

Read-only FastAPI service over the SQLite database that `pipeline/scripts/build_db.py` builds. It runs locally; nothing is hosted.

```bash
pip install -r requirements.txt
EARNINGS_TONE_DB=../data/earnings_tone.sqlite uvicorn app.main:app --reload
# open http://127.0.0.1:8000/docs
```

| Endpoint | Returns |
| --- | --- |
| `GET /companies` | All companies with call counts and date range |
| `GET /companies/{ticker}` | One company plus summary: beat rate, average hedging percentile, average reaction |
| `GET /companies/{ticker}/calls` | Every call with tone scores, beat or miss, and CAR[0,+1], CAR[+2,+20] |
| `GET /companies/{ticker}/prices?freq=week` | Weekly (or daily) adjusted closes |
| `GET /calls/{call_id}` | One call (`call_id` is `<TICKER>_<YYYY-MM-DD>`) |
| `GET /calls/{call_id}/window` | Stock vs S&P 500 % change, trading days -5 to +20 |
| `GET /calls/{call_id}/qa?sort=hedging` | Q&A exchanges (excerpts) with per-answer scores |
| `GET /study/runs`, `GET /study/runs/{run_id}?section=regressions` | Stored study results |
| `GET /search?q=` | Companies matching a ticker or name |

Tests use a small fixture database built from `db/schema.sql`: `python -m pytest -q`.
