# Earnings Call Tone and Post-Earnings Returns

**Question:** Does *how* management talks on an earnings call (hedging, uncertainty, evasive Q&A answers) predict the stock's abnormal return after the call, beyond what the EPS surprise already explains?

This is a classic research setup, written the way a buy-side or sell-side quant team would expect it: a clear hypothesis, proper controls, out-of-sample discipline, and an honest writeup even if the answer is "no".

---

## 1. Hypotheses

| # | Hypothesis | Expected sign |
|---|---|---|
| H1 | More hedging and uncertainty language in the Q&A predicts lower CAR[0,+1], controlling for SUE | negative |
| H2 | Evasive answers (low answer-to-question relevance, non-answer phrases) predict lower CAR[0,+1] | negative |
| H3 | The tone gap (prepared remarks more positive than Q&A) predicts negative drift CAR[+2,+20] | negative |
| H4 | Effects are stronger when the EPS surprise is small (|SUE| low), meaning tone carries more information when the numbers are ambiguous | interaction |

Why Q&A and not prepared remarks? Prepared remarks are scripted and lawyered. Q&A is the only unscripted part, so it is where real information should leak.

## 2. Data

| Data | Source | Notes |
|---|---|---|
| Transcripts | Hugging Face `kurry/sp500_earnings_transcripts` (or any JSONL with `ticker, date, transcript`) | Loader in `data.py`. Also accepts your own CSV/JSONL. |
| Daily prices | `yfinance` (stock + SPY, plus sector ETFs for robustness) | Cached to parquet. |
| EPS surprise | Nasdaq / Zacks / Yahoo earnings history, or WRDS I/B/E/S if you get Stern WRDS access | `surprise.py` takes a CSV of `ticker, date, eps_actual, eps_estimate`. |
| Sector | GICS from the S&P 500 constituents list | For sector-quarter fixed effects. |

**Universe:** S&P 500 tech + communication services, 2018 to present. That's roughly 100 names times 30 quarters, or about 3,000 calls. Expand to the full S&P 500 once the pipeline is stable.

**Ask Stern about WRDS.** I/B/E/S consensus and CRSP returns make the study far more credible than scraped data.

## 3. Pipeline

```
transcripts ─► parse speakers ─► split prepared vs Q&A ─► pair each analyst question with the exec answer
                                                     │
                                                     ▼
                         features: LM uncertainty, hedging, negativity, forward-looking,
                                   evasiveness (Q-A relevance), non-answer phrases,
                                   optional FinBERT sentiment, optional LLM rubric score
                                                     │
prices ─► market-model abnormal returns ─► CAR[0,+1], CAR[+2,+20]
surprise CSV ─► SUE                                  │
                                                     ▼
              panel ─► OLS with sector x quarter FE, firm-clustered SE ─► quintile long-short ─► report
```

### Timing (where most student projects go wrong)
- Calls after the close (most US calls) mean that **day 0 is the next trading day**. `prices.py` handles this with a `call_after_close` flag, defaulting to True for calls with a timestamp at or after 16:00 ET.
- The estimation window for the market model is [-250, -30] trading days, so the event never contaminates the beta.

### Features (`features.py`)
- **Loughran-McDonald word lists** (the finance-specific standard, not general sentiment): uncertainty, negative, positive, weak modal, litigious. A seed list is built in. Download the full master dictionary from the Notre Dame SRAF site and point `--lm-dict` at it for the real run.
- **Hedging:** weak modals plus phrases like "we'll see", "too early to tell", "I wouldn't want to speculate".
- **Evasiveness:** TF-IDF cosine similarity between each analyst question and the executive's answer (low means the answer drifted off topic), plus a count of non-answer phrases ("we don't break that out", "we don't guide to that").
- **Tone gap:** net tone of prepared remarks minus net tone of Q&A.
- **Optional:** FinBERT sentiment (`ProsusAI/finbert`) and an LLM rubric score (1 to 5 evasiveness), which ties into the LLM cost study.

All features are scaled per 1,000 words and standardized within each quarter, so market-wide shifts in tone don't leak into the results.

## 4. Econometrics (`study.py`)

Main specification:

```
CAR[0,+1]_it = a + b1 * QA_Uncertainty_it + b2 * Evasiveness_it + b3 * SUE_it
               + b4 * log(MktCap) + b5 * PreCallRet[-20,-1] + SectorxQuarter FE + e_it
```

- Standard errors are clustered by firm.
- Run the specification separately for CAR[+2,+20] to test drift (H3).
- Add an interaction with a low-|SUE| dummy (H4).
- **Portfolio test:** each quarter, sort into quintiles on the tone score and go long Q1 (cleanest) and short Q5 (most evasive). Report the mean CAR and t-stat.
- **Out of sample:** fit any learned weights on 2018 to 2022, then test on 2023 onward. Never tune on the test period.

## 5. Robustness checks
1. Use sector ETFs instead of SPY as the market benchmark.
2. Drop calls with |SUE| in the top 5% (huge misses dominate everything).
3. Replace the lexicon with FinBERT and check whether the sign holds.
4. Use a placebo: shuffle tone scores across firms within each quarter. The coefficient should vanish.

## 6. Pitfalls to write about honestly
- **Survivorship:** the current S&P 500 list misses delisted firms, so mention it in the writeup.
- **Scraped EPS estimates** are noisier than I/B/E/S.
- **Multiple testing:** with four hypotheses times two windows, report all of them, not just the significant ones.

## 7. Timeline (about 5 weeks part-time)
| Week | Deliverable |
|---|---|
| 1 | Data pulled and cached; parsing validated on 20 hand-checked transcripts |
| 2 | Features done; sanity plots (tone over time, by sector) |
| 3 | Event study and main regressions |
| 4 | Robustness checks and portfolio test |
| 5 | Two-page writeup with charts, polished README, resume bullet |

## 8. Resume bullet template
> Built an NLP event-study pipeline over **3,000+ S&P 500 tech earnings calls**; found that Q&A evasiveness predicted **X bps** lower 2-day abnormal returns beyond EPS surprise (t = Y), with a long-short quintile spread of **Z bps** out of sample.

---

## Running it

```bash
pip install -r requirements.txt
pip install -e .   # the package lives in src/, so install it before running the CLI

# 1) Sanity check: synthetic data with a planted effect. The pipeline should recover it.
python -m earnings_tone.cli demo

# 2) Real run
python -m earnings_tone.cli fetch-transcripts --tickers-file config/tickers_tech.txt --out data/transcripts.jsonl
python -m earnings_tone.cli features --transcripts data/transcripts.jsonl --out data/features.parquet
python -m earnings_tone.cli prices   --features data/features.parquet --out data/car.parquet
python -m earnings_tone.cli study    --features data/features.parquet --car data/car.parquet \
                                     --surprise data/eps_surprise.csv --out reports/
```

Tests: `pytest -q`
