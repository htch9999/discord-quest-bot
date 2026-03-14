"""
Per-user rate limiter for commands and quest runs.
"""

import time
from collections import defaultdict
from bot.config import MAX_RUNS_PER_HOUR, COMMAND_COOLDOWN


class RateLimiter:
    """
    Tracks per-user rate limits:
    - Quest runs: max MAX_RUNS_PER_HOUR per hour
    - Command cooldown: COMMAND_COOLDOWN seconds between commands
    """

    def __init__(self):
        # uid -> list of timestamps (quest runs in last hour)
        self._run_history: dict[str, list[float]] = defaultdict(list)
        # uid -> last command timestamp
        self._last_command: dict[str, float] = {}

    def _cleanup_runs(self, uid: str):
        """Remove run timestamps older than 1 hour."""
        cutoff = time.time() - 3600
        self._run_history[uid] = [
            t for t in self._run_history[uid] if t > cutoff
        ]

    def can_run(self, uid: str) -> tuple[bool, str]:
        """Check if user can start a quest run. Returns (allowed, reason)."""
        self._cleanup_runs(uid)
        if len(self._run_history[uid]) >= MAX_RUNS_PER_HOUR:
            oldest = self._run_history[uid][0]
            wait = int(3600 - (time.time() - oldest))
            return False, f"Đã đạt giới hạn {MAX_RUNS_PER_HOUR} lần/giờ. Chờ {wait}s."
        return True, ""

    def record_run(self, uid: str):
        """Record a quest run for rate limiting."""
        self._run_history[uid].append(time.time())

    def can_command(self, uid: str) -> tuple[bool, str]:
        """Check command cooldown. Returns (allowed, reason)."""
        last = self._last_command.get(uid, 0)
        elapsed = time.time() - last
        if elapsed < COMMAND_COOLDOWN:
            wait = int(COMMAND_COOLDOWN - elapsed)
            return False, f"Cooldown: chờ {wait}s."
        return True, ""

    def record_command(self, uid: str):
        """Record a command use."""
        self._last_command[uid] = time.time()
