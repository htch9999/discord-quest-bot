"""
Live progress message — Discord embed updater with debouncing.
"""

import asyncio
import time
import discord
from typing import Optional

from bot.config import EMBED_UPDATE_INTERVAL
from bot.utils.logger import get_logger
from bot.utils.i18n import tr, mode_text

logger = get_logger("progress_message")

# ── Embed color palette ──────────────────────────────────────────────────────
COLOR_RUNNING = 0x5865F2   # Blurple
COLOR_SUCCESS = 0x57F287   # Green
COLOR_ERROR   = 0xED4245   # Red
COLOR_WAITING = 0xFEE75C   # Yellow


def _fit_field(lines: list[str], limit: int = 1024) -> str:
    """Keep a multi-line quest list within Discord's embed field value limit."""
    text = "\n".join(lines)
    if len(text) <= limit:
        return text
    prefix = text[: limit - 3].rsplit("\n", 1)[0]
    if not prefix:
        prefix = text[: limit - 3]
    return prefix + "\n…"


class ProgressMessage:
    """
    Manages a single Discord embed message that shows real-time quest progress.

    Debounces edits to avoid Discord rate limits (min interval = EMBED_UPDATE_INTERVAL).
    """

    def __init__(
        self,
        channel: discord.abc.Messageable,
        token_hint: str = "????",
        user_name: str = "Unknown",
        language: str = "en",
        run_mode: str = "manual",
        quest_mode: str = "multi",
    ):
        self.channel = channel
        self.token_hint = token_hint
        self.user_name = user_name
        self.language = language
        self.run_mode = run_mode
        self.quest_mode = quest_mode if quest_mode in {"single", "multi"} else "multi"
        self.message: Optional[discord.Message] = None

        # Quest progress data: {quest_id: {name, task_type, done, total, status}}
        self._quests: dict[str, dict] = {}
        self._started_at: float = time.time()
        self._last_edit: float = 0
        self._dirty: bool = False
        self._update_task: Optional[asyncio.Task] = None
        self._finished: bool = False

    async def start(self):
        """Send the initial embed."""
        embed = self._build_embed(include_mode_hint=True)
        self.message = await self.channel.send(embed=embed)
        self._dirty = False
        self._start_update_loop()
        logger.debug("Progress message sent: %s", self.message.id)

    def _start_update_loop(self):
        if self._update_task is None or self._update_task.done():
            self._update_task = asyncio.create_task(self._update_loop())

    async def _update_loop(self):
        """Background loop: edit the message periodically when dirty."""
        while not self._finished:
            await asyncio.sleep(EMBED_UPDATE_INTERVAL)
            if self._dirty and self.message:
                try:
                    embed = self._build_embed(include_mode_hint=False)
                    await self.message.edit(embed=embed)
                    self._dirty = False
                    self._last_edit = time.time()
                except discord.HTTPException as e:
                    logger.warning("Failed to edit progress message: %s", e)
                except Exception as e:
                    logger.error("Unexpected error editing message: %s", e)

    def update_quest(
        self,
        quest_id: str,
        name: str,
        task_type: str,
        done: float,
        total: float,
        status: str = "running",
    ):
        """Update progress for a quest (called by quest engine callback)."""
        self._quests[quest_id] = {
            "name": name,
            "task_type": task_type,
            "done": done,
            "total": total,
            "status": status if status in {"queued", "running", "done", "failed"} else "running",
        }
        self._dirty = True

    def mark_running(self, quest_id: str, name: str, task_type: str):
        """Mark a queued quest as the currently active quest."""
        existing = self._quests.get(quest_id, {})
        self.update_quest(
            quest_id,
            name,
            task_type,
            existing.get("done", 0),
            existing.get("total", 0),
            status="running",
        )

    def mark_complete(self, quest_id: str, name: str, task_type: str, duration: int):
        """Mark a quest as completed."""
        self._quests[quest_id] = {
            "name": name,
            "task_type": task_type,
            "done": self._quests.get(quest_id, {}).get("total", 0),
            "total": self._quests.get(quest_id, {}).get("total", 0),
            "status": "done",
            "duration": duration,
        }
        self._dirty = True

    async def finish(self, summary: Optional[dict] = None, next_run=None):
        """Send the final embed and stop updating."""
        self._finished = True
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            await asyncio.gather(self._update_task, return_exceptions=True)

        if self.message:
            try:
                embed = self._build_final_embed(summary, next_run)
                await self.message.edit(embed=embed)
            except discord.HTTPException as e:
                logger.warning("Failed to send final embed: %s", e)

    async def finish_error(self, error_msg: str):
        """Send error embed and stop."""
        self._finished = True
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            await asyncio.gather(self._update_task, return_exceptions=True)

        embed = discord.Embed(
            title=tr(self.language, "error"),
            description=error_msg,
            color=COLOR_ERROR,
        )
        if self.message:
            try:
                await self.message.edit(embed=embed)
            except discord.HTTPException:
                pass

    # ── Embed builders ───────────────────────────────────────────────────────

    def _mode_value(self, include_hint: bool = False) -> str:
        return mode_text(self.language, self.quest_mode, include_hint)

    def _build_embed(self, include_mode_hint: bool = False) -> discord.Embed:
        elapsed = int(time.time() - self._started_at)
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

        embed = discord.Embed(
            title=tr(self.language, {
                "scheduled": "auto_progress_title",
                "startup": "startup_progress_title",
            }.get(self.run_mode, "progress_title")),
            color=COLOR_RUNNING,
        )
        embed.add_field(
            name="Token", value=f"`...{self.token_hint}`", inline=True
        )
        embed.add_field(
            name=tr(self.language, "elapsed"), value=time_str, inline=True
        )
        embed.add_field(
            name=tr(self.language, "mode_label"),
            value=self._mode_value(include_mode_hint),
            inline=False,
        )

        # Quest list
        if self._quests:
            total_quests = len(self._quests)
            done_count = sum(1 for q in self._quests.values() if q["status"] == "done")

            lines = []
            for qid, q in self._quests.items():
                if q["status"] == "done":
                    status = "✅"
                    pct = "100%"
                elif q["status"] == "queued":
                    status = tr(self.language, "quest_queued")
                    pct = tr(self.language, "waiting")
                elif q["status"] == "failed":
                    status = "❌"
                    pct = tr(self.language, "quest_failed")
                elif q["total"] > 0:
                    status = tr(self.language, "quest_running")
                    p = (q["done"] / q["total"]) * 100
                    pct = f"{p:.0f}%"
                else:
                    status = tr(self.language, "quest_running")
                    pct = "0%"

                task_tag = f"[{q['task_type']}]"
                if status in {"✅", "❌"}:
                    lines.append(f"{status} {q['name']} {task_tag} {pct}")
                else:
                    lines.append(f"[{status}] {q['name']} {task_tag} {pct}")

            embed.add_field(
                name=tr(self.language, "quest_list", done=done_count, total=total_quests),
                value=_fit_field(lines) or tr(self.language, "no_quests"),
                inline=False,
            )

            embed.add_field(
                name=tr(self.language, "progress"),
                value=f"{done_count}/{total_quests} {tr(self.language, 'completed')}",
                inline=True,
            )
        else:
            embed.add_field(
                name=tr(self.language, "quest_list", done=0, total=0),
                value=tr(self.language, "loading"),
                inline=False,
            )

        embed.set_footer(text="Discord Quest Bot")
        return embed

    def _build_final_embed(self, summary: Optional[dict] = None, next_run=None) -> discord.Embed:
        elapsed = int(time.time() - self._started_at)
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

        total_quests = len(self._quests)
        done_count = sum(1 for q in self._quests.values() if q["status"] == "done")

        final_title_key = {
            "scheduled": "auto_run_title",
            "startup": "startup_run_title",
        }.get(self.run_mode, "finished")
        embed = discord.Embed(
            title=tr(self.language, final_title_key) if done_count else tr(self.language, "no_quests_completed"),
            description=(
                tr(self.language, "processed", done=done_count, total=total_quests)
                if done_count else tr(self.language, "no_quests_completed")
            ),
            color=COLOR_SUCCESS if done_count else COLOR_WAITING,
        )
        embed.add_field(name="Token", value=f"`...{self.token_hint}`", inline=True)
        embed.add_field(name=tr(self.language, "total_time"), value=time_str, inline=True)
        embed.add_field(
            name=tr(self.language, "mode_label"),
            value=self._mode_value(include_hint=True),
            inline=False,
        )

        # Final quest list
        lines = []
        for qid, q in self._quests.items():
            status = "✅" if q["status"] == "done" else "❌"
            dur = q.get("duration", 0)
            dur_str = f" ({dur}s)" if dur else ""
            lines.append(f"{status} {q['name']} [{q['task_type']}]{dur_str}")

        if lines:
            embed.add_field(
                name=tr(self.language, "results"),
                value=_fit_field(lines),
                inline=False,
            )

        if summary:
            stats_lines = []
            if "total" in summary:
                stats_lines.append(f"{tr(self.language, 'total_quests')}: {summary['total']}")
            if "completed_now" in summary:
                stats_lines.append(f"{tr(self.language, 'completed_this_run')}: {summary['completed_now']}")
            if stats_lines:
                embed.add_field(
                    name=tr(self.language, "statistics"),
                    value="\n".join(stats_lines),
                    inline=False,
                )

        if next_run:
            embed.add_field(
                name=tr(self.language, "next_run"),
                value=f"<t:{int(next_run.timestamp())}:R>",
                inline=False,
            )

        embed.set_footer(text="Discord Quest Bot")
        return embed
