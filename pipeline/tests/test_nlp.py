import numpy as np
import pandas as pd

from earnings_tone import data, nlp


def fake_scorer(sents):
    """Positive if 'grew', negative if 'declined', else neutral; mimics FinBert's output shape."""
    rows = []
    for s in sents:
        if "grew" in s:
            rows.append([0.9, 0.05, 0.05])
        elif "declined" in s:
            rows.append([0.05, 0.9, 0.05])
        else:
            rows.append([0.1, 0.1, 0.8])
    return np.array(rows).reshape(-1, 3)


def _call():
    raw = ("Operator: Welcome to the call.\n"
           "Jane Doe -- CEO: Revenue grew strongly this quarter. Margins grew as well in every region.\n"
           "Operator: We will now begin the question-and-answer session.\n"
           "Sam Lee -- Big Bank: Why exactly did China sales slow down?\n"
           "Jane Doe: China sales declined on weaker demand. We expect things to stay about the same.\n")
    return data.Transcript("X", pd.Timestamp("2024-01-01"), data.label_turns(data.parse_raw_text(raw)))


def test_split_sentences_drops_fragments():
    assert nlp.split_sentences("Thank you. Revenue grew ten percent this year. Okay.") == [
        "Revenue grew ten percent this year."]


def test_transcript_scores_by_section():
    r = nlp.transcript_scores(_call(), fake_scorer)
    assert r["fb_prep_n_sent"] == 2 and r["fb_qa_n_sent"] == 2 and r["fb_q_n_sent"] == 1
    assert r["fb_prep_net"] > 0.8 and r["fb_prep_pos_share"] == 1.0
    assert r["fb_qa_neg_share"] == 0.5
    assert np.isclose(r["fb_tone_gap"], r["fb_prep_net"] - r["fb_qa_net"])
    assert r["fb_q_net"] == 0.0


def test_empty_sections_are_nan():
    t = data.Transcript("X", pd.Timestamp("2024-01-01"), [])
    r = nlp.transcript_scores(t, fake_scorer)
    assert np.isnan(r["fb_qa_net"]) and r["fb_qa_n_sent"] == 0


def test_most_extreme_orders_sentences():
    ex = nlp.most_extreme(_call(), fake_scorer, n=1)
    assert "declined" in ex["negative"][0]["text"] and ex["negative"][0]["score"] < 0
