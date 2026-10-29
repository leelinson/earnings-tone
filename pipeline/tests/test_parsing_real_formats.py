"""Regression tests for transcript layouts seen in kurry/sp500_earnings_transcripts."""
from earnings_tone import data


def label(rows):
    return data.label_turns([data.Turn(s, t) for s, t in rows])


def roles(turns):
    return [(t.speaker, t.section, t.role) for t in turns]


def test_operator_opening_boilerplate_is_not_qa_start():
    turns = label([
        ("Operator", "Welcome. After the speakers' presentation, there will be a question-and-answer session."),
        ("Jane Smith", "Thank you. With me today are our CEO and CFO."),
        ("Tim Cook", "We had a record quarter."),
        ("Operator", "[Operator Instructions] Our first question comes from Erik Woodring with Morgan Stanley."),
        ("Erik Woodring", "What drove gross margin?"),
        ("Tim Cook", "Mix and pricing."),
    ])
    assert roles(turns)[1:3] == [("Jane Smith", "prepared", "exec"), ("Tim Cook", "prepared", "exec")]
    assert roles(turns)[4:] == [("Erik Woodring", "qa", "analyst"), ("Tim Cook", "qa", "exec")]


def test_ir_handoff_sentence_is_not_qa_start():
    turns = label([
        ("Operator", "Good day and welcome."),
        ("Nancy Paxton", "Speaking first is Tim Cook. After that, we'll open the call to questions from analysts."),
        ("Tim Cook", "Revenue grew."),
        ("Luca Maestri", "Margins expanded."),
        ("Operator", "Our first question will come from Wamsi Mohan with Bank of America."),
        ("Wamsi Mohan", "How is China?"),
    ])
    assert [t.section for t in turns] == ["prepared"] * 5 + ["qa"]
    assert turns[3].role == "exec" and turns[5].role == "analyst"


def test_qa_only_exec_and_stand_in_analyst():
    turns = label([
        ("Operator", "Welcome."),
        ("Colette Kress", "Revenue was a record."),
        ("Operator", "Your first question comes from the line of Toshiya Hari from Goldman Sachs. Your line is open."),
        ("Toshiya Hari", "Question on data center?"),
        ("Jensen Huang", "Demand is strong."),
        ("Operator", "Your next question comes from Samik Chatterjee with JPMorgan."),
        ("Joe Cardoso", "This is Joe on for Samik. How is supply?"),
        ("Jensen Huang", "Improving."),
        ("Operator", "I will now turn the call back over to Jensen Huang for closing remarks."),
        ("Jensen Huang", "Thank you all."),
    ])
    r = {t.speaker: t.role for t in turns}
    assert r["Jensen Huang"] == "exec"
    assert r["Toshiya Hari"] == "analyst" and r["Joe Cardoso"] == "analyst"
    t = data.Transcript("NVDA", None, turns)
    assert len(t.qa_pairs()) == 2


def test_ir_moderated_qa():
    turns = label([
        ("Operator", "Welcome."),
        ("Walter Pritchard", "Thanks. Nikesh will start."),
        ("Nikesh Arora", "Great quarter."),
        ("Walter Pritchard", "Let's start Q&A. First up is Gray Powell from BTIG. Go ahead, Gray."),
        ("Gray Powell", "How is SASE?"),
        ("Lee Klarich", "Strong."),
    ])
    r = {t.speaker: t.role for t in turns}
    assert r["Gray Powell"] == "analyst" and r["Lee Klarich"] == "exec"


def test_2018_header_turns_and_firm_suffixes():
    turns = label([
        ("Executives", "Shawn Simmons - NVIDIA Corp. Colette M. Kress - NVIDIA Corp. Jen-Hsun Huang - NVIDIA Corp."),
        ("Analysts", "Vivek Arya - Bank of America Merrill Lynch Mark Lipacis - Jefferies LLC"),
        ("Operator", "Good afternoon."),
        ("Shawn Simmons - NVIDIA Corp.", "Welcome."),
        ("Colette M. Kress - NVIDIA Corp.", "Revenue was strong."),
        ("Operator", "Your first question comes from the line of Vivek Arya with Bank of America."),
        ("Vivek Arya - Bank of America Merrill Lynch", "Data center?"),
        ("Jen-Hsun Huang - NVIDIA Corp.", "Great."),
    ])
    assert [t.speaker for t in turns][:2] == ["Operator", "Shawn Simmons"]
    r = {t.speaker: t.role for t in turns}
    assert r == {"Operator": "operator", "Shawn Simmons": "exec", "Colette M. Kress": "exec",
                 "Vivek Arya": "analyst", "Jen-Hsun Huang": "exec"}


def test_prose_split_at_colon_is_merged_back():
    row = {"ticker": "x", "date": "2024-01-01 17:00", "structured_content": [
        {"speaker": "Operator", "text": "Welcome."},
        {"speaker": "Gary Dickerson", "text": "Results were good."},
        {"speaker": "As a reminder, our strategy has three pillars that we laid out last year", "text": "a, b, c."},
        {"speaker": "Operator", "text": "Our first question comes from C.J. Muse with Evercore."},
        {"speaker": "C.J. Muse", "text": "Question?"},
    ]}
    t = data._row_to_transcript(row)
    assert [x.speaker for x in t.turns] == ["Operator", "Gary Dickerson", "Operator", "C.J. Muse"]
    assert "three pillars" in t.turns[1].text


def test_raw_text_name_line_format():
    raw = """Prepared Remarks:
Operator
Good day, and welcome.
Tim Cook -- Chief Executive Officer
Thanks. Record quarter.
Questions & Answers:
Operator
Our first question comes from Erik Woodring with Morgan Stanley.
Erik Woodring -- Morgan Stanley -- Analyst
What drove margin?
"""
    turns = data.label_turns(data.parse_raw_text(raw))
    assert roles(turns) == [("Operator", "prepared", "operator"), ("Tim Cook", "prepared", "exec"),
                            ("Operator", "prepared", "operator"), ("Erik Woodring", "qa", "analyst")]


def test_raw_text_rejects_numeric_pseudo_speakers():
    turns = data.parse_raw_text("Tim Cook: Three drivers.\nQ3 2024 Revenue: up 12%.")
    assert [t.speaker for t in turns] == ["Tim Cook"]
