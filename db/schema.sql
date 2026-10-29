-- SQLite schema for the earnings tone web app. Built by pipeline/scripts/build_db.py.
-- Holds derived values only: no raw EPS estimates and no full transcripts.

CREATE TABLE companies (
    ticker      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sector      TEXT,                 -- 'Information Technology' or 'Communication Services'
    n_calls     INTEGER NOT NULL,
    first_call  TEXT,
    last_call   TEXT
);

CREATE TABLE calls (
    call_id          TEXT PRIMARY KEY, -- '<ticker>_<call_date>'
    ticker           TEXT NOT NULL REFERENCES companies(ticker),
    call_date        TEXT NOT NULL,    -- event date used in the study (after the date fix)
    transcript_date  TEXT NOT NULL,    -- date stored with the transcript
    date_fixed       INTEGER NOT NULL DEFAULT 0,
    call_hour        INTEGER,
    after_close      INTEGER,
    quarter          TEXT,             -- calendar quarter of the call, e.g. '2023Q2'
    reaction_day     TEXT,             -- trading day 0
    n_questions      INTEGER,
    qa_exec_words    INTEGER,
    in_study         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX calls_ticker_date ON calls(ticker, call_date);

CREATE TABLE call_features (
    call_id              TEXT PRIMARY KEY REFERENCES calls(call_id),
    hedging_per1k        REAL,  -- uncertainty + weak modal + hedge phrases, per 1,000 exec Q&A words
    uncertainty_per1k    REAL,
    weak_modal_per1k     REAL,
    hedge_phrases_per1k  REAL,
    net_tone             REAL,  -- positive minus negative per 1,000 exec Q&A words
    prep_net_tone        REAL,
    tone_gap             REAL,  -- prepared remarks net tone minus Q&A net tone
    relevance            REAL,  -- mean question-answer TF-IDF similarity
    non_answer_rate      REAL,
    hedging_pct          REAL,  -- percentile within the calendar quarter, study calls only
    evasion_pct          REAL,
    net_tone_pct         REAL,
    tone_group           INTEGER -- quintile of the combined score within the quarter (1 = cleanest)
);

CREATE TABLE eps (
    call_id       TEXT PRIMARY KEY REFERENCES calls(call_id),
    beat          TEXT,     -- 'Beat', 'Miss' or 'In line'
    surprise_pct  REAL,     -- percentile of the price-scaled surprise within the quarter
    sources_disagree INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE car (
    call_id         TEXT PRIMARY KEY REFERENCES calls(call_id),
    car_0_1         REAL,   -- cumulative abnormal return, days 0 to +1 (fraction)
    car_2_20        REAL,
    pre_ret_m20_m1  REAL,
    beta            REAL
);

CREATE TABLE prices (
    ticker     TEXT NOT NULL,   -- includes SPY
    date       TEXT NOT NULL,
    adj_close  REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE qa_pairs (
    call_id          TEXT NOT NULL REFERENCES calls(call_id),
    pair_no          INTEGER NOT NULL,
    question         TEXT,   -- excerpt, at most 320 characters
    answer           TEXT,   -- excerpt, at most 600 characters
    answer_words     INTEGER,
    hedging_per1k    REAL,
    net_tone         REAL,
    relevance        REAL,
    non_answer       INTEGER,
    PRIMARY KEY (call_id, pair_no)
);

CREATE TABLE study_runs (
    run_id     TEXT PRIMARY KEY,
    run_at     TEXT NOT NULL,
    label      TEXT,
    n_calls    INTEGER,
    results    TEXT NOT NULL    -- JSON object: one key per result file (regressions, quintiles, ...)
);
