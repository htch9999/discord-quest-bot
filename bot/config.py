"""
Bot configuration — loads .env and defines constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ── Bot ──────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_PREFIX: str = os.getenv("BOT_PREFIX", "!")

# ── Security ─────────────────────────────────────────────────────────────────
MASTER_SECRET: str = os.getenv("MASTER_SECRET", "")

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "quest_bot.db"))

# ── Discord API ──────────────────────────────────────────────────────────────
API_BASE: str = "https://discord.com/api/v9"
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))
HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
AUTO_ACCEPT: bool = os.getenv("AUTO_ACCEPT", "true").lower() in ("true", "1", "yes")

# ── Concurrency ──────────────────────────────────────────────────────────────
MAX_PARALLEL_PLAY: int = int(os.getenv("MAX_PARALLEL_PLAY", "6"))
MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", "10"))
TASK_TIMEOUT_HOURS: int = int(os.getenv("TASK_TIMEOUT_HOURS", "6"))

# ── Rate Limits ──────────────────────────────────────────────────────────────
MAX_RUNS_PER_HOUR: int = int(os.getenv("MAX_RUNS_PER_HOUR", "5"))
COMMAND_COOLDOWN: int = int(os.getenv("COMMAND_COOLDOWN", "10"))

# ── Scheduler ────────────────────────────────────────────────────────────────
AUTO_RUN_INTERVAL_DAYS: int = int(os.getenv("AUTO_RUN_INTERVAL_DAYS", "2"))
SCHEDULER_CHECK_HOURS: int = int(os.getenv("SCHEDULER_CHECK_HOURS", "1"))
SCHEDULER_JITTER_MINS: int = int(os.getenv("SCHEDULER_JITTER_MINS", "30"))

# ── Logging ──────────────────────────────────────────────────────────────────
DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
LOG_DIR: str = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
LOG_PROGRESS: bool = os.getenv("LOG_PROGRESS", "true").lower() in ("true", "1", "yes")

# ── Progress embed ───────────────────────────────────────────────────────────
EMBED_UPDATE_INTERVAL: int = int(os.getenv("EMBED_UPDATE_INTERVAL", "5"))

# ── Supported task types ─────────────────────────────────────────────────────
SUPPORTED_TASKS: list[str] = [
    "WATCH_VIDEO",
    "PLAY_ON_DESKTOP",
    "STREAM_ON_DESKTOP",
    "PLAY_ACTIVITY",
    "WATCH_VIDEO_ON_MOBILE",
]

# ── Version ──────────────────────────────────────────────────────────────────
VERSION: str = "2.0 Public Beta"
