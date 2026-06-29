-- ─────────────────────────────────────────
--  CONTENT TABLES  (seeded from JSON, read-only at runtime)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS terms (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT 'physiology'
);

CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id     INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS questions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id             INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    question_text       TEXT NOT NULL,
    answer_definition   TEXT,
    answer_intro        TEXT,
    answer_explanation  TEXT,
    answer_mechanism    TEXT,
    answer_flowchart    TEXT,
    answer_clinical     TEXT,
    answer_high_yield   TEXT,
    answer_viva         TEXT,
    guyton_chapter      TEXT
);

CREATE TABLE IF NOT EXISTS search_index (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,   -- 'term' | 'card' | 'item' | 'question'
    entity_id   INTEGER NOT NULL,
    keyword     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_keyword ON search_index(keyword);

-- ─────────────────────────────────────────
--  USER TABLES  (written by bot at runtime)
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    joined_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    streak      INTEGER NOT NULL DEFAULT 0,
    last_active DATE
);

CREATE TABLE IF NOT EXISTS progress (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(telegram_id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    viewed_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcq_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(telegram_id),
    item_id    INTEGER NOT NULL REFERENCES items(id),
    difficulty TEXT NOT NULL,
    score      INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    played_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(telegram_id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, question_id)
);
