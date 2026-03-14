"""
Scheduler — background job to auto-run quests for saved tokens.

Uses APScheduler async mode. Checks DB every SCHEDULER_CHECK_HOURS
for tokens with next_run_at <= now and is_active = 1.
"""

import asyncio
import random
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bot.config import (
    SCHEDULER_CHECK_HOURS,
    SCHEDULER_JITTER_MINS,
    AUTO_RUN_INTERVAL_DAYS,
)
from bot.utils.logger import get_logger

logger = get_logger("scheduler")


class QuestScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self._running = False

    def start(self):
        """Start the background scheduler."""
        self.scheduler.add_job(
            self._check_and_run,
            trigger=IntervalTrigger(hours=SCHEDULER_CHECK_HOURS),
            id="quest_auto_run",
            name="Auto-run quests",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info(
            "Scheduler started (check every %dh, jitter ±%dm)",
            SCHEDULER_CHECK_HOURS,
            SCHEDULER_JITTER_MINS,
        )

    def stop(self):
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")

    async def _check_and_run(self):
        """Check DB for due tokens and run quests."""
        from bot.db.database import Database
        from bot.services.crypto import decrypt_token
        from bot.core.discord_api import DiscordAPI, fetch_latest_build_number
        from bot.core.quest_engine import QuestEngine
        from bot.core.task_manager import TaskManager

        db: Database = self.bot.db
        task_manager: TaskManager = self.bot.task_manager

        try:
            due_tokens = await db.get_due_tokens()

            if not due_tokens:
                logger.debug("No tokens due for auto-run")
                return

            logger.info("Found %d token(s) due for auto-run", len(due_tokens))

            for token_data in due_tokens:
                uid = token_data["discord_uid"]
                token_id = token_data["id"]
                label = token_data.get("label", "default")
                hint = token_data.get("token_hint", "????")

                # Jitter: delay by random minutes
                jitter = random.randint(0, SCHEDULER_JITTER_MINS * 60)
                if jitter > 0:
                    logger.debug(
                        "Jitter delay %ds for %s/%s", jitter, uid, label
                    )
                    await asyncio.sleep(jitter)

                # Skip if already running
                if task_manager.is_running(uid, token_id):
                    logger.debug("Token %s/%s already running, skip", uid, label)
                    continue

                try:
                    # Decrypt token
                    token_enc = token_data["token_enc"]
                    if isinstance(token_enc, bytes):
                        token_enc = token_enc.decode("utf-8")
                    token = decrypt_token(token_enc, uid)

                    # Create run task
                    async def _auto_run(
                        _uid=uid,
                        _token=token,
                        _token_id=token_id,
                        _label=label,
                        _hint=hint,
                    ):
                        api = None
                        try:
                            build_number = await fetch_latest_build_number()
                            api = DiscordAPI(_token, build_number)

                            if not await api.validate_token():
                                # Token invalid — deactivate
                                await db.set_token_active(_token_id, False)
                                logger.warning(
                                    "Token %s/%s invalid, deactivated",
                                    _uid, _label,
                                )
                                # DM user
                                try:
                                    user = await self.bot.fetch_user(int(_uid))
                                    await user.send(
                                        f"⚠️ Token **{_label}** (`...{_hint}`) "
                                        "không hợp lệ. Auto-schedule đã bị tắt."
                                    )
                                except Exception:
                                    pass
                                return

                            engine = QuestEngine(api=api)
                            summary = await engine.run_once()
                            await engine.wait_all()

                            # Update run times
                            now = datetime.now(timezone.utc)
                            next_run = now + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
                            await db.update_run_times(_token_id, now, next_run)

                            # Save stats
                            for qid in engine.completed_ids:
                                quest_info = next(
                                    (
                                        q
                                        for q in summary.get("quests", [])
                                        if q["id"] == qid
                                    ),
                                    None,
                                )
                                if quest_info:
                                    await db.save_quest_stat(
                                        token_id=_token_id,
                                        discord_uid=_uid,
                                        quest_id=qid,
                                        quest_name=quest_info.get("name", ""),
                                        task_type=quest_info.get("task_type", ""),
                                        duration_secs=0,
                                        run_mode="auto",
                                    )
                            await db.increment_global_stat(
                                "total_quests_done", len(engine.completed_ids)
                            )

                            # DM summary
                            try:
                                user = await self.bot.fetch_user(int(_uid))
                                completed = len(engine.completed_ids)
                                if completed > 0:
                                    msg = (
                                        f"✅ Auto-run **{_label}** hoàn thành: "
                                        f"{completed} quest(s).\n"
                                        f"Lần chạy tiếp: <t:{int(next_run.timestamp())}:R>"
                                    )
                                    await user.send(msg)
                            except Exception:
                                pass

                            logger.info(
                                "Auto-run completed: %s/%s (%d quests)",
                                _uid, _label, len(engine.completed_ids),
                            )
                        except Exception as e:
                            logger.error(
                                "Auto-run error %s/%s: %s", _uid, _label, e
                            )
                        finally:
                            if api:
                                try:
                                    await api.close()
                                except Exception:
                                    pass

                    await task_manager.start_task(
                        uid=uid,
                        token_id=token_id,
                        coro_factory=_auto_run,
                        label=f"auto-{label}",
                    )

                except Exception as e:
                    logger.error(
                        "Error starting auto-run for %s/%s: %s", uid, label, e
                    )

        except Exception as e:
            logger.error("Scheduler check failed: %s", e)
