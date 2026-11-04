"""Transformer tone scoring with FinBERT, alongside the Loughran-McDonald word counts.

FinBERT (ProsusAI/finbert) is BERT fine-tuned on financial news sentences; it labels each
sentence positive, negative or neutral. Word counts miss context ("not strong", "less of a
headwind"); a sentence model reads it. We run the ONNX export (Xenova/finbert) with
onnxruntime, so there is no PyTorch dependency and CPU scoring in CI is quick.

Features (exec sentences only unless noted, each a call-level mean over sentences):
  fb_{sec}_net        mean of P(positive) - P(negative)
  fb_{sec}_neg_share  share of sentences whose top label is negative
  fb_{sec}_pos_share  share of sentences whose top label is positive
  fb_{sec}_n_sent     sentences scored
where sec is prep (prepared remarks), qa (executive answers) or q (analyst questions).
  fb_tone_gap         fb_prep_net - fb_qa_net (scripted optimism the Q&A does not back up)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from .data import Transcript

MODEL_ID = "Xenova/finbert"
MODEL_REVISION = "8f269abebfdd9009d7d9b5e96af7e5c6bfe50b20"  # pinned so scores are reproducible
ONNX_FILE = "onnx/model.onnx"  # fp32; the int8 file is ~2x faster but misreads negations ("not as weak")
LABELS = ("positive", "negative", "neutral")
MIN_WORDS = 4
MAX_TOKENS = 128

SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")

# A scorer maps sentences to an (n, 3) array of probabilities in LABELS order.
Scorer = Callable[[Sequence[str]], np.ndarray]


def split_sentences(text: str) -> list[str]:
    """Split on sentence ends and drop fragments too short to carry tone ("Thank you.")."""
    out = []
    for s in SENT_RE.split(text.strip()):
        s = s.strip()
        if len(s.split()) >= MIN_WORDS:
            out.append(s)
    return out


class FinBert:
    """FinBERT sentence classifier on onnxruntime. Downloads the model once to the HF cache."""

    def __init__(self, model_id: str = MODEL_ID, onnx_file: str = ONNX_FILE,
                 revision: str = MODEL_REVISION, batch_size: int = 32, threads: int | None = None):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        import json

        cfg = json.loads(Path(hf_hub_download(model_id, "config.json", revision=revision)).read_text())
        id2label = {int(k): v.lower() for k, v in cfg["id2label"].items()}
        self._order = [next(i for i, l in id2label.items() if l == lab) for lab in LABELS]
        self.tok = Tokenizer.from_file(hf_hub_download(model_id, "tokenizer.json", revision=revision))
        self.tok.enable_truncation(MAX_TOKENS)
        self.tok.enable_padding()
        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(hf_hub_download(model_id, onnx_file, revision=revision), opts,
                                         providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self.sess.get_inputs()}
        self.batch_size = batch_size

    def __call__(self, sentences: Sequence[str]) -> np.ndarray:
        if not sentences:
            return np.zeros((0, 3))
        # Sort by length so each batch pads to a similar size, then restore order.
        order = np.argsort([len(s) for s in sentences])
        out = np.zeros((len(sentences), 3))
        for b in range(0, len(order), self.batch_size):
            idx = order[b:b + self.batch_size]
            enc = self.tok.encode_batch([sentences[i] for i in idx])
            feed = {
                "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
                "token_type_ids": np.array([e.type_ids for e in enc], dtype=np.int64),
            }
            logits = self.sess.run(None, {k: v for k, v in feed.items() if k in self._inputs})[0]
            logits = logits - logits.max(axis=1, keepdims=True)
            p = np.exp(logits)
            out[idx] = (p / p.sum(axis=1, keepdims=True))[:, self._order]
        return out


def summarize(probs: np.ndarray, prefix: str) -> dict[str, float]:
    if len(probs) == 0:
        return {f"{prefix}_net": np.nan, f"{prefix}_neg_share": np.nan,
                f"{prefix}_pos_share": np.nan, f"{prefix}_n_sent": 0}
    top = probs.argmax(axis=1)
    return {
        f"{prefix}_net": float((probs[:, 0] - probs[:, 1]).mean()),
        f"{prefix}_neg_share": float((top == 1).mean()),
        f"{prefix}_pos_share": float((top == 0).mean()),
        f"{prefix}_n_sent": int(len(probs)),
    }


def _sections(t: Transcript) -> dict[str, list[str]]:
    return {
        "prep": split_sentences(t.text("prepared", "exec")),
        "qa": split_sentences(t.text("qa", "exec")),
        "q": split_sentences(t.text("qa", "analyst")),
    }


def transcript_scores(t: Transcript, scorer: Scorer, keep_sentences: bool = False) -> dict:
    """Call-level FinBERT features. One scorer call per transcript keeps batches full."""
    secs = _sections(t)
    flat = [s for v in secs.values() for s in v]
    probs = scorer(flat)
    row: dict = {"ticker": t.ticker, "call_date": t.call_date}
    i = 0
    for name, sents in secs.items():
        p = probs[i:i + len(sents)]
        row.update(summarize(p, f"fb_{name}"))
        if keep_sentences and name == "qa":
            row["_qa_sentences"] = list(zip(sents, (p[:, 0] - p[:, 1]).tolist()))
        i += len(sents)
    row["fb_tone_gap"] = row["fb_prep_net"] - row["fb_qa_net"]
    return row


def build_scores(transcripts: Iterable[Transcript], scorer: Scorer | None = None,
                 progress: bool = False) -> pd.DataFrame:
    scorer = scorer or FinBert()
    ts = list(transcripts)
    rows = []
    for k, t in enumerate(ts, 1):
        rows.append(transcript_scores(t, scorer))
        if progress and k % 50 == 0:
            print(f"  scored {k}/{len(ts)} calls", flush=True)
    return pd.DataFrame(rows)


def most_extreme(t: Transcript, scorer: Scorer, n: int = 3) -> dict[str, list[dict]]:
    """The most negative and most positive executive Q&A sentences, for excerpts on the site."""
    sents = split_sentences(t.text("qa", "exec"))
    if not sents:
        return {"negative": [], "positive": []}
    p = scorer(sents)
    net = p[:, 0] - p[:, 1]
    order = np.argsort(net)
    pick = lambda idx: [{"text": sents[i], "score": round(float(net[i]), 3)} for i in idx]
    return {"negative": pick(order[:n]), "positive": pick(order[::-1][:n])}
