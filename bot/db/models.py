"""
Database schema definitions (SQLite).
"""

SCHEMA_SQL = """
-- Bảng lưu token đã mã hoá
CREATE TABLE IF NOT EXISTS saved_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_uid TEXT NOT NULL,
    label       TEXT DEFAULT 'default',
    token_enc   BLOB NOT NULL,
    token_hint  TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_run_at DATETIME,
    next_run_at DATETIME,
    is_active   BOOLEAN DEFAULT 1,
    UNIQUE(discord_uid, label)
);

-- Bảng thống kê nhiệm vụ
CREATE TABLE IF NOT EXISTS quest_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        INTEGER REFERENCES saved_tokens(id),
    discord_uid     TEXT NOT NULL,
    quest_id        TEXT NOT NULL,
    quest_name      TEXT,
    task_type       TEXT,
    completed_at    DATETIME,
    duration_secs   INTEGER,
    run_mode        TEXT
);

-- Bảng global stats
CREATE TABLE IF NOT EXISTS global_stats (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Bảng run sessions (tracking tiến độ real-time)
CREATE TABLE IF NOT EXISTS run_sessions (
    id              TEXT PRIMARY KEY,
    discord_uid     TEXT,
    token_id        INTEGER,
    channel_id      TEXT,
    message_id      TEXT,
    started_at      DATETIME,
    finished_at     DATETIME,
    status          TEXT,
    summary         TEXT
);
"""
