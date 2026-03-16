"""
Async SQLite database handler.
"""

import aiosqlite
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from bot.db.models import SCHEMA_SQL, MIGRATION_FIX_FK


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        """Initialize connection and create tables."""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = await aiosqlite.connect(str(path))
        conn.row_factory = aiosqlite.Row
        self._db = conn
        
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")

        for statement in SCHEMA_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(stmt)
        await conn.commit()

        # Run migrations
        await self._run_migrations()

    async def _run_migrations(self):
        """Run database migrations if needed."""
        conn = self._db
        if not conn: return
        # Check if quest_stats has FK constraint (old schema)
        try:
            assert conn is not None
            cur = await conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='quest_stats'"
            )
            row = await cur.fetchone()
            if row and "REFERENCES" in (row[0] or ""):
                await conn.execute("PRAGMA foreign_keys=OFF")
                for statement in MIGRATION_FIX_FK.strip().split(";"):
                    stmt = statement.strip()
                    if stmt:
                        await conn.execute(stmt)
                await conn.commit()
                await conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass

    async def close(self):
        conn = self._db
        if conn:
            await conn.close()
            self._db = None

    # ── Token CRUD ───────────────────────────────────────────────────────────

    async def save_token(
        self,
        discord_uid: str,
        label: str,
        token_enc: bytes,
        token_hint: str,
        next_run_at: Optional[datetime] = None,
    ) -> int:
        """Save an encrypted token. Returns the row id."""
        conn = self._db
        if not conn: return 0
        if next_run_at is None:
            from bot.config import AUTO_RUN_INTERVAL_DAYS
            next_run_at = datetime.now(timezone.utc) + timedelta(days=AUTO_RUN_INTERVAL_DAYS)

        cur = await conn.execute(
            """
            INSERT INTO saved_tokens (discord_uid, label, token_enc, token_hint, next_run_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (discord_uid, label, token_enc, token_hint, next_run_at.isoformat()),
        )
        await conn.commit()
        return cur.lastrowid

    async def get_tokens(self, discord_uid: str) -> list[dict]:
        """Get all tokens for a user."""
        conn = self._db
        if not conn: return []
        cur = await conn.execute(
            "SELECT * FROM saved_tokens WHERE discord_uid = ? ORDER BY created_at",
            (discord_uid,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_token_by_label(self, discord_uid: str, label: str) -> Optional[dict]:
        conn = self._db
        if not conn: return None
        cur = await conn.execute(
            "SELECT * FROM saved_tokens WHERE discord_uid = ? AND label = ?",
            (discord_uid, label),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_token_by_id(self, token_id: int) -> Optional[dict]:
        conn = self._db
        if not conn: return None
        cur = await conn.execute(
            "SELECT * FROM saved_tokens WHERE id = ?",
            (token_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def remove_token(self, discord_uid: str, label: str) -> bool:
        conn = self._db
        if not conn: return False
        cur = await conn.execute(
            "DELETE FROM saved_tokens WHERE discord_uid = ? AND label = ?",
            (discord_uid, label),
        )
        await conn.commit()
        return cur.rowcount > 0

    async def rename_token(self, discord_uid: str, old_label: str, new_label: str) -> bool:
        conn = self._db
        if not conn: return False
        cur = await conn.execute(
            "UPDATE saved_tokens SET label = ? WHERE discord_uid = ? AND label = ?",
            (new_label, discord_uid, old_label),
        )
        await conn.commit()
        return cur.rowcount > 0

    async def set_token_active(self, token_id: int, active: bool):
        conn = self._db
        if not conn: return
        await conn.execute(
            "UPDATE saved_tokens SET is_active = ? WHERE id = ?",
            (1 if active else 0, token_id),
        )
        await conn.commit()

    async def update_run_times(self, token_id: int, last_run: datetime, next_run: datetime):
        conn = self._db
        if not conn: return
        await conn.execute(
            "UPDATE saved_tokens SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (last_run.isoformat(), next_run.isoformat(), token_id),
        )
        await conn.commit()

    async def get_due_tokens(self) -> list[dict]:
        """Get tokens that are due for auto-run."""
        conn = self._db
        if not conn: return []
        now = datetime.now(timezone.utc).isoformat()
        cur = await conn.execute(
            "SELECT * FROM saved_tokens WHERE next_run_at <= ? AND is_active = 1",
            (now,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_all_active_tokens(self) -> list[dict]:
        """Get all active tokens (for startup auto-run)."""
        conn = self._db
        if not conn: return []
        cur = await conn.execute(
            "SELECT * FROM saved_tokens WHERE is_active = 1"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    # ── Quest Stats ──────────────────────────────────────────────────────────

    async def save_quest_stat(
        self,
        token_id: Optional[int],
        discord_uid: str,
        quest_id: str,
        quest_name: str,
        task_type: str,
        duration_secs: int,
        run_mode: str = "once",
    ):
        conn = self._db
        if not conn: return
        await conn.execute(
            """
            INSERT INTO quest_stats (token_id, discord_uid, quest_id, quest_name,
                                     task_type, completed_at, duration_secs, run_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                discord_uid,
                quest_id,
                quest_name,
                task_type,
                datetime.now(timezone.utc).isoformat(),
                duration_secs,
                run_mode,
            ),
        )
        await conn.commit()

    async def get_user_stats(self, discord_uid: str) -> dict:
        conn = self._db
        if not conn: return {"total": 0, "total_time": 0}
        cur = await conn.execute(
            "SELECT COUNT(*) as total, SUM(duration_secs) as total_time "
            "FROM quest_stats WHERE discord_uid = ?",
            (discord_uid,),
        )
        row = await cur.fetchone()
        return dict(row) if row else {"total": 0, "total_time": 0}

    # ── Global Stats ─────────────────────────────────────────────────────────

    async def get_global_stat(self, key: str) -> Optional[str]:
        conn = self._db
        if not conn: return None
        cur = await conn.execute(
            "SELECT value FROM global_stats WHERE key = ?", (key,)
        )
        row = await cur.fetchone()
        return row["value"] if row else None

    async def set_global_stat(self, key: str, value: str):
        conn = self._db
        if not conn: return
        await conn.execute(
            "INSERT OR REPLACE INTO global_stats (key, value) VALUES (?, ?)",
            (key, value),
        )
        await conn.commit()

    async def increment_global_stat(self, key: str, amount: int = 1):
        cur_val = await self.get_global_stat(key)
        new_val = int(cur_val or 0) + amount
        await self.set_global_stat(key, str(new_val))

    # ── User Interaction Tracking ────────────────────────────────────────────

    async def track_user(self, discord_uid: str):
        """Track a user interaction (called from any command)."""
        conn = self._db
        if not conn: return
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """
            INSERT INTO user_interactions (discord_uid, first_seen_at, last_seen_at, interaction_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(discord_uid) DO UPDATE SET
                last_seen_at = ?,
                interaction_count = interaction_count + 1
            """,
            (discord_uid, now, now, now),
        )
        await conn.commit()

    # ── Run Sessions ─────────────────────────────────────────────────────────

    async def create_session(
        self,
        discord_uid: str,
        token_id: int,
        channel_id: str,
        message_id: str,
    ) -> str:
        conn = self._db
        if not conn: return ""
        session_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO run_sessions (id, discord_uid, token_id, channel_id,
                                      message_id, started_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'running')
            """,
            (
                session_id,
                discord_uid,
                token_id,
                channel_id,
                message_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()
        return session_id

    async def update_session(
        self,
        session_id: str,
        status: str,
        summary: Optional[dict] = None,
    ):
        conn = self._db
        if not conn: return
        await conn.execute(
            """
            UPDATE run_sessions
            SET status = ?, finished_at = ?, summary = ?
            WHERE id = ?
            """,
            (
                status,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(summary) if summary else None,
                session_id,
            ),
        )
        await conn.commit()

    async def mark_interrupted_sessions(self):
        """Mark all 'running' sessions as 'interrupted' (crash recovery)."""
        conn = self._db
        if not conn: return
        await conn.execute(
            "UPDATE run_sessions SET status = 'interrupted' WHERE status = 'running'"
        )
        await conn.commit()

    # ── Counts for /info ─────────────────────────────────────────────────────

    async def count_unique_users(self) -> int:
        """Count all unique users who have ever interacted with the bot."""
        conn = self._db
        if not conn: return 0
        cur = await conn.execute(
            """
            SELECT COUNT(*) as cnt FROM (
                SELECT discord_uid FROM saved_tokens
                UNION
                SELECT discord_uid FROM quest_stats
                UNION
                SELECT discord_uid FROM user_interactions
            )
            """
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def count_total_quests_done(self) -> int:
        """Autoritative source: use global_stats table."""
        val = await self.get_global_stat("total_quests_done")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        
        # Fallback to counting rows if global_stat is missing/corrupt
        conn = self._db
        if not conn: return 0
        cur = await conn.execute("SELECT COUNT(*) as cnt FROM quest_stats")
        row = await cur.fetchone()
        return row["cnt"] if row else 0
