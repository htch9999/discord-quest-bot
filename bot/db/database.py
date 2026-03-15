"""
Async SQLite database handler.
"""

import aiosqlite
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from bot.db.models import SCHEMA_SQL


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        """Initialize connection and create tables."""
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(str(path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

        for statement in SCHEMA_SQL.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                await self._db.execute(stmt)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
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
        if next_run_at is None:
            from bot.config import AUTO_RUN_INTERVAL_DAYS
            next_run_at = datetime.now(timezone.utc) + timedelta(days=AUTO_RUN_INTERVAL_DAYS)

        cur = await self._db.execute(
            """
            INSERT INTO saved_tokens (discord_uid, label, token_enc, token_hint, next_run_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (discord_uid, label, token_enc, token_hint, next_run_at.isoformat()),
        )
        await self._db.commit()
        return cur.lastrowid

    async def get_tokens(self, discord_uid: str) -> list[dict]:
        """Get all tokens for a user."""
        cur = await self._db.execute(
            "SELECT * FROM saved_tokens WHERE discord_uid = ? ORDER BY created_at",
            (discord_uid,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_token_by_label(self, discord_uid: str, label: str) -> Optional[dict]:
        cur = await self._db.execute(
            "SELECT * FROM saved_tokens WHERE discord_uid = ? AND label = ?",
            (discord_uid, label),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def get_token_by_id(self, token_id: int) -> Optional[dict]:
        cur = await self._db.execute(
            "SELECT * FROM saved_tokens WHERE id = ?",
            (token_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def remove_token(self, discord_uid: str, label: str) -> bool:
        cur = await self._db.execute(
            "DELETE FROM saved_tokens WHERE discord_uid = ? AND label = ?",
            (discord_uid, label),
        )
        await self._db.commit()
        return cur.rowcount > 0

    async def rename_token(self, discord_uid: str, old_label: str, new_label: str) -> bool:
        cur = await self._db.execute(
            "UPDATE saved_tokens SET label = ? WHERE discord_uid = ? AND label = ?",
            (new_label, discord_uid, old_label),
        )
        await self._db.commit()
        return cur.rowcount > 0

    async def set_token_active(self, token_id: int, active: bool):
        await self._db.execute(
            "UPDATE saved_tokens SET is_active = ? WHERE id = ?",
            (1 if active else 0, token_id),
        )
        await self._db.commit()

    async def update_run_times(self, token_id: int, last_run: datetime, next_run: datetime):
        await self._db.execute(
            "UPDATE saved_tokens SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (last_run.isoformat(), next_run.isoformat(), token_id),
        )
        await self._db.commit()

    async def get_due_tokens(self) -> list[dict]:
        """Get tokens that are due for auto-run."""
        now = datetime.now(timezone.utc).isoformat()
        cur = await self._db.execute(
            "SELECT * FROM saved_tokens WHERE next_run_at <= ? AND is_active = 1",
            (now,),
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
        await self._db.execute(
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
        await self._db.commit()

    async def get_user_stats(self, discord_uid: str) -> dict:
        cur = await self._db.execute(
            "SELECT COUNT(*) as total, SUM(duration_secs) as total_time "
            "FROM quest_stats WHERE discord_uid = ?",
            (discord_uid,),
        )
        row = await cur.fetchone()
        return dict(row) if row else {"total": 0, "total_time": 0}

    # ── Global Stats ─────────────────────────────────────────────────────────

    async def get_global_stat(self, key: str) -> Optional[str]:
        cur = await self._db.execute(
            "SELECT value FROM global_stats WHERE key = ?", (key,)
        )
        row = await cur.fetchone()
        return row["value"] if row else None

    async def set_global_stat(self, key: str, value: str):
        await self._db.execute(
            "INSERT OR REPLACE INTO global_stats (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._db.commit()

    async def increment_global_stat(self, key: str, amount: int = 1):
        cur_val = await self.get_global_stat(key)
        new_val = int(cur_val or 0) + amount
        await self.set_global_stat(key, str(new_val))

    # ── Run Sessions ─────────────────────────────────────────────────────────

    async def create_session(
        self,
        discord_uid: str,
        token_id: int,
        channel_id: str,
        message_id: str,
    ) -> str:
        session_id = str(uuid.uuid4())
        await self._db.execute(
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
        await self._db.commit()
        return session_id

    async def update_session(
        self,
        session_id: str,
        status: str,
        summary: Optional[dict] = None,
    ):
        await self._db.execute(
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
        await self._db.commit()

    async def mark_interrupted_sessions(self):
        """Mark all 'running' sessions as 'interrupted' (crash recovery)."""
        await self._db.execute(
            "UPDATE run_sessions SET status = 'interrupted' WHERE status = 'running'"
        )
        await self._db.commit()

    # ── Counts for /info ─────────────────────────────────────────────────────

    async def count_unique_users(self) -> int:
        cur = await self._db.execute(
            """
            SELECT COUNT(*) as cnt FROM (
                SELECT discord_uid FROM saved_tokens
                UNION
                SELECT discord_uid FROM quest_stats
            )
            """
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def count_total_quests_done(self) -> int:
        cur = await self._db.execute(
            "SELECT COUNT(*) as cnt FROM quest_stats"
        )
        row = await cur.fetchone()
        return row["cnt"] if row else 0
