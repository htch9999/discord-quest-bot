"""
Task manager — async task isolation with per-user locks and global semaphore.
"""

import asyncio
from typing import Optional, Callable, Awaitable
from datetime import datetime, timezone

from bot.config import MAX_CONCURRENT_TASKS, TASK_TIMEOUT_HOURS
from bot.utils.logger import get_logger

logger = get_logger("task_manager")


class TaskManager:
    """
    Manages concurrent quest-completion tasks.

    - Per-user lock: prevents same user from running 2 tasks on the same token
    - Global semaphore: limits total concurrent tasks across all users
    - Task timeout: cancels tasks exceeding TASK_TIMEOUT_HOURS
    """

    def __init__(self):
        self.running_tasks: dict[str, asyncio.Task] = {}  # "uid:token_id" -> Task
        self.user_locks: dict[str, asyncio.Lock] = {}     # uid -> Lock
        self.global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self._engines: dict[str, object] = {}  # "uid:token_id" -> QuestEngine

    def _task_key(self, uid: str, token_id: int | str) -> str:
        return f"{uid}:{token_id}"

    def _get_user_lock(self, uid: str) -> asyncio.Lock:
        if uid not in self.user_locks:
            self.user_locks[uid] = asyncio.Lock()
        return self.user_locks[uid]

    def is_running(self, uid: str, token_id: int | str) -> bool:
        key = self._task_key(uid, token_id)
        task = self.running_tasks.get(key)
        return task is not None and not task.done()

    def register_engine(self, uid: str, token_id: int | str, engine):
        """Register a QuestEngine for active quest tracking."""
        key = self._task_key(uid, token_id)
        self._engines[key] = engine

    def unregister_engine(self, uid: str, token_id: int | str):
        """Unregister a QuestEngine."""
        key = self._task_key(uid, token_id)
        self._engines.pop(key, None)

    def get_active_quest_count(self) -> int:
        """Get total number of individual quests being processed across all engines."""
        total = 0
        for engine in list(self._engines.values()):
            try:
                total += engine.active_quest_count
            except Exception:
                pass
        return total

    async def start_task(
        self,
        uid: str,
        token_id: int | str,
        coro_factory: Callable[[], Awaitable],
        label: str = "",
    ) -> bool:
        """
        Start a quest-completion task.
        Returns True if started, False if already running for this uid+token_id.
        """
        key = self._task_key(uid, token_id)

        # Check if already running
        if self.is_running(uid, token_id):
            logger.warning("Task already running: %s (%s)", key, label)
            return False

        user_lock = self._get_user_lock(uid)

        async def _wrapped():
            async with self.global_semaphore:
                async with user_lock:
                    try:
                        await asyncio.wait_for(
                            coro_factory(),
                            timeout=TASK_TIMEOUT_HOURS * 3600,
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            "Task timed out after %dh: %s (%s)",
                            TASK_TIMEOUT_HOURS, key, label,
                        )
                    except asyncio.CancelledError:
                        logger.info("Task cancelled: %s (%s)", key, label)
                    except Exception as e:
                        logger.error("Task error %s (%s): %s", key, label, e)
                    finally:
                        self.running_tasks.pop(key, None)
                        self._engines.pop(key, None)

        task = asyncio.create_task(_wrapped())
        self.running_tasks[key] = task
        logger.info("Started task: %s (%s)", key, label)
        return True

    async def cancel_task(self, uid: str, token_id: int | str) -> bool:
        key = self._task_key(uid, token_id)
        task = self.running_tasks.get(key)
        if task and not task.done():
            task.cancel()
            logger.info("Cancelled task: %s", key)
            return True
        return False

    async def cancel_user_tasks(self, uid: str):
        """Cancel all tasks for a given user."""
        cancelled = 0
        for key, task in list(self.running_tasks.items()):
            if key.startswith(f"{uid}:") and not task.done():
                task.cancel()
                cancelled += 1
        if cancelled:
            logger.info("Cancelled %d tasks for user %s", cancelled, uid)

    async def shutdown(self):
        """Cancel all running tasks (used on bot shutdown)."""
        for key, task in list(self.running_tasks.items()):
            if not task.done():
                task.cancel()
        if self.running_tasks:
            await asyncio.gather(
                *self.running_tasks.values(), return_exceptions=True
            )
        self.running_tasks.clear()
        self._engines.clear()
        logger.info("TaskManager shut down")

    def get_status(self) -> dict:
        """Get a summary of running tasks."""
        active = sum(1 for t in self.running_tasks.values() if not t.done())
        active_quests = self.get_active_quest_count()
        return {
            "total_tasks": len(self.running_tasks),
            "active_tasks": active,
            "active_quests": active_quests,
            "max_concurrent": MAX_CONCURRENT_TASKS,
        }

