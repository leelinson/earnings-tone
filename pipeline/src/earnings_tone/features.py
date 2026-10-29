"""Tone and evasiveness features for one transcript.

The built-in word lists are short seeds drawn from Loughran-McDonald
categories. For the real study, load the full LM master dictionary with
`load_lm_dictionary` (free download from the Notre Dame SRAF site).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .data import Transcript

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")

SEED_LEXICON: dict[str, set[str]] = {
    "uncertainty": set(
        "approximately uncertain uncertainty unclear unknown unpredictable risk risks "
        "volatile volatility fluctuate fluctuations depend depends depending tentative "
        "variable assume assumption contingent possibly perhaps maybe".split()
    ),
    "negative": set(
        "decline declined declines decrease decreased weak weakness weaker loss losses "
        "headwind headwinds challenge challenges challenging difficult adverse slowdown "
        "pressure pressures shortfall impairment disappointing deteriorate soft softness".split()
    ),
    "positive": set(
        "strong stronger strength growth grew record improve improved improvement gain "
        "gains exceed exceeded outperform momentum robust healthy accelerate accelerated "
        "excellent favorable success successful".split()
    ),
    "weak_modal": set("could might may possibly perhaps appears seems suggest suggests".split()),
}

HEDGE_PHRASES = [
    "too early to tell", "too early to say", "we'll see", "we will see", "hard to say",
    "difficult to predict", "wouldn't want to speculate", "not going to speculate",
    "remains to be seen", "time will tell", "it depends", "kind of", "sort of",
]
NON_ANSWER_PHRASES = [
    "don't break that out", "do not break that out", "don't guide", "do not guide",
    "not going to comment", "won't comment", "can't comment", "cannot comment",
    "not something we disclose", "don't disclose", "not going to get into",
    "take that offline", "not prepared to", "won't get into", "we don't provide",
]


def load_lm_dictionary(path: str | Path) -> dict[str, set[str]]:
    """Load the Loughran-McDonald master dictionary CSV into category word sets."""
    df = pd.read_csv(path)
    df["Word"] = df["Word"].astype(str).str.lower()
    cols = {"uncertainty": "Uncertainty", "negative": "Negative", "positive": "Positive",
            "weak_modal": "Weak_Modal", "litigious": "Litigious"}
    return {k: set(df.loc[df[c] > 0, "Word"]) for k, c in cols.items() if c in df}


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def lexicon_rates(text: str, lexicon: dict[str, set[str]]) -> dict[str, float]:
    toks = tokenize(text)
    n = max(len(toks), 1)
    out = {f"{k}_per1k": 1000 * sum(t in words for t in toks) / n for k, words in lexicon.items()}
    low = text.lower()
    out["hedge_phrases_per1k"] = 1000 * sum(low.count(p) for p in HEDGE_PHRASES) / n
    out["net_tone"] = out.get("positive_per1k", 0) - out.get("negative_per1k", 0)
    out["n_words"] = len(toks)
    return out


def evasiveness(pairs: list[tuple[str, str]]) -> dict[str, float]:
    """Lower question-answer similarity and more non-answer phrases mean more evasive."""
    if not pairs:
        return {"qa_relevance": np.nan, "non_answer_rate": np.nan, "n_questions": 0}
    docs = [q for q, _ in pairs] + [a for _, a in pairs]
    try:
        vec = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit(docs)
        Q, A = vec.transform([q for q, _ in pairs]), vec.transform([a for _, a in pairs])
        sims = np.asarray([cosine_similarity(Q[i], A[i])[0, 0] for i in range(len(pairs))])
        rel = float(sims.mean())
    except ValueError:  # empty vocabulary
        rel = np.nan
    non_ans = np.mean([any(p in a.lower() for p in NON_ANSWER_PHRASES) for _, a in pairs])
    return {"qa_relevance": rel, "non_answer_rate": float(non_ans), "n_questions": len(pairs)}


def transcript_features(t: Transcript, lexicon: dict[str, set[str]] | None = None) -> dict:
    lexicon = lexicon or SEED_LEXICON
    prep = lexicon_rates(t.text("prepared", "exec"), lexicon)
    qa = lexicon_rates(t.text("qa", "exec"), lexicon)
    row = {"ticker": t.ticker, "call_date": t.call_date, "call_after_close": t.call_after_close}
    row.update({f"prep_{k}": v for k, v in prep.items()})
    row.update({f"qa_{k}": v for k, v in qa.items()})
    row.update(evasiveness(t.qa_pairs()))
    row["tone_gap"] = prep["net_tone"] - qa["net_tone"]
    row["qa_hedging"] = qa.get("uncertainty_per1k", 0) + qa.get("weak_modal_per1k", 0) + qa["hedge_phrases_per1k"]
    row.update(t.meta)
    return row


def build_features(transcripts: list[Transcript], lexicon=None) -> pd.DataFrame:
    df = pd.DataFrame([transcript_features(t, lexicon) for t in transcripts])
    df["quarter"] = pd.PeriodIndex(df["call_date"], freq="Q").astype(str)
    return df


def zscore_within(df: pd.DataFrame, cols: list[str], by: str = "quarter") -> pd.DataFrame:
    """Standardize within each quarter so market-wide tone shifts don't drive results."""
    out = df.copy()
    for c in cols:
        g = out.groupby(by)[c]
        out[f"z_{c}"] = (out[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    return out


# Optional: LLM rubric score, which ties in with the LLM cost study.
LLM_EVASION_PROMPT = """You are an equity analyst. Rate how directly the executive answered the
analyst's question on a 1-5 scale (1 = fully direct with specifics, 5 = evaded entirely).
Return only the integer.

Question: {question}

Answer: {answer}
"""
