"""
Quest engine — async port of QuestAutocompleter from original main.py.

All quest-related logic: helpers, fetching, enrolling, completing tasks.
Uses callbacks for progress/completion reporting to decouple from Discord embed.
"""

import asyncio
import random
import time
import traceback
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

from bot.core.discord_api import DiscordAPI
from bot.config import (
    HEARTBEAT_INTERVAL,
    AUTO_ACCEPT,
    MAX_PARALLEL_PLAY,
    SUPPORTED_TASKS,
    DEBUG,
)
from bot.utils.logger import get_logger

logger = get_logger("quest_engine")

# ── Type aliases for callbacks ───────────────────────────────────────────────
ProgressCallback = Optional[Callable[[str, str, str, float, float], Awaitable[None]]]
# (quest_id, quest_name, task_type, done, total)

CompleteCallback = Optional[Callable[[str, str, str, int], Awaitable[None]]]
# (quest_id, quest_name, task_type, duration_secs)


# ── Quest helper functions ───────────────────────────────────────────────────

def _get(d: Optional[dict], *keys):
    """Get value from dict trying multiple key names (camelCase & snake_case)."""
    if d is None:
        return None
    for k in keys:
        if k in d:
            return d[k]
    return None


def get_task_config(quest: dict) -> Optional[dict]:
    cfg = quest.get("config", {})
    return _get(cfg, "taskConfig", "task_config", "taskConfigV2", "task_config_v2")


def get_quest_name(quest: dict) -> str:
    cfg = quest.get("config", {})
    msgs = cfg.get("messages", {})
    name = _get(msgs, "questName", "quest_name")
    if name:
        return name.strip()
    game = _get(msgs, "gameTitle", "game_title")
    if game:
        return game.strip()
    app_name = cfg.get("application", {}).get("name")
    if app_name:
        return app_name
    return f"Quest#{quest.get('id', '?')}"


def get_expires_at(quest: dict) -> Optional[str]:
    cfg = quest.get("config", {})
    return _get(cfg, "expiresAt", "expires_at")


def get_user_status(quest: dict) -> dict:
    us = _get(quest, "userStatus", "user_status")
    return us if isinstance(us, dict) else {}


def is_completable(quest: dict) -> bool:
    expires = get_expires_at(quest)
    if expires:
        try:
            exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if exp_dt <= datetime.now(timezone.utc):
                return False
        except Exception:
            pass

    tc = get_task_config(quest)
    if not tc or "tasks" not in tc:
        return False

    tasks = tc["tasks"]
    return any(tasks.get(t) is not None for t in SUPPORTED_TASKS)


def is_enrolled(quest: dict) -> bool:
    us = get_user_status(quest)
    return bool(_get(us, "enrolledAt", "enrolled_at"))


def is_completed(quest: dict) -> bool:
    us = get_user_status(quest)
    return bool(_get(us, "completedAt", "completed_at"))


def get_task_type(quest: dict) -> Optional[str]:
    tc = get_task_config(quest)
    if not tc or "tasks" not in tc:
        return None
    for t in SUPPORTED_TASKS:
        if tc["tasks"].get(t) is not None:
            return t
    return None


def get_seconds_needed(quest: dict) -> int:
    tc = get_task_config(quest)
    task_type = get_task_type(quest)
    if not tc or not task_type:
        return 0
    return tc["tasks"][task_type].get("target", 0)


def get_seconds_done(quest: dict) -> float:
    task_type = get_task_type(quest)
    if not task_type:
        return 0
    us = get_user_status(quest)
    progress = us.get("progress", {})
    if not progress:
        progress = {}
    return progress.get(task_type, {}).get("value", 0)


def get_enrolled_at(quest: dict) -> Optional[str]:
    us = get_user_status(quest)
    return _get(us, "enrolledAt", "enrolled_at")


# ── Quest Engine ─────────────────────────────────────────────────────────────

