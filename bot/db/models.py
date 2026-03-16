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

-- Bảng thống kê nhiệm vụ (NO foreign key on token_id)
CREATE TABLE IF NOT EXISTS quest_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        INTEGER,
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

-- Bảng theo dõi tương tác người dùng (tất cả users đã dùng bot)
CREATE TABLE IF NOT EXISTS user_interactions (
    discord_uid     TEXT PRIMARY KEY,
    first_seen_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    interaction_count INTEGER DEFAULT 1
);

-- Chỉ mục tối ưu hiệu năng
CREATE INDEX IF NOT EXISTS idx_tokens_uid ON saved_tokens(discord_uid);
CREATE INDEX IF NOT EXISTS idx_stats_user ON quest_stats(discord_uid);
CREATE INDEX IF NOT EXISTS idx_stats_type ON quest_stats(task_type);
CREATE INDEX IF NOT EXISTS idx_stats_date ON quest_stats(completed_at);
"""

# Migration to fix quest_stats FK constraint from older schema
MIGRATION_FIX_FK = """
-- Recreate quest_stats without FOREIGN KEY constraint
CREATE TABLE IF NOT EXISTS quest_stats_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id        INTEGER,
    discord_uid     TEXT NOT NULL,
    quest_id        TEXT NOT NULL,
    quest_name      TEXT,
    task_type       TEXT,
    completed_at    DATETIME,
    duration_secs   INTEGER,
    run_mode        TEXT
);
INSERT OR IGNORE INTO quest_stats_new SELECT * FROM quest_stats;
DROP TABLE quest_stats;
ALTER TABLE quest_stats_new RENAME TO quest_stats;
CREATE INDEX IF NOT EXISTS idx_stats_user ON quest_stats(discord_uid);
CREATE INDEX IF NOT EXISTS idx_stats_type ON quest_stats(task_type);
CREATE INDEX IF NOT EXISTS idx_stats_date ON quest_stats(completed_at);
"""

