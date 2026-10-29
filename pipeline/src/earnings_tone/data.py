"""Load earnings call transcripts and split them into prepared remarks and Q&A.

Transcript sources differ in format, so the loader accepts:
  * a list of {"speaker", "text"} turns (structured datasets), or
  * raw text with "Speaker Name: text" or "Speaker Name -- Title" headers.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd

QA_START_PATTERNS = [
    r"question[- ]and[- ]answer",
    r"q\s*&\s*a",
    r"(first|our first) question",
    r"open (up )?the (call|line|lines) (up )?(for|to) questions",
    r"we will now (begin|take) questions",
]
QA_START_RE = re.compile("|".join(QA_START_PATTERNS), re.I)
# The operator handing the line to a specific analyst. Opening boilerplate
# ("there will be a question-and-answer session") does not match this.
QA_INTRO_RE = re.compile(
    r"(first|next|1st|final|last) question|question (comes|is coming|will come|is) from"
    r"|(will|that) come from|comes from|line of|go ahead with your question|your line is (now )?open"
    r"|(you may|please) (now )?go ahead|ask your question|\bgo (first )?(\w+ \w+ )?to\b",
    re.I,
)
# "Our first question comes from Jane Doe with Big Bank" -> "Jane Doe"
INTRO_NAME_RE = re.compile(
    r"(?:from|of|to)\s+(?:the line of\s+)?(?P<name>[A-Z][\w.'\-]*(?:\s+[A-Z][\w.'\-]*){0,3})"
    r"|(?P<lead>^|\.\s+)(?P<name2>[A-Z][\w.'\-]*(?:\s+[A-Z][\w.'\-]*){1,3})\s+(?:from|with|of|at)\s",
)
# Sentences where the operator names an exec, not an analyst.
CLOSING_RE = re.compile(r"closing|remarks|back (over )?to|over to|conclude|turn the (call|conference|floor)", re.I)
OPERATOR_RE = re.compile(r"^\s*operator\s*$", re.I)
HEADER_SPEAKERS = {
    "executives": "exec", "corporate participants": "exec", "company participants": "exec",
    "analysts": "analyst", "conference call participants": "analyst",
}
SPEAKER_LINE_RE = re.compile(
    r"^(?P<speaker>[A-Z][\w.'\- ]{1,60}?)(\s+--\s+[^:\n]{0,80})?\s*:\s*(?P<text>.*)$"
)
# Motley Fool style: "Jane Doe -- Chief Executive Officer" alone on a line, text below.
SPEAKER_ONLY_RE = re.compile(r"^(?P<speaker>[A-Z][\w.'\- ]{1,60}?)\s+--\s+[^:\n]{1,120}$")
SECTION_HEADER_RE = re.compile(r"^(prepared remarks|questions (&|and) answers|call participants)\s*:?\s*$", re.I)


def _looks_like_name(s: str) -> bool:
    toks = s.split()
    return bool(OPERATOR_RE.match(s)) or (1 <= len(toks) <= 5 and not re.search(r"[\d%$]", s))


def clean_speaker(s: str) -> str:
    """Drop " - Firm" / " -- Title" suffixes: "Mark Lipacis - Jefferies LLC" -> "Mark Lipacis"."""
    return re.split(r"\s+-{1,2}\s+", s.strip(), maxsplit=1)[0].strip()


@dataclass
class Turn:
    speaker: str
    text: str
    section: str = "prepared"  # "prepared" or "qa"
    role: str = "unknown"  # "operator", "exec", "analyst"


@dataclass
class Transcript:
    ticker: str
    call_date: pd.Timestamp
    turns: list[Turn] = field(default_factory=list)
    call_after_close: bool = True
    meta: dict = field(default_factory=dict)

    def text(self, section: str | None = None, role: str | None = None) -> str:
        return "\n".join(
            t.text
            for t in self.turns
            if (section is None or t.section == section) and (role is None or t.role == role)
        )

    def qa_pairs(self) -> list[tuple[str, str]]:
        """Return (analyst question, executive answer) pairs from the Q&A.

        Consecutive exec turns after one analyst turn are joined into one answer.
        """
        pairs: list[tuple[str, str]] = []
        q: str | None = None
        a: list[str] = []
        for t in self.turns:
            if t.section != "qa" or t.role == "operator":
                continue
            if t.role == "analyst":
                if q is not None and a:
                    pairs.append((q, " ".join(a)))
                q, a = t.text, []
            elif t.role == "exec" and q is not None:
                a.append(t.text)
        if q is not None and a:
            pairs.append((q, " ".join(a)))
        return pairs


def parse_raw_text(raw: str) -> list[Turn]:
    """Split raw transcript text into speaker turns."""
    turns: list[Turn] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or SECTION_HEADER_RE.match(line):
            continue
        m = SPEAKER_LINE_RE.match(line)
        if m and (m.group(2) or _looks_like_name(m.group("speaker").strip())):  # "-- Title" marks a speaker
            turns.append(Turn(m.group("speaker").strip(), m.group("text").strip()))
        elif OPERATOR_RE.match(line) or ((m := SPEAKER_ONLY_RE.match(line)) and _looks_like_name(m.group("speaker"))):
            turns.append(Turn(line if OPERATOR_RE.match(line) else m.group("speaker").strip(), ""))
        elif turns:
            turns[-1].text = (turns[-1].text + " " + line).strip()
    return [t for t in turns if t.text]


def _qa_start(turns: list[Turn]) -> int | None:
    """Index of the turn that opens the Q&A, or None.

    Look for an operator turn that opens Q&A or hands the line to an analyst.
    A candidate only counts once an executive has spoken and the next speaker
    is someone new, so opening boilerplate and "after that we'll open the call
    to questions" in the IR intro are skipped.
    """
    def ok(i: int, min_prior: int) -> bool:
        prior = {t.speaker.lower() for t in turns[:i] if t.role != "operator"}
        nxt = next((t for t in turns[i + 1 :] if t.role != "operator"), None)
        return len(prior) >= min_prior and nxt is not None and nxt.speaker.lower() not in prior

    for i, t in enumerate(turns):
        if t.role == "operator" and (QA_INTRO_RE.search(t.text) or QA_START_RE.search(t.text)) and ok(i, 1):
            return i
    for i, t in enumerate(turns):  # exec hands over without an operator
        if (QA_INTRO_RE.search(t.text) or QA_START_RE.search(t.text)) and ok(i, 2):
            return i
    return None


def _sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x]


def _surnames(name: str) -> set[str]:
    toks = [w.strip(".,").lower() for w in name.split()]
    return {toks[-1]} if toks else set()


def label_turns(turns: list[Turn]) -> list[Turn]:
    """Assign section (prepared/qa) and role (operator/exec/analyst) to each turn.

    Roles come from, in order: "Executives"/"Analysts" header turns (older
    transcripts), speaking in prepared remarks (exec), then in the Q&A being
    named by the operator or speaking right after the operator (analyst).
    Anyone else in the Q&A is an exec who joined only for questions.
    """
    header = {}
    for t in turns:
        kind = HEADER_SPEAKERS.get(t.speaker.strip().lower())
        if kind:
            header[kind] = header.get(kind, "") + " " + t.text.lower()
    turns = [t for t in turns if t.speaker.strip().lower() not in HEADER_SPEAKERS]
    for t in turns:
        raw = t.speaker.strip().lower()
        t.speaker = clean_speaker(t.speaker)
        t.role = "operator" if OPERATOR_RE.match(t.speaker) else "unknown"
        if header and t.role != "operator":
            if raw in header.get("analyst", "") or (t.speaker.lower() in header.get("analyst", "")
                                                    and t.speaker.lower() not in header.get("exec", "")):
                t.role = "analyst"
            elif t.speaker.lower() in header.get("exec", ""):
                t.role = "exec"

    qa_idx = _qa_start(turns)
    if qa_idx is None:
        qa_idx = len(turns)

    # Hand-offs to analysts, wherever they appear: some calls have the IR host
    # moderate, or a named operator, or the operator's line folded into an exec turn.
    intro_text = " ".join(
        sent for t in turns[qa_idx:] for sent in _sentences(t.text)
        if QA_INTRO_RE.search(sent) and not CLOSING_RE.search(sent)
    )
    introduced = set()
    for m in INTRO_NAME_RE.finditer(intro_text):
        introduced |= _surnames(m.group("name") or m.group("name2"))

    execs: set[str] = set()
    for i, t in enumerate(turns):
        t.section = "prepared" if i <= qa_idx else "qa"
        if t.role == "unknown" and i <= qa_idx:
            t.role = "exec"
        if t.role == "exec":
            execs.add(t.speaker.lower())
    # An analyst is named by the operator, or is the first to speak after the
    # operator hands over the line (not after "back to X for closing remarks").
    # Execs answer after analysts.
    analysts: set[str] = set()
    prev_operator = True
    for t in turns[qa_idx + 1 :]:
        if t.role == "operator":
            prev_operator = not CLOSING_RE.search(t.text)
            continue
        last = (_sentences(t.text) or [""])[-1]
        name = t.speaker.lower()
        if t.role == "unknown" and name not in execs and (
            "analyst" in name or _surnames(t.speaker) & introduced or prev_operator
        ):
            analysts.add(name)
        prev_operator = bool(QA_INTRO_RE.search(last)) and not CLOSING_RE.search(last)
    for t in turns[qa_idx + 1 :]:
        if t.role == "unknown":
            t.role = "analyst" if t.speaker.lower() in analysts else "exec"
    return turns


def _row_to_transcript(row: dict) -> Transcript | None:
    ticker = row.get("ticker") or row.get("symbol")
    date = row.get("date") or row.get("call_date") or row.get("datetime")
    if not ticker or not date:
        return None
    structured = row.get("structured_content") or row.get("turns")
    if isinstance(structured, str):
        try:
            structured = json.loads(structured)
        except json.JSONDecodeError:
            structured = None
    if structured:
        turns = []
        for s in structured:
            spk, txt = str(s.get("speaker", "")).strip(), str(s.get("text", ""))
            # Some sources split a sentence at its colon, leaving prose as the "speaker".
            if turns and (len(clean_speaker(spk).split()) > 6 or len(clean_speaker(spk)) > 60):
                turns[-1].text = f"{turns[-1].text} {spk}: {txt}".strip()
            else:
                turns.append(Turn(spk, txt))
    else:
        raw = row.get("transcript") or row.get("content") or ""
        turns = parse_raw_text(str(raw))
    if len(turns) < 4:
        return None
    ts = pd.Timestamp(date)
    after_close = bool(row.get("call_after_close", ts.hour >= 16 or ts.hour == 0))
    return Transcript(
        ticker=str(ticker).upper(),
        call_date=ts.normalize(),
        turns=label_turns(turns),
        call_after_close=after_close,
        meta={k: row[k] for k in ("year", "quarter", "company_name", "sector") if k in row},
    )


def load_transcripts(path: str | Path) -> list[Transcript]:
    path = Path(path)
    if path.suffix == ".jsonl":
        rows: Iterable[dict] = (json.loads(l) for l in path.open() if l.strip())
    elif path.suffix in {".csv", ".parquet"}:
        df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)
        rows = df.to_dict("records")
    else:
        raise ValueError(f"Unsupported transcript file: {path}")
    out = [t for r in rows if (t := _row_to_transcript(r)) is not None]
    return out


def fetch_hf_transcripts(
    tickers: list[str], out: str | Path, dataset: str = "kurry/sp500_earnings_transcripts",
    start_year: int = 2018,
) -> int:
    """Download transcripts from Hugging Face and write JSONL. Needs internet."""
    from datasets import load_dataset  # imported lazily

    want = {t.upper() for t in tickers}
    ds = load_dataset(dataset, split="train")
    n = 0
    with Path(out).open("w") as f:
        for r in ds:
            sym = str(r.get("symbol") or r.get("ticker") or "").upper()
            if sym not in want or int(r.get("year", start_year)) < start_year:
                continue
            f.write(json.dumps(r, default=str) + "\n")
            n += 1
    return n
