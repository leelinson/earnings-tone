"""NLP analysis of every earnings call for one ticker.

For a chosen ticker this scores each call with the study's features, then adds:
  * how each call compares with the firm's own history and with peers that quarter,
  * themes and keywords over time (what is new, rising and fading),
  * what analysts asked about,
  * notable Q&A excerpts (most hedged answer, least on-topic answer, non-answers),
  * how tone lined up with the post-call abnormal return, when a study panel is given.

Writes report.md, charts, calls.csv, answers.csv and analysis.json to one folder.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import data, features

# Words that fill every call and say nothing about its content.
CALL_STOP_WORDS = set(ENGLISH_STOP_WORDS) | set(
    "quarter quarters year years think thinking going really just know like thank thanks question "
    "questions yes yeah okay ok good great lot bit little things thing way look looking said say "
    "talk talked talking mentioned want come comes coming obviously actually maybe sure kind sort "
    "right time terms point today guys mean saw seeing seen continue continued continues "
    "number numbers able did does let make made new expect expected expecting got getting "
    "use used different important probably particularly certainly clearly basically "
    "fiscal million billion percent operator conference call calls analyst analysts "
    "morning afternoon evening hi hey follow-up followup curious taking color help helpful "
    "indiscernible inaudible unintelligible ll ve don didn doesn isn wasn won wouldn couldn".split()
)
TOKEN_PATTERN = r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b"

# Broad themes for large-cap tech and communication services. A call's score is
# mentions per 10,000 words of everything said on the call (operator excluded).
THEMES: dict[str, list[str]] = {
    "AI": [r"\bai\b", r"artificial intelligence", r"generative", r"\bgenai\b", r"\bllms?\b",
           r"machine learning", r"copilot", r"\bgpus?\b", r"accelerated computing"],
    "Cloud": [r"\bcloud\b", r"\bsaas\b", r"subscription", r"\bazure\b", r"\baws\b", r"data cent(?:er|re)s?"],
    "China": [r"\bchina\b", r"\bchinese\b", r"greater china"],
    "Supply chain": [r"supply chain", r"supply constraint", r"shortages?", r"\bcomponents?\b", r"\blogistics\b"],
    "Pricing": [r"\bpricing\b", r"price increases?", r"\basps?\b", r"average selling price"],
    "Margins": [r"\bmargins?\b", r"gross margin", r"operating margin", r"\bprofitability\b"],
    "Capital return": [r"buybacks?", r"repurchases?", r"\bdividends?\b", r"capital return"],
    "Regulation": [r"\bregulat\w*", r"antitrust", r"\bdoj\b", r"\bftc\b", r"european commission", r"\btariffs?\b"],
    "Macro": [r"\bmacro\b", r"macroeconomic", r"\binflation\b", r"\brecession\b", r"interest rates?",
              r"foreign exchange", r"\bfx\b", r"currency"],
    "Guidance": [r"\bguidance\b", r"\boutlook\b", r"\bguide\b", r"\bforecast\b"],
    "Covid": [r"\bcovid\w*", r"pandemic", r"coronavirus"],
}
_THEME_RE = {k: re.compile("|".join(v), re.I) for k, v in THEMES.items()}
MIN_ANSWER_WORDS = 40  # shorter answers make the per-answer rates too noisy to rank


def load_ticker_transcripts(path: str | Path, ticker: str) -> list[data.Transcript]:
    """Parse only this ticker's calls, oldest first. Same parsing as the study."""
    ticker = ticker.upper()
    path = Path(path)
    if path.suffix == ".jsonl":
        rows = []
        with path.open() as fh:
            for line in fh:
                # cheap pre-filter so a 180 MB file isn't fully JSON-decoded
                if f'"{ticker}"' not in line:
                    continue
                r = json.loads(line)
                if str(r.get("ticker") or r.get("symbol") or "").upper() == ticker:
                    rows.append(r)
    else:
        df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)
        col = "ticker" if "ticker" in df else "symbol"
        rows = df[df[col].astype(str).str.upper() == ticker].to_dict("records")
    ts = [t for t in (data._row_to_transcript(r) for r in rows) if t is not None]
    # Same transcript stored twice (one source re-dates a call): keep the first per date.
    seen, out = set(), []
    for t in sorted(ts, key=lambda t: t.call_date):
        if t.call_date not in seen:
            seen.add(t.call_date)
            out.append(t)
    return out


