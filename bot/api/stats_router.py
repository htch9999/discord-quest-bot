"""
Public Stats API — FastAPI router.

Provides read-only aggregate statistics for the website frontend.
All endpoints are public, CORS-enabled, and cached in-memory.
"""

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp
import psutil
import logging

logger = logging.getLogger("stats_api")
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bot.config import VERSION


def create_api(bot) -> FastAPI:
    """Create a FastAPI app wired to the bot instance."""

    api = FastAPI(
        title="Discord Quest Bot API",
        version=VERSION,
        docs_url=None,    # disable Swagger UI in production
        redoc_url=None,
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://htch9999.github.io",
            "https://discord-autoquests.vercel.app",
            "http://localhost:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "*", # Allow all for public stats API to avoid future CORS issues
        ],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # ── In-memory cache ──────────────────────────────────────────────────
    _cache: dict[str, tuple[float, dict]] = {}

    def _get_cached(key: str, ttl: int = 30) -> Optional[dict]:
        if key in _cache:
            ts, data = _cache[key]
            if time.time() - ts < ttl:
                return data
        return None

    def _set_cache(key: str, data: dict):
        _cache[key] = (time.time(), data)

    # ── Background Stats Updater ─────────────────────────────────────────
    # Updates the heavy DB aggregations every 60 seconds independently of API requests
    _bg_task = None
    _stats_data = {
        "total_users": 0,
        "total_quests_completed": 0,
        "quests_today": 0,
        "quests_this_week": 0,
        "quest_type_breakdown": {}
    }

    async def _update_stats_loop():
        while True:
            try:
                db = bot.db
                _stats_data["total_users"] = await db.count_unique_users()
                _stats_data["total_quests_completed"] = await db.count_total_quests_done()
                
                # Breakdown
                try:
                    cur = await db._db.execute(
                        "SELECT task_type, COUNT(*) as cnt FROM quest_stats GROUP BY task_type"
                    )
                    rows = await cur.fetchall()
                    _stats_data["quest_type_breakdown"] = {r["task_type"]: r["cnt"] for r in rows}
                except Exception as e:
                    logger.error("Error computing quest_type_breakdown: %s", e)

                # Quests today / this week
                now = datetime.now(timezone.utc)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                week_start = today_start - timedelta(days=today_start.weekday())

                try:
                    cur = await db._db.execute(
                        "SELECT COUNT(*) as cnt FROM quest_stats WHERE completed_at >= ?",
                        (today_start.isoformat(),)
                    )
                    row = await cur.fetchone()
                    _stats_data["quests_today"] = row["cnt"] if row else 0

                    cur = await db._db.execute(
                        "SELECT COUNT(*) as cnt FROM quest_stats WHERE completed_at >= ?",
                        (week_start.isoformat(),)
                    )
                    row = await cur.fetchone()
                    _stats_data["quests_this_week"] = row["cnt"] if row else 0
                except Exception as e:
                    logger.error("Error computing quests today/week: %s", e)
            except Exception as e:
                logger.error("Error in stats update loop: %s", e)
                
            await asyncio.sleep(60)

    @api.on_event("startup")
    async def startup_event():
        nonlocal _bg_task
        _bg_task = asyncio.create_task(_update_stats_loop())

    @api.on_event("shutdown")
    async def shutdown_event():
        if _bg_task:
            _bg_task.cancel()

    # ── GET /v1/stats/public ─────────────────────────────────────────────
    @api.get("/v1/stats/public")
    async def stats_public():
        cached = _get_cached("stats_public", ttl=10) # Reduced ttl for faster live updates for active stats
        if cached:
            return cached

        guild_count = len(bot.guilds) if bot.is_ready() else 0
        latency_ms = round(bot.latency * 1000, 1) if bot.is_ready() else -1
        uptime_secs = int(time.time() - bot.start_time)

        # Active sessions from task manager
        tm_status = bot.task_manager.get_status()

        data = {
            "total_users": _stats_data["total_users"],
            "total_quests_completed": _stats_data["total_quests_completed"],
            "quests_today": _stats_data["quests_today"],
            "quests_this_week": _stats_data["quests_this_week"],
            "active_sessions": tm_status["active_quests"],
            "uptime_seconds": uptime_secs,
            "bot_ping_ms": latency_ms,
            "guild_count": guild_count,
            "quest_type_breakdown": _stats_data["quest_type_breakdown"],
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        _set_cache("stats_public", data)
        return data

    # ── GET /v1/stats/server ─────────────────────────────────────────────
    @api.get("/v1/stats/server")
    async def stats_server():
        cached = _get_cached("stats_server", ttl=30)
        if cached:
            return cached

        guild_count = len(bot.guilds) if bot.is_ready() else 0
        total_members = sum(g.member_count or 0 for g in bot.guilds) if bot.is_ready() else 0

        data = {
            "guild_count": guild_count,
            "total_members": total_members,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        _set_cache("stats_server", data)
        return data

    # ── GET /v1/health ───────────────────────────────────────────────────
    @api.get("/v1/health")
    async def health():
        bot_ready = bot.is_ready()
        uptime = int(time.time() - bot.start_time)
        mem = psutil.Process().memory_info()

        status = "operational" if bot_ready else "degraded"

        return {
            "status": status,
            "bot_ready": bot_ready,
            "uptime_seconds": uptime,
            "memory_mb": round(mem.rss / 1024 / 1024, 1),
            "cpu_percent": psutil.cpu_percent(interval=0),
            "version": VERSION,
            "response_time_ms": round(bot.latency * 1000, 1) if bot_ready else -1,
        }

    # ── GET /v1/github ───────────────────────────────────────────────────
    @api.get("/v1/github")
    async def github_stats():
        cached = _get_cached("github", ttl=300)  # 5 min cache
        if cached:
            return cached

        repo = "htch9999/discord-quest-bot"
        data = {}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.github.com/repos/{repo}",
                    headers={"Accept": "application/vnd.github.v3+json"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        gh = await resp.json()
                        data = {
                            "stars": gh.get("stargazers_count", 0),
                            "forks": gh.get("forks_count", 0),
                            "open_issues": gh.get("open_issues_count", 0),
                            "last_commit": gh.get("pushed_at", ""),
                            "language": gh.get("language", "Python"),
                            "description": gh.get("description", ""),
                        }

                # Fetch latest release
                async with session.get(
                    f"https://api.github.com/repos/{repo}/releases/latest",
                    headers={"Accept": "application/vnd.github.v3+json"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        rel = await resp.json()
                        data["latest_release"] = rel.get("tag_name", "")
                    else:
                        data["latest_release"] = ""
        except Exception:
            data = {
                "stars": 0, "forks": 0, "open_issues": 0,
                "last_commit": "", "latest_release": "",
                "language": "Python", "description": "",
            }

        data["cached_at"] = datetime.now(timezone.utc).isoformat()
        _set_cache("github", data)
        return data

    return api
