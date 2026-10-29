import numpy as np
import pandas as pd

from earnings_tone import data, features, prices

RAW = """Operator: Welcome to the call.
Jane Doe -- CEO: Revenue grew strongly this quarter.
Operator: We will now begin the question-and-answer session.
Sam Lee -- Big Bank: What drove gross margin?
Jane Doe: Gross margin expanded on pricing.
Operator: Next question.
Amy Wu -- Other Bank: Any color on China?
Jane Doe: We don't break that out.
"""


def test_parse_and_label():
    turns = data.label_turns(data.parse_raw_text(RAW))
    roles = [(t.speaker, t.section, t.role) for t in turns]
    assert roles[1] == ("Jane Doe", "prepared", "exec")
    assert roles[3] == ("Sam Lee", "qa", "analyst")
    assert roles[4] == ("Jane Doe", "qa", "exec")


def test_qa_pairs_and_evasion():
    t = data.Transcript("X", pd.Timestamp("2024-01-01"), data.label_turns(data.parse_raw_text(RAW)))
    pairs = t.qa_pairs()
    assert len(pairs) == 2
    ev = features.evasiveness(pairs)
    assert ev["non_answer_rate"] == 0.5


def test_day0_timing():
    dates = pd.bdate_range("2024-01-01", periods=10)
    call = pd.Timestamp("2024-01-03")
    assert dates[prices.event_day0(dates, call, after_close=False)] == call
    assert dates[prices.event_day0(dates, call, after_close=True)] == pd.Timestamp("2024-01-04")


def test_car_recovers_injected_return():
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2022-01-03", periods=400)
    m = rng.normal(0, 0.01, 400)
    s = 1.2 * m + rng.normal(0, 0.005, 400)
    s[301] += 0.05  # call after close on day 300 -> reaction on day 301
    px = pd.DataFrame({"A": 100 * np.exp(np.cumsum(s)), "SPY": 100 * np.exp(np.cumsum(m))}, index=dates)
    ev = pd.DataFrame({"ticker": ["A"], "call_date": [dates[300]], "call_after_close": [True]})
    car = prices.compute_cars(px, ev).iloc[0]
    assert abs(car["beta"] - 1.2) < 0.1
    assert abs(car["car_0_1"] - 0.05) < 0.02