def qa_exchanges(t: data.Transcript) -> list[dict]:
    """Analyst question / executive answer pairs, keeping who asked and who answered."""
    out, cur = [], None
    for turn in t.turns:
        if turn.section != "qa" or turn.role == "operator":
            continue
        if turn.role == "analyst":
            if cur and cur["answer"]:
                out.append(cur)
            cur = {"analyst": turn.speaker, "question": turn.text, "answer": "", "answered_by": []}
        elif turn.role == "exec" and cur is not None:
            cur["answer"] = (cur["answer"] + " " + turn.text).strip()
            if turn.speaker not in cur["answered_by"]:
                cur["answered_by"].append(turn.speaker)
    if cur and cur["answer"]:
        out.append(cur)
    return out


def score_answers(t: data.Transcript, lexicon: dict[str, set[str]]) -> pd.DataFrame:
    """One row per Q&A exchange with the per-answer versions of the call-level features."""
    ex = qa_exchanges(t)
    if not ex:
        return pd.DataFrame()
    qs, ans = [e["question"] for e in ex], [e["answer"] for e in ex]
    try:
        vec = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit(qs + ans)
        Q, A = vec.transform(qs), vec.transform(ans)
        rel = [float(cosine_similarity(Q[i], A[i])[0, 0]) for i in range(len(ex))]
    except ValueError:
        rel = [np.nan] * len(ex)
    rows = []
    for i, e in enumerate(ex):
        r = features.lexicon_rates(e["answer"], lexicon)
        low = e["answer"].lower()
        rows.append({
            "call_date": t.call_date, "n": i + 1, "analyst": e["analyst"],
            "answered_by": ", ".join(e["answered_by"]), "question": e["question"], "answer": e["answer"],
            "answer_words": r["n_words"], "question_words": len(features.tokenize(e["question"])),
            "hedging": r.get("uncertainty_per1k", 0) + r.get("weak_modal_per1k", 0) + r["hedge_phrases_per1k"],
            "net_tone": r["net_tone"], "relevance": rel[i],
            "non_answer": next((p for p in features.NON_ANSWER_PHRASES if p in low), ""),
        })
    return pd.DataFrame(rows)


def _speaker_stats(t: data.Transcript) -> dict:
    qa = [x for x in t.turns if x.section == "qa" and x.role in ("exec", "analyst")]
    words = {"exec": 0, "analyst": 0}
    by_exec: dict[str, int] = {}
    for x in qa:
        n = len(features.tokenize(x.text))
        words[x.role] += n
        if x.role == "exec":
            by_exec[x.speaker] = by_exec.get(x.speaker, 0) + n
    total = max(words["exec"] + words["analyst"], 1)
    top = max(by_exec, key=by_exec.get) if by_exec else ""
    return {
        "n_analysts": len({x.speaker for x in qa if x.role == "analyst"}),
        "exec_share_of_qa_words": words["exec"] / total,
        "top_answerer": top,
        "top_answerer_share": by_exec.get(top, 0) / max(words["exec"], 1),
    }


def _theme_rates(text: str) -> dict[str, float]:
    n = max(len(features.tokenize(text)), 1)
    return {k: 1e4 * len(rx.findall(text)) / n for k, rx in _THEME_RE.items()}


def call_table(transcripts: list[data.Transcript], lexicon: dict[str, set[str]]) -> pd.DataFrame:
    rows = []
    for t in transcripts:
        row = features.transcript_features(t, lexicon)
        row.update(_speaker_stats(t))
        full = "\n".join(x.text for x in t.turns if x.role != "operator")
        row.update({f"theme_{k}": v for k, v in _theme_rates(full).items()})
        rows.append(row)
    df = pd.DataFrame(rows)
    df["quarter"] = pd.PeriodIndex(df["call_date"], freq="Q").astype(str)
    if {"year", "quarter"} <= set(transcripts[0].meta):
        df["fiscal"] = [f"FY{t.meta['year']} Q{t.meta['quarter']}" for t in transcripts]
    else:
        df["fiscal"] = df["quarter"]
    return df