class QuestEngine:
    """
    Async quest autocompleter engine.

    Unlike the original threaded QuestAutocompleter, this uses asyncio tasks
    and communicates progress via callbacks.
    """

    def __init__(
        self,
        api: DiscordAPI,
        on_progress: ProgressCallback = None,
        on_complete: CompleteCallback = None,
    ):
        self.api = api
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.completed_ids: set = set()
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(MAX_PARALLEL_PLAY)
        self._cancelled = False

    def cancel(self):
        """Signal all running tasks to stop."""
        self._cancelled = True
        for task in self._running_tasks.values():
            task.cancel()

    async def _notify_progress(
        self, qid: str, name: str, task_type: str, done: float, total: float
    ):
        if self.on_progress:
            try:
                await self.on_progress(qid, name, task_type, done, total)
            except Exception:
                pass

    async def _notify_complete(
        self, qid: str, name: str, task_type: str, duration: int
    ):
        if self.on_complete:
            try:
                await self.on_complete(qid, name, task_type, duration)
            except Exception:
                pass

    # ── Fetch quests ─────────────────────────────────────────────────────────

    async def fetch_quests(self) -> list:
        try:
            r = await self.api.get("/quests/@me")

            if r.status == 200:
                data = await r.json()
                if isinstance(data, dict):
                    quests = data.get("quests", [])
                    excluded = data.get("excluded_quests", [])
                    blocked = _get(data, "quest_enrollment_blocked_until")
                    if blocked:
                        logger.warning("Enrollment blocked until: %s", blocked)
                    if excluded:
                        logger.debug("%d quest(s) excluded", len(excluded))
                    return quests
                elif isinstance(data, list):
                    return data
                return []

            elif r.status == 429:
                body = await r.json()
                retry_after = body.get("retry_after", 10)
                logger.warning("Rate limited – chờ %ds", retry_after)
                await asyncio.sleep(retry_after)
                return await self.fetch_quests()
            else:
                text = await r.text()
                logger.warning("Quest fetch lỗi (%s): %s", r.status, text[:200])
                return []

        except Exception as e:
            logger.error("Error fetching quests: %s", e)
            if DEBUG:
                traceback.print_exc()
            return []

    # ── Auto-accept ──────────────────────────────────────────────────────────

    async def enroll_quest(self, quest: dict) -> bool:
        name = get_quest_name(quest)
        qid = quest["id"]

        for attempt in range(1, 4):
            try:
                r = await self.api.post(
                    f"/quests/{qid}/enroll",
                    {
                        "location": 11,
                        "is_targeted": False,
                        "metadata_raw": None,
                        "metadata_sealed": None,
                        "traffic_metadata_raw": quest.get("traffic_metadata_raw"),
                        "traffic_metadata_sealed": quest.get("traffic_metadata_sealed"),
                    },
                )

                if r.status == 429:
                    body = await r.json()
                    retry_after = body.get("retry_after", 5)
                    wait = retry_after + 1
                    logger.warning(
                        'Rate limited nhận "%s" (lần %d/3) – chờ %ds',
                        name, attempt, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                if r.status in (200, 201, 204):
                    logger.info("Đã nhận: %s", name)
                    return True

                text = await r.text()
                logger.warning(
                    'Enroll "%s" thất bại (%s): %s', name, r.status, text[:200]
                )
                return False

            except Exception as e:
                logger.error('Lỗi enroll "%s": %s', name, e)
                return False

        logger.warning('Bỏ qua "%s" sau 3 lần rate limited', name)
        return False

    async def auto_accept(self, quests: list) -> list:
        if not AUTO_ACCEPT:
            return quests

        unaccepted = [
            q
            for q in quests
            if not is_enrolled(q) and not is_completed(q) and is_completable(q)
        ]

        if not unaccepted:
            return quests

        logger.info(
            "Tìm thấy %d quest chưa nhận – đang auto-accept...", len(unaccepted)
        )

        for q in unaccepted:
            await self.enroll_quest(q)
            await asyncio.sleep(3)

        await asyncio.sleep(2)
        return await self.fetch_quests()

    # ── Complete: WATCH_VIDEO ────────────────────────────────────────────────

    async def complete_video(self, quest: dict):
        name = get_quest_name(quest)
        qid = quest["id"]
        seconds_needed = get_seconds_needed(quest)
        seconds_done = get_seconds_done(quest)
        enrolled_at_str = get_enrolled_at(quest)
        start_ts = time.time()

        if enrolled_at_str:
            enrolled_ts = datetime.fromisoformat(
                enrolled_at_str.replace("Z", "+00:00")
            ).timestamp()
        else:
            enrolled_ts = time.time()

        logger.info("🎬 Video: %s (%d/%ds)", name, seconds_done, seconds_needed)
        await self._notify_progress(qid, name, "WATCH_VIDEO", seconds_done, seconds_needed)

        max_future = 10
        speed = 7
        interval = 1

        while seconds_done < seconds_needed and not self._cancelled:
            max_allowed = (time.time() - enrolled_ts) + max_future
            diff = max_allowed - seconds_done
            timestamp = seconds_done + speed

            if diff >= speed:
                try:
                    r = await self.api.post(
                        f"/quests/{qid}/video-progress",
                        {"timestamp": min(seconds_needed, timestamp + random.random())},
                    )
                    if r.status == 200:
                        body = await r.json()
                        if body.get("completed_at"):
                            duration = int(time.time() - start_ts)
                            logger.info("✅ Hoàn thành: %s", name)
                            await self._notify_complete(qid, name, "WATCH_VIDEO", duration)
                            return
                        seconds_done = min(seconds_needed, timestamp)
                        logger.debug("  [%s] %d/%ds", name, seconds_done, seconds_needed)
                        await self._notify_progress(
                            qid, name, "WATCH_VIDEO", seconds_done, seconds_needed
                        )
                    elif r.status == 429:
                        body = await r.json()
                        retry_after = body.get("retry_after", 5)
                        logger.warning("  Rate limited – chờ %ds", retry_after + 1)
                        await asyncio.sleep(retry_after + 1)
                        continue
                    else:
                        text = await r.text()
                        logger.warning(
                            "  Video progress lỗi (%s): %s", r.status, text[:200]
                        )
                except Exception as e:
                    logger.error("  Lỗi: %s", e)

            if timestamp >= seconds_needed:
                break
            await asyncio.sleep(interval)

        # Final push
        try:
            await self.api.post(
                f"/quests/{qid}/video-progress", {"timestamp": seconds_needed}
            )
        except Exception:
            pass

        duration = int(time.time() - start_ts)
        logger.info("✅ Hoàn thành: %s", name)
        await self._notify_complete(qid, name, "WATCH_VIDEO", duration)

    # ── Complete: PLAY_ON_DESKTOP / STREAM_ON_DESKTOP ────────────────────────

    async def complete_heartbeat(self, quest: dict):
        name = get_quest_name(quest)
        qid = quest["id"]
        task_type = get_task_type(quest)
        seconds_needed = get_seconds_needed(quest)
        seconds_done = get_seconds_done(quest)
        start_ts = time.time()

        remaining = max(0, seconds_needed - seconds_done)
        logger.info(
            "🎮 %s: %s (~%d phút còn lại)", task_type, name, remaining // 60
        )

        pid = random.randint(1000, 30000)
        await self._notify_progress(qid, name, task_type, seconds_done, seconds_needed)

        while seconds_done < seconds_needed and not self._cancelled:
            try:
                r = await self.api.post(
                    f"/quests/{qid}/heartbeat",
                    {"stream_key": f"call:0:{pid}", "terminal": False},
                )

                if r.status == 200:
                    body = await r.json()
                    progress_data = body.get("progress", {})
                    if progress_data and task_type in progress_data:
                        seconds_done = progress_data[task_type].get(
                            "value", seconds_done
                        )
                    logger.debug("  [%s] %d/%ds", name, seconds_done, seconds_needed)
                    await self._notify_progress(
                        qid, name, task_type, seconds_done, seconds_needed
                    )

                    if body.get("completed_at") or seconds_done >= seconds_needed:
                        duration = int(time.time() - start_ts)
                        logger.info("✅ Hoàn thành: %s", name)
                        await self._notify_complete(qid, name, task_type, duration)
                        return

                elif r.status == 429:
                    body = await r.json()
                    retry_after = body.get("retry_after", 10)
                    logger.warning("  Rate limited – chờ %ds", retry_after + 1)
                    await asyncio.sleep(retry_after + 1)
                    continue
                else:
                    text = await r.text()
                    logger.warning(
                        "  Heartbeat lỗi (%s): %s", r.status, text[:200]
                    )

            except Exception as e:
                logger.error("  Lỗi heartbeat: %s", e)

            await asyncio.sleep(HEARTBEAT_INTERVAL)

        # Terminal heartbeat
        try:
            await self.api.post(
                f"/quests/{qid}/heartbeat",
                {"stream_key": f"call:0:{pid}", "terminal": True},
            )
        except Exception:
            pass

        duration = int(time.time() - start_ts)
        logger.info("✅ Hoàn thành: %s", name)
        await self._notify_complete(qid, name, task_type, duration)

    # ── Complete: PLAY_ACTIVITY ──────────────────────────────────────────────

    async def complete_activity(self, quest: dict):
        name = get_quest_name(quest)
        qid = quest["id"]
        seconds_needed = get_seconds_needed(quest)
        seconds_done = get_seconds_done(quest)
        start_ts = time.time()

        remaining = max(0, seconds_needed - seconds_done)
        logger.info(
            "🕹️  Activity: %s (~%d phút còn lại)", name, remaining // 60
        )

        stream_key = "call:0:1"
        await self._notify_progress(qid, name, "PLAY_ACTIVITY", seconds_done, seconds_needed)

        while seconds_done < seconds_needed and not self._cancelled:
            try:
                r = await self.api.post(
                    f"/quests/{qid}/heartbeat",
                    {"stream_key": stream_key, "terminal": False},
                )

                if r.status == 200:
                    body = await r.json()
                    progress_data = body.get("progress", {})
                    if progress_data and "PLAY_ACTIVITY" in progress_data:
                        seconds_done = progress_data["PLAY_ACTIVITY"].get(
                            "value", seconds_done
                        )
                    logger.debug("  [%s] %d/%ds", name, seconds_done, seconds_needed)
                    await self._notify_progress(
                        qid, name, "PLAY_ACTIVITY", seconds_done, seconds_needed
                    )

                    if body.get("completed_at") or seconds_done >= seconds_needed:
                        break
                elif r.status == 429:
                    body = await r.json()
                    retry_after = body.get("retry_after", 10)
                    logger.warning("  Rate limited – chờ %ds", retry_after + 1)
                    await asyncio.sleep(retry_after + 1)
                    continue
                else:
                    text = await r.text()
                    logger.warning(
                        "  Heartbeat lỗi (%s): %s", r.status, text[:200]
                    )
            except Exception as e:
                logger.error("  Lỗi: %s", e)

            await asyncio.sleep(HEARTBEAT_INTERVAL)

        # Terminal
        try:
            await self.api.post(
                f"/quests/{qid}/heartbeat",
                {"stream_key": stream_key, "terminal": True},
            )
        except Exception:
            pass

        duration = int(time.time() - start_ts)
        logger.info("✅ Hoàn thành: %s", name)
        await self._notify_complete(qid, name, "PLAY_ACTIVITY", duration)

    # ── Process a single quest ───────────────────────────────────────────────

    async def process_quest(self, quest: dict):
        """Process a single quest based on its task type."""
        qid = quest.get("id")
        name = get_quest_name(quest)
        task_type = get_task_type(quest)

        if not task_type:
            logger.warning('"%s" – task không hỗ trợ, bỏ qua', name)
            return

        if qid in self.completed_ids:
            return

        logger.info("━━━ Bắt đầu: %s (task: %s) ━━━", name, task_type)

        async def _run():
            async with self._semaphore:
                try:
                    if task_type in ("WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"):
                        await self.complete_video(quest)
                    elif task_type == "PLAY_ACTIVITY":
                        await self.complete_activity(quest)
                    elif task_type in ("PLAY_ON_DESKTOP", "STREAM_ON_DESKTOP"):
                        await self.complete_heartbeat(quest)
                    self.completed_ids.add(qid)
                except asyncio.CancelledError:
                    logger.info("Task cancelled: %s", name)
                except Exception as e:
                    logger.error("Error processing %s: %s", name, e)
                    if DEBUG:
                        traceback.print_exc()
                finally:
                    self._running_tasks.pop(qid, None)

        task = asyncio.create_task(_run())
        self._running_tasks[qid] = task

    # ── Run all quests once ──────────────────────────────────────────────────

    async def run_once(self) -> dict:
        """
        Fetch quests, auto-accept, and complete all actionable quests.
        Returns a summary dict.
        """
        self._cancelled = False
        summary = {
            "total": 0,
            "enrolled": 0,
            "completed_before": 0,
            "completed_now": 0,
            "errors": 0,
            "quests": [],
        }

        quests = await self.fetch_quests()
        summary["total"] = len(quests)

        if not quests:
            logger.info("Không có quest nào")
            return summary

        summary["enrolled"] = sum(1 for q in quests if is_enrolled(q))
        summary["completed_before"] = sum(1 for q in quests if is_completed(q))

        # Auto-accept
        quests = await self.auto_accept(quests)

        # Filter actionable
        actionable = [
            q
            for q in quests
            if is_enrolled(q)
            and not is_completed(q)
            and is_completable(q)
            and q.get("id") not in self.completed_ids
        ]

        if not actionable:
            logger.info("Không có quest nào cần hoàn thành lúc này")
            return summary

        logger.info("%d quest(s) cần hoàn thành:", len(actionable))

        # Start all quest processing tasks
        for q in actionable:
            await self.process_quest(q)
            summary["quests"].append({
                "id": q.get("id"),
                "name": get_quest_name(q),
                "task_type": get_task_type(q),
            })

        # Wait for all tasks to complete
        if self._running_tasks:
            await asyncio.gather(
                *self._running_tasks.values(), return_exceptions=True
            )

        summary["completed_now"] = len(self.completed_ids)
        return summary

    async def wait_all(self):
        """Wait for all currently running tasks to finish."""
        if self._running_tasks:
            await asyncio.gather(
                *list(self._running_tasks.values()), return_exceptions=True
            )

    def get_running_quests(self) -> list[str]:
        """Return IDs of currently running quest tasks."""
        return [qid for qid, task in self._running_tasks.items() if not task.done()]
