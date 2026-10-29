# Web

Static Next.js site: Explore a company (home, company and call pages) and the project walkthrough. It reads JSON exported from the API at build time, so the built site needs no server and can be hosted for free.

```bash
# 1. build the database (see pipeline/scripts/build_db.py), then export it for the site
cd api && EARNINGS_TONE_DB=../data/earnings_tone.sqlite python export_static.py ../web/data
# 2. build or preview the site
cd ../web && npm install
npm run dev        # http://localhost:3000
npm run build      # static files in out/ (about 1,900 pages)
```

For GitHub Pages under `/earnings-tone`, build with `NEXT_BASE_PATH=/earnings-tone npm run build`.

`web/data/` is not committed. It holds derived values only (tone scores, abnormal returns, beat or miss, Q&A excerpts).