def add_returns_and_peers(calls: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Attach CARs and SUE from the study panel, and each call's percentile among
    all firms' calls that quarter (100 = highest in the quarter)."""
    p = panel.copy()
    p["match_date"] = pd.to_datetime(p["transcript_date"] if "transcript_date" in p else p["call_date"])
    if "transcript_date" in p:
        p["match_date"] = p["match_date"].fillna(pd.to_datetime(p["call_date"]))
    p["peer_quarter"] = pd.PeriodIndex(pd.to_datetime(p["call_date"]), freq="Q").astype(str)
    if "z_evasion" not in p:
        p["z_evasion"] = np.nan
    for c in ["qa_hedging", "qa_net_tone", "qa_relevance", "z_evasion", "tone_gap"]:
        p[f"pct_{c}"] = 100 * p.groupby("peer_quarter")[c].rank(pct=True)
    p["peers_in_quarter"] = p.groupby("peer_quarter")["ticker"].transform("count")
    keep = ["match_date", "car_0_1", "car_2_20", "sue", "surprise_pct", "beat", "z_evasion", "peers_in_quarter",
            "pct_qa_hedging", "pct_qa_net_tone", "pct_qa_relevance", "pct_z_evasion", "pct_tone_gap"]
    keep = [c for c in keep if c in p]
    tick = p[p["ticker"] == calls["ticker"].iloc[0]][keep].rename(columns={"match_date": "call_date"})
    return calls.merge(tick, on="call_date", how="left")


def own_history_z(calls: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Each call vs the firm's earlier calls: (x - mean of prior calls) / SD of prior calls."""
    out = pd.DataFrame(index=calls.index)
    for c in cols:
        prior = calls[c].shift(1).expanding(min_periods=4)
        out[f"own_z_{c}"] = (calls[c] - prior.mean()) / prior.std()
    return out


def _name_tokens(transcripts: list[data.Transcript]) -> set[str]:
    """Speaker and company name words, so "tim" and "luca" don't top the keyword lists."""
    names = {x.speaker for t in transcripts for x in t.turns}
    names |= {str(t.meta.get("company_name", "")) for t in transcripts} | {t.ticker for t in transcripts}
    return {w.lower() for n in names for w in re.findall(r"[A-Za-z]{3,}", n)}


def keyword_analysis(transcripts: list[data.Transcript], recent: int = 4, top: int = 10) -> dict:
    """Distinctive terms per call (TF-IDF across this firm's calls), terms rising or
    fading in the last `recent` calls, and what analysts asked about."""
    docs = ["\n".join(x.text for x in t.turns if x.role != "operator") for t in transcripts]
    qdocs = ["\n".join(x.text for x in t.turns if x.section == "qa" and x.role == "analyst") for t in transcripts]
    dates = [str(t.call_date.date()) for t in transcripts]
    stop = list(CALL_STOP_WORDS | _name_tokens(transcripts))
    n = len(docs)
    res: dict = {"per_call": {}, "rising": [], "fading": [], "analyst_focus_recent": [], "analyst_focus_all": []}
    if n < 2:
        return res
    tf = TfidfVectorizer(stop_words=stop, token_pattern=TOKEN_PATTERN, ngram_range=(1, 2),
                         sublinear_tf=True, min_df=1, max_df=0.85 if n >= 6 else 1.0)
    X = tf.fit_transform(docs)
    vocab = np.array(tf.get_feature_names_out())
    for i, d in enumerate(dates):
        row = X[i].toarray().ravel()
        res["per_call"][d] = [str(vocab[j]) for j in np.argsort(-row)[:top] if row[j] > 0]

    # Rising / fading: rate per 10k words in the recent calls vs the earlier ones.
    if n > recent:
        cv = CountVectorizer(stop_words=stop, token_pattern=TOKEN_PATTERN, ngram_range=(1, 2), min_df=2)
        C = cv.fit_transform(docs).toarray().astype(float)
        words = cv.get_feature_names_out()
        lens = np.array([max(len(features.tokenize(d)), 1) for d in docs], dtype=float)
        early, late = C[:-recent].sum(0), C[-recent:].sum(0)
        r_early, r_late = 1e4 * early / lens[:-recent].sum(), 1e4 * late / lens[-recent:].sum()
        ok = (early + late) >= max(8, n // 2)
        score = np.log((r_late + 0.5) / (r_early + 0.5))
        order = np.argsort(-score)
        fmt = lambda i: {"term": str(words[i]), "recent_per10k": round(float(r_late[i]), 1),
                         "earlier_per10k": round(float(r_early[i]), 1)}
        res["rising"] = [fmt(i) for i in order if ok[i] and score[i] > 0][:top]
        res["fading"] = [fmt(i) for i in order[::-1] if ok[i] and score[i] < 0][:top]

    # Analyst focus: most frequent content terms in analyst questions.
    try:
        qv = CountVectorizer(stop_words=stop, token_pattern=TOKEN_PATTERN, ngram_range=(1, 2), min_df=1)
        Qm = qv.fit_transform(qdocs).toarray()
        qw = qv.get_feature_names_out()
        for key, rows in (("analyst_focus_recent", Qm[-recent:]), ("analyst_focus_all", Qm)):
            tot = rows.sum(0)
            res[key] = [{"term": str(qw[i]), "mentions": int(tot[i])} for i in np.argsort(-tot)[:top] if tot[i] > 0]
    except ValueError:
        pass
    return res


def notable_excerpts(answers: pd.DataFrame, k: int = 3) -> dict[str, pd.DataFrame]:
    """Top answers per lens. An exchange appears under one lens only; sign-offs
    ("Thank you." followed by the replay details) are skipped."""
    a = answers[(answers["answer_words"] >= MIN_ANSWER_WORDS) & (answers["question_words"] >= 8)]
    out, used = {}, set()
    for key, col, asc in [("most_hedged", "hedging", False), ("least_on_topic", "relevance", True),
                          ("most_negative", "net_tone", True)]:
        d = a[~a["n"].isin(used)].sort_values(col, ascending=asc).head(k)
        used |= set(d["n"])
        out[key] = d
    out["non_answers"] = answers[answers["non_answer"] != ""].head(k)
    return out


def returns_link(calls: pd.DataFrame) -> pd.DataFrame:
    """Within-firm Spearman correlations of tone with the post-call abnormal return."""
    rows = []
    for x, label in [("qa_net_tone", "Q&A net tone"), ("qa_hedging", "Q&A hedging"),
                     ("qa_relevance", "Answer relevance"), ("tone_gap", "Tone gap"),
                     ("surprise_pct", "EPS surprise")]:
        for y in ("car_0_1", "car_2_20"):
            d = calls[[x, y]].dropna() if x in calls and y in calls else pd.DataFrame()
            if len(d) >= 6:
                rows.append({"signal": label, "return": y, "n": len(d),
                             "spearman": d[x].rank().corr(d[y].rank())})
    return pd.DataFrame(rows)


def analyze_ticker(transcripts: list[data.Transcript], lexicon: dict[str, set[str]] | None = None,
                   panel: pd.DataFrame | None = None, recent: int = 4) -> dict:
    if not transcripts:
        raise ValueError("no parseable calls for this ticker")
    lexicon = lexicon or features.SEED_LEXICON
    calls = call_table(transcripts, lexicon)
    if panel is not None:
        calls = add_returns_and_peers(calls, panel)
    calls = pd.concat([calls, own_history_z(calls, ["qa_hedging", "qa_net_tone", "qa_relevance", "tone_gap"])], axis=1)
    answers = pd.concat([score_answers(t, lexicon) for t in transcripts], ignore_index=True)
    return {"ticker": transcripts[0].ticker, "calls": calls, "answers": answers,
            "keywords": keyword_analysis(transcripts, recent=recent), "recent": recent,
            "returns_link": returns_link(calls)}


# ---------------------------------------------------------------- report

def _fmt(x, nd=1, pct=False, bps=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    if bps:
        return f"{x * 1e4:+.0f} bps"
    if pct:
        return f"{x:.0f}"
    return f"{x:.{nd}f}"


def _pct(x):
    return "n/a" if x is None or pd.isna(x) else f"{x:+.1%}"


def _clip(s: str, n: int = 320) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + " …"


def _charts(res: dict, out: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    c = res["calls"]
    files = []
    has_car = "car_0_1" in c and c["car_0_1"].notna().any()
    fig, axes = plt.subplots(3 if has_car else 2, 1, figsize=(10, 8.5 if has_car else 6), sharex=True)
    ax = axes[0]
    ax.plot(c["call_date"], c["prep_net_tone"], marker="o", ms=3, label="Prepared remarks")
    ax.plot(c["call_date"], c["qa_net_tone"], marker="o", ms=3, label="Q&A (execs)")
    ax.axhline(0, color="grey", lw=0.6)
    ax.set_ylabel("Net tone\n(pos - neg per 1k)")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(f"{res['ticker']}: tone across {len(c)} earnings calls")
    ax = axes[1]
    ax.plot(c["call_date"], c["qa_hedging"], marker="o", ms=3, color="tab:red", label="Q&A hedging")
    ax.plot(c["call_date"], c["qa_relevance"] * 100, marker="o", ms=3, color="tab:green",
            label="Answer relevance (x100)")
    ax.set_ylabel("Per 1k words /\nrelevance x100")
    ax.legend(frameon=False, fontsize=8)
    if has_car:
        ax = axes[2]
        v = c["car_0_1"] * 100
        ax.bar(c["call_date"], v, width=25, color=np.where(v >= 0, "tab:blue", "tab:orange"))
        ax.axhline(0, color="grey", lw=0.6)
        ax.set_ylabel("CAR[0,+1] %")
    fig.tight_layout()
    fig.savefig(out / "tone_trend.png", dpi=130)
    plt.close(fig)
    files.append("tone_trend.png")

    th = c[[f"theme_{k}" for k in THEMES]].T
    th.index = list(THEMES)
    th = th.loc[th.sum(axis=1) > 0]
    if len(th):
        fig, ax = plt.subplots(figsize=(10, 0.45 * len(th) + 1.4))
        im = ax.imshow(th.values, aspect="auto", cmap="Blues")
        ax.set_yticks(range(len(th)), th.index, fontsize=8)
        step = max(1, len(c) // 12)
        ax.set_xticks(range(0, len(c), step), [str(d.date())[:7] for d in c["call_date"].iloc[::step]],
                      rotation=45, ha="right", fontsize=7)
        fig.colorbar(im, ax=ax, label="mentions per 10k words")
        ax.set_title(f"{res['ticker']}: themes by call")
        fig.tight_layout()
        fig.savefig(out / "themes.png", dpi=130)
        plt.close(fig)
        files.append("themes.png")
    return files


def write_report(res: dict, out: str | Path, focus_date: str | None = None) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    c, a, kw = res["calls"], res["answers"], res["keywords"]
    tk = res["ticker"]
    if focus_date:
        fd = pd.Timestamp(focus_date)
        idx = (c["call_date"] - fd).abs().idxmin()
    else:
        idx = c.index[-1]
    f = c.loc[idx]
    fdate = f["call_date"]
    fa = a[a["call_date"] == fdate] if len(a) else a
    has_ret = "car_0_1" in c
    name = f.get("company_name") or tk

    L = [f"# {tk} earnings call NLP analysis", ""]
    L.append(f"{name.rstrip('.')}. {len(c)} calls from {c['call_date'].min().date()} to {c['call_date'].max().date()}. "
             f"Tone words are Loughran-McDonald categories per 1,000 words of executive speech; "
             f"\"own z\" compares a call with the firm's earlier calls (needs 4 prior calls).")
    L.append("")
    L.append("![Tone trend](tone_trend.png)")
    L.append("")

    # Focus call summary
    L.append(f"## Focus call: {fdate.date()} ({f['fiscal']})")
    L.append("")
    L.append("| Measure | This call | Firm average | Own z | Peer percentile |")
    L.append("| --- | --- | --- | --- | --- |")
    for col, label, pc in [("qa_net_tone", "Q&A net tone", "pct_qa_net_tone"),
                           ("prep_net_tone", "Prepared net tone", None),
                           ("qa_hedging", "Q&A hedging", "pct_qa_hedging"),
                           ("qa_relevance", "Answer relevance", "pct_qa_relevance"),
                           ("tone_gap", "Tone gap (prepared - Q&A)", "pct_tone_gap")]:
        nd = 3 if col == "qa_relevance" else 1
        oz = f.get(f"own_z_{col}", np.nan)
        L.append(f"| {label} | {_fmt(f[col], nd)} | {_fmt(c[col].mean(), nd)} | "
                 f"{_fmt(oz, 2)} | {_fmt(f.get(pc, np.nan), pct=True) if pc else ''} |")
    L.append("")
    extra = [f"{int(f['n_questions'])} Q&A exchanges with {int(f['n_analysts'])} "
             f"analyst{'s' if f['n_analysts'] != 1 else ''}",
             f"executives spoke {f['exec_share_of_qa_words']:.0%} of Q&A words",
             f"{f['top_answerer']} gave {f['top_answerer_share']:.0%} of executive answers"]
    if has_ret and pd.notna(f.get("car_0_1")):
        extra.append(f"CAR[0,+1] {_fmt(f['car_0_1'], bps=True)}, CAR[+2,+20] {_fmt(f.get('car_2_20'), bps=True)}")
    if has_ret and pd.notna(f.get("surprise_pct")):
        extra.append(f"EPS {f['surprise_pct']:+.1%} vs consensus ({'beat' if f.get('beat') == 1 else 'miss or in line'})")
    L.append("; ".join(extra) + ".")
    if has_ret and pd.notna(f.get("peers_in_quarter")):
        L.append(f"Peer percentile ranks this call among {int(f['peers_in_quarter'])} study calls in "
                 f"{f.get('quarter')} (100 = highest).")
    L.append("")
    L.append(f"Distinctive terms: {', '.join(kw['per_call'].get(str(fdate.date()), [])) or 'n/a'}.")
    L.append("")

    # Excerpts
    if len(fa):
        L.append("### Notable Q&A excerpts from this call")
        L.append("")
        ex = notable_excerpts(fa, k=2)
        titles = {"most_hedged": "Most hedged answers", "least_on_topic": "Least on-topic answers",
                  "most_negative": "Most negative answers", "non_answers": "Non-answer phrases"}
        for key, title in titles.items():
            d = ex[key]
            if not len(d):
                continue
            L.append(f"**{title}**")
            L.append("")
            for _, r in d.iterrows():
                stat = {"most_hedged": f"hedging {r['hedging']:.1f} per 1k",
                        "least_on_topic": f"relevance {r['relevance']:.3f}",
                        "most_negative": f"net tone {r['net_tone']:.1f}",
                        "non_answers": f"\"{r['non_answer']}\""}[key]
                L.append(f"- Q ({r['analyst']}): {_clip(r['question'], 220)}")
                L.append(f"  A ({r['answered_by']}, {stat}): {_clip(r['answer'])}")
            L.append("")

    # History table
    L.append("## Every call")
    L.append("")
    head = "| Date | Fiscal | Prep tone | Q&A tone | Hedging | Relevance | Non-answers | Qs |"
    sep = "| --- | --- | --- | --- | --- | --- | --- | --- |"
    if has_ret:
        head += " EPS surprise | CAR[0,+1] | CAR[+2,+20] |"
        sep += " --- | --- | --- |"
    L += [head, sep]
    for _, r in c.iterrows():
        line = (f"| {r['call_date'].date()} | {r['fiscal']} | {_fmt(r['prep_net_tone'])} | {_fmt(r['qa_net_tone'])} | "
                f"{_fmt(r['qa_hedging'])} | {_fmt(r['qa_relevance'], 3)} | {r['non_answer_rate']:.0%} | "
                f"{int(r['n_questions'])} |")
        if has_ret:
            line += f" {_pct(r.get('surprise_pct'))} | {_fmt(r.get('car_0_1'), bps=True)} | {_fmt(r.get('car_2_20'), bps=True)} |"
        L.append(line)
    L.append("")

    # Extremes over history
    L.append("## Standout calls")
    L.append("")
    for col, label in [("qa_net_tone", "Q&A net tone"), ("qa_hedging", "Q&A hedging")]:
        hi, lo = c.loc[c[col].idxmax()], c.loc[c[col].idxmin()]
        L.append(f"- Highest {label}: {hi['call_date'].date()} ({_fmt(hi[col])}); "
                 f"lowest: {lo['call_date'].date()} ({_fmt(lo[col])}).")
    if has_ret and c["car_0_1"].notna().any():
        best, worst = c.loc[c["car_0_1"].idxmax()], c.loc[c["car_0_1"].idxmin()]
        for r, lab in [(best, "Best"), (worst, "Worst")]:
            L.append(f"- {lab} 2-day reaction: {r['call_date'].date()} ({_fmt(r['car_0_1'], bps=True)}), "
                     f"Q&A tone {_fmt(r['qa_net_tone'])}, hedging {_fmt(r['qa_hedging'])}, EPS surprise {_pct(r.get('surprise_pct'))}.")
    L.append("")

    # Themes and keywords
    L.append("## Themes and keywords")
    L.append("")
    if (out / "themes.png").exists():
        L.append("![Themes](themes.png)")
        L.append("")
    recent = res["recent"]
    if kw["rising"]:
        L.append(f"**Rising in the last {recent} calls** (per 10k words, recent vs earlier): " +
                 ", ".join(f"{x['term']} ({x['recent_per10k']} vs {x['earlier_per10k']})" for x in kw["rising"]) + ".")
        L.append("")
        L.append(f"**Fading:** " + ", ".join(f"{x['term']} ({x['recent_per10k']} vs {x['earlier_per10k']})"
                                              for x in kw["fading"]) + ".")
        L.append("")
    if kw["analyst_focus_recent"]:
        L.append(f"**What analysts asked about, last {recent} calls:** " +
                 ", ".join(f"{x['term']} ({x['mentions']})" for x in kw["analyst_focus_recent"]) + ".")
        L.append("")
        L.append("**All calls:** " + ", ".join(f"{x['term']} ({x['mentions']})" for x in kw["analyst_focus_all"]) + ".")
        L.append("")
    L.append("Distinctive terms by call (TF-IDF against this firm's other calls):")
    L.append("")
    for d, terms in list(kw["per_call"].items())[-8:]:
        L.append(f"- {d}: {', '.join(terms)}")
    L.append("")

    # Returns
    rl = res["returns_link"]
    if len(rl):
        L.append("## Tone and the stock's reaction")
        L.append("")
        L.append("Spearman correlation across this firm's calls. With one firm's calls, a correlation "
                 "needs to be about ±0.3 or larger to stand out from noise, and the cross-firm study "
                 "found no reliable tone effect except a modest one for Q&A net tone.")
        L.append("")
        L.append("| Signal | CAR[0,+1] | CAR[+2,+20] | Calls |")
        L.append("| --- | --- | --- | --- |")
        for sig, g in rl.groupby("signal", sort=False):
            v = g.set_index("return")["spearman"]
            L.append(f"| {sig} | {_fmt(v.get('car_0_1', np.nan), 2)} | {_fmt(v.get('car_2_20', np.nan), 2)} | {g['n'].max()} |")
        L.append("")

    L.append("## Method notes")
    L.append("")
    L.append("- Parsing, speaker roles and features are the same code the study uses (`earnings_tone.data`, "
             "`earnings_tone.features`). Hedging = LM uncertainty + weak modal words + hedge phrases per 1k words.")
    L.append("- Answer relevance is TF-IDF cosine similarity between a question and its answer, fit within the call.")
    L.append(f"- Excerpt rankings skip answers under {MIN_ANSWER_WORDS} words. Themes are regex word lists in "
             "`ticker_report.THEMES`.")
    L.append("- Peer percentiles and returns come from the study panel when `--panel` is given.")
    (out / "report.md").write_text("\n".join(L) + "\n")
    return out / "report.md"


def save_outputs(res: dict, out: str | Path, focus_date: str | None = None) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    _charts(res, out)
    res["calls"].to_csv(out / "calls.csv", index=False)
    res["answers"].to_csv(out / "answers.csv", index=False)
    payload = {
        "ticker": res["ticker"],
        "calls": json.loads(res["calls"].to_json(orient="records", date_format="iso")),
        "keywords": res["keywords"],
        "returns_link": res["returns_link"].to_dict("records"),
    }
    (out / "analysis.json").write_text(json.dumps(payload, indent=1, default=str))
    return write_report(res, out, focus_date)
