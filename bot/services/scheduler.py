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
    SCHEDULER_CLEANUP_HOURS,
    TOKEN_MAX_FAILURES,
    TOKEN_INACTIVE_CLEANUP_DAYS,
)
from bot.utils.logger import get_logger
from bot.utils.formatter import auto_run_embed, token_invalid_embed, token_deleted_embed
from bot.utils.i18n import tr
from bot.services.progress_message import ProgressMessage

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
        self.scheduler.add_job(
            self.cleanup_dead_tokens,
            trigger=IntervalTrigger(hours=SCHEDULER_CLEANUP_HOURS),
            id="dead_token_cleanup",
            name="Clean up dead saved tokens",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info(
            "Scheduler started (check every %dh, jitter ±%dm)",
            SCHEDULER_CHECK_HOURS,
            SCHEDULER_JITTER_MINS,
        )

    async def cleanup_dead_tokens(self):
        """Remove tokens repeatedly rejected by Discord or stale while paused."""
        try:
            tokens = await self.bot.db.get_dead_tokens(
                TOKEN_MAX_FAILURES, TOKEN_INACTIVE_CLEANUP_DAYS
            )
            removed = 0
            for token in tokens:
                deleted = await self.bot.db.delete_token_by_id(token["id"])
                removed += bool(deleted)
                if deleted:
                    try:
                        language = await self.bot.db.get_user_language(token["discord_uid"])
                        user = await self.bot.fetch_user(int(token["discord_uid"]))
                        await user.send(embed=token_deleted_embed(
                            token.get("label", "default"),
                            token.get("token_hint", "????"),
                            language=language,
                        ))
                    except Exception:
                        logger.debug("Could not notify user about token cleanup")
            if removed:
                logger.info("Removed %d dead or stale saved token(s)", removed)
        except Exception:
            logger.exception("Dead-token cleanup failed")

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
        from bot.core.quest_engine import QuestEngine, get_quest_name, get_task_type, get_seconds_needed
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
                language = await db.get_user_language(uid)

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
                        _language=language,
                    ):
                        api = None
                        progress = None
                        quest_mode = await db.get_user_quest_mode(_uid)

                        async def on_start(actionable):
                            nonlocal progress
                            try:
                                user = await self.bot.fetch_user(int(_uid))
                                channel = await user.create_dm()
                                progress = ProgressMessage(
                                    channel=channel,
                                    token_hint=_hint,
                                    user_name=user.display_name,
                                    language=_language,
                                    run_mode="scheduled",
                                    quest_mode=quest_mode,
                                )
                                for quest in actionable:
                                    progress.update_quest(
                                        str(quest.get("id")),
                                        get_quest_name(quest),
                                        get_task_type(quest) or "Quest",
                                        0,
                                        get_seconds_needed(quest),
                                        status="queued",
                                    )
                                await progress.start()
                            except Exception as e:
                                progress = None
                                logger.warning("Could not start progress message for %s: %s", _uid, e)

                        async def on_progress(qid, name, task_type, done, total):
                            if progress:
                                progress.update_quest(qid, name, task_type, done, total)

                        async def on_complete(qid, name, task_type, duration):
                            if progress:
                                progress.mark_complete(qid, name, task_type, duration)

                        async def on_quest_start(qid, name, task_type):
                            if progress:
                                progress.mark_running(qid, name, task_type)

                        try:
                            build_number = await fetch_latest_build_number()
                            api = DiscordAPI(_token, build_number)

                            valid, status = await api.validate_token_status()
                            if not valid:
                                if status != 401:
                                    try:
                                        user = await self.bot.fetch_user(int(_uid))
                                        await user.send(tr(_language, "temporary_validation"))
                                    except Exception:
                                        pass
                                    return
                                failures = await db.record_token_failure(_token_id)
                                await db.set_token_active(_token_id, False)
                                logger.warning(
                                    "Token %s/%s invalid, deactivated",
                                    _uid, _label,
                                )
                                # DM user
                                try:
                                    user = await self.bot.fetch_user(int(_uid))
                                    if failures >= TOKEN_MAX_FAILURES:
                                        await db.delete_token_by_id(_token_id)
                                        await user.send(embed=token_deleted_embed(_label, _hint, language=_language))
                                    else:
                                        await user.send(embed=token_invalid_embed(_label, _hint, failures, TOKEN_MAX_FAILURES, _language))
                                except Exception:
                                    pass
                                return

                            engine = QuestEngine(
                                api=api,
                                on_progress=on_progress,
                                on_complete=on_complete,
                                on_start=on_start,
                                on_quest_start=on_quest_start,
                                run_mode=quest_mode,
                            )
                            summary = await engine.run_once()
                            await engine.wait_all()

                            # Update run times
                            now = datetime.now(timezone.utc)
                            next_run = now + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
                            await db.update_run_times(_token_id, now, next_run)

                            if progress:
                                await progress.finish(summary, next_run)

                            # Save stats
                            completed_names = []
                            newly_completed = 0
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
                                    quest_name = quest_info.get("name", "")
                                    task_type = quest_info.get("task_type", "")
                                    if quest_name:
                                        name_str = f"{quest_name} [{task_type}]" if task_type else quest_name
                                        completed_names.append(name_str)
                                    inserted = await db.save_quest_stat(
                                        token_id=_token_id,
                                        discord_uid=_uid,
                                        quest_id=qid,
                                        quest_name=quest_name,
                                        task_type=quest_info.get("task_type", ""),
                                        duration_secs=0,
                                        run_mode="auto",
                                    )
                                    newly_completed += int(bool(inserted))
                            await db.reset_token_failures(_token_id)
                            await db.increment_global_stat(
                                "total_quests_done", newly_completed
                            )

                            # Do not send a success notification when nothing completed.
                            if engine.completed_ids and not progress:
                                try:
                                    user = await self.bot.fetch_user(int(_uid))
                                    await user.send(embed=auto_run_embed(
                                        _label, _hint, len(engine.completed_ids), completed_names, next_run,
                                        language=_language, quest_mode=quest_mode,
                                    ))
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

    async def run_all_active(self):
        """Check and run quests for ALL active tokens (startup use).

        Unlike _check_and_run which only processes due tokens,
        this processes ALL active tokens regardless of schedule.
        """
        from bot.db.database import Database
        from bot.services.crypto import decrypt_token
        from bot.core.discord_api import DiscordAPI, fetch_latest_build_number
        from bot.core.quest_engine import QuestEngine, get_quest_name, get_task_type, get_seconds_needed
        from bot.core.task_manager import TaskManager

        db: Database = self.bot.db
        task_manager: TaskManager = self.bot.task_manager

        try:
            active_tokens = await db.get_all_active_tokens()

            if not active_tokens:
                logger.info("Startup: no active tokens found")
                return

            logger.info("Startup: found %d active token(s) to check", len(active_tokens))

            for token_data in active_tokens:
                uid = token_data["discord_uid"]
                token_id = token_data["id"]
                label = token_data.get("label", "default")
                hint = token_data.get("token_hint", "????")
                language = await db.get_user_language(uid)

                # Skip if already running
                if task_manager.is_running(uid, token_id):
                    logger.debug("Startup: token %s/%s already running, skip", uid, label)
                    continue

                try:
                    # Decrypt token
                    token_enc = token_data["token_enc"]
                    if isinstance(token_enc, bytes):
                        token_enc = token_enc.decode("utf-8")
                    token = decrypt_token(token_enc, uid)

                    # Create run task
                    async def _startup_run(
                        _uid=uid,
                        _token=token,
                        _token_id=token_id,
                        _label=label,
                        _hint=hint,
                        _language=language,
                    ):
                        api = None
                        progress = None
                        quest_mode = await db.get_user_quest_mode(_uid)

                        async def on_start(actionable):
                            nonlocal progress
                            try:
                                user = await self.bot.fetch_user(int(_uid))
                                channel = await user.create_dm()
                                progress = ProgressMessage(
                                    channel=channel,
                                    token_hint=_hint,
                                    user_name=user.display_name,
                                    language=_language,
                                    run_mode="startup",
                                    quest_mode=quest_mode,
                                )
                                for quest in actionable:
                                    progress.update_quest(
                                        str(quest.get("id")),
                                        get_quest_name(quest),
                                        get_task_type(quest) or "Quest",
                                        0,
                                        get_seconds_needed(quest),
                                        status="queued",
                                    )
                                await progress.start()
                            except Exception as e:
                                progress = None
                                logger.warning("Could not start startup progress message for %s: %s", _uid, e)

                        async def on_progress(qid, name, task_type, done, total):
                            if progress:
                                progress.update_quest(qid, name, task_type, done, total)

                        async def on_complete(qid, name, task_type, duration):
                            if progress:
                                progress.mark_complete(qid, name, task_type, duration)

                        async def on_quest_start(qid, name, task_type):
                            if progress:
                                progress.mark_running(qid, name, task_type)

                        try:
                            build_number = await fetch_latest_build_number()
                            api = DiscordAPI(_token, build_number)

                            valid, status = await api.validate_token_status()
                            if not valid:
                                if status != 401:
                                    try:
                                        user = await self.bot.fetch_user(int(_uid))
                                        await user.send(tr(_language, "temporary_validation"))
                                    except Exception:
                                        pass
                                    return
                                failures = await db.record_token_failure(_token_id)
                                await db.set_token_active(_token_id, False)
                                logger.warning(
                                    "Startup: token %s/%s invalid, deactivated",
                                    _uid, _label,
                                )
                                try:
                                    user = await self.bot.fetch_user(int(_uid))
                                    if failures >= TOKEN_MAX_FAILURES:
                                        await db.delete_token_by_id(_token_id)
                                        await user.send(embed=token_deleted_embed(_label, _hint, language=_language))
                                    else:
                                        await user.send(embed=token_invalid_embed(_label, _hint, failures, TOKEN_MAX_FAILURES, _language))
                                except Exception:
                                    pass
                                return

                            engine = QuestEngine(
                                api=api,
                                on_progress=on_progress,
                                on_complete=on_complete,
                                on_start=on_start,
                                on_quest_start=on_quest_start,
                                run_mode=quest_mode,
                            )

                            # Register engine for active quest tracking
                            task_manager.register_engine(_uid, _token_id, engine)

                            summary = await engine.run_once()
                            await engine.wait_all()

                            # Update run times
                            now = datetime.now(timezone.utc)
                            next_run = now + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
                            await db.update_run_times(_token_id, now, next_run)

                            if progress:
                                await progress.finish(summary, next_run)

                            # Save stats
                            completed_names = []
                            newly_completed = 0
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
                                    quest_name = quest_info.get("name", "")
                                    task_type = quest_info.get("task_type", "")
                                    if quest_name:
                                        name_str = f"{quest_name} [{task_type}]" if task_type else quest_name
                                        completed_names.append(name_str)
                                    try:
                                        inserted = await db.save_quest_stat(
                                            token_id=_token_id,
                                            discord_uid=_uid,
                                            quest_id=qid,
                                            quest_name=quest_name,
                                            task_type=quest_info.get("task_type", ""),
                                            duration_secs=0,
                                            run_mode="auto",
                                        )
                                        newly_completed += int(bool(inserted))
                                    except Exception as e:
                                        logger.error("Startup: failed to save quest stat: %s", e)
                            await db.reset_token_failures(_token_id)
                            try:
                                await db.increment_global_stat(
                                    "total_quests_done", newly_completed
                                )
                            except Exception as e:
                                logger.error("Startup: failed to increment global stat: %s", e)

                            # Do not send a success notification when nothing completed.
                            if engine.completed_ids and not progress:
                                try:
                                    user = await self.bot.fetch_user(int(_uid))
                                    await user.send(embed=auto_run_embed(
                                        _label, _hint, len(engine.completed_ids), completed_names, next_run,
                                        startup=True, language=_language, quest_mode=quest_mode,
                                    ))
                                except Exception:
                                    pass

                            logger.info(
                                "Startup: completed %s/%s (%d quests)",
                                _uid, _label, len(engine.completed_ids),
                            )
                        except Exception as e:
                            logger.error(
                                "Startup: error %s/%s: %s", _uid, _label, e
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
                        coro_factory=_startup_run,
                        label=f"startup-{label}",
                    )

                    # Small delay between starts to avoid rate limiting
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(
                        "Startup: error starting %s/%s: %s", uid, label, e
                    )

        except Exception as e:
            logger.error("Startup quest check failed: %s", e)
