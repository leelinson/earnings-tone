"""Export the API's responses as JSON files for the static site.

Usage: EARNINGS_TONE_DB=../data/earnings_tone.sqlite python export_static.py ../web/data

Writes companies.json, study.json, company/<TICKER>.json and call/<call_id>.json.
Going through the API keeps the site's numbers identical to what the API serves.
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

RUN_ID = "2026-10-27"


def main(out_dir: str) -> None:
    out = Path(out_dir)
    (out / "company").mkdir(parents=True, exist_ok=True)
    (out / "call").mkdir(parents=True, exist_ok=True)
    api = TestClient(app)
    get = lambda path: api.get(path).raise_for_status().json()
    dump = lambda path, obj: path.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))

    companies = get("/companies")
    dump(out / "companies.json", companies)
    run = get(f"/study/runs/{RUN_ID}")
    dump(out / "study.json", {s: get(f"/study/runs/{RUN_ID}?section={s}") for s in run["sections"]})

    n_calls = 0
    for c in companies:
        t = c["ticker"]
        calls = get(f"/companies/{t}/calls")
        dump(out / "company" / f"{t}.json",
             {"company": get(f"/companies/{t}"), "calls": calls, "prices": get(f"/companies/{t}/prices")})
        for call in calls:
            cid = call["call_id"]
            dump(out / "call" / f"{cid}.json",
                 {"call": call, "window": get(f"/calls/{cid}/window"), "qa": get(f"/calls/{cid}/qa")})
            n_calls += 1
    print(f"wrote {len(companies)} companies and {n_calls} calls to {out}")


if __name__ == "__main__":
    main(sys.argv[1])
