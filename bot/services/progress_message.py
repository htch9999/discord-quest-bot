"""
Live progress message — Discord embed updater with debouncing.
"""

import asyncio
import time
import discord
from typing import Optional

from bot.config import EMBED_UPDATE_INTERVAL
from bot.utils.logger import get_logger

logger = get_logger("progress_message")

# ── Embed color palette ──────────────────────────────────────────────────────
COLOR_RUNNING = 0x5865F2   # Blurple
COLOR_SUCCESS = 0x57F287   # Green
COLOR_ERROR   = 0xED4245   # Red
COLOR_WAITING = 0xFEE75C   # Yellow


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
    ):
        self.channel = channel
        self.token_hint = token_hint
        self.user_name = user_name
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
        embed = self._build_embed()
        self.message = await self.channel.send(embed=embed)
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
                    embed = self._build_embed()
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
    ):
        """Update progress for a quest (called by quest engine callback)."""
        self._quests[quest_id] = {
            "name": name,
            "task_type": task_type,
            "done": done,
            "total": total,
            "status": "running",
        }
        self._dirty = True

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

    async def finish(self, summary: Optional[dict] = None):
        """Send the final embed and stop updating."""
        self._finished = True
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()

        if self.message:
            try:
                embed = self._build_final_embed(summary)
                await self.message.edit(embed=embed)
            except discord.HTTPException as e:
                logger.warning("Failed to send final embed: %s", e)

    async def finish_error(self, error_msg: str):
        """Send error embed and stop."""
        self._finished = True
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()

        embed = discord.Embed(
            title="❌ Lỗi",
            description=error_msg,
            color=COLOR_ERROR,
        )
        if self.message:
            try:
                await self.message.edit(embed=embed)
            except discord.HTTPException:
                pass

    # ── Embed builders ───────────────────────────────────────────────────────

    def _build_embed(self) -> discord.Embed:
        elapsed = int(time.time() - self._started_at)
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

        embed = discord.Embed(
            title="🎮 Discord Quest Auto-Completer",
            color=COLOR_RUNNING,
        )
        embed.add_field(
            name="Token", value=f"`...{self.token_hint}`", inline=True
        )
        embed.add_field(
            name="⏱️ Thời gian chạy", value=time_str, inline=True
        )

        # Quest list
        if self._quests:
            total_quests = len(self._quests)
            done_count = sum(1 for q in self._quests.values() if q["status"] == "done")

            lines = []
            for qid, q in self._quests.items():
                if q["status"] == "done":
                    icon = "✅"
                    pct = "100%"
                elif q["total"] > 0:
                    icon = "▶️"
                    p = (q["done"] / q["total"]) * 100
                    pct = f"{p:.0f}%"
                else:
                    icon = "○"
                    pct = "0%"

                task_tag = f"[{q['task_type']}]"
                lines.append(f"{icon} {q['name']} {task_tag} {pct}")

            embed.add_field(
                name=f"📋 Danh sách quest ({done_count}/{total_quests})",
                value="\n".join(lines) or "Không có quest",
                inline=False,
            )

            embed.add_field(
                name="📊 Tiến độ",
                value=f"{done_count}/{total_quests} hoàn thành",
                inline=True,
            )
        else:
            embed.add_field(
                name="📋 Danh sách quest",
                value="Đang tải...",
                inline=False,
            )

        embed.set_footer(text="CTDOTEAM — Discord Quest Bot")
        return embed

    def _build_final_embed(self, summary: Optional[dict] = None) -> discord.Embed:
        elapsed = int(time.time() - self._started_at)
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

        total_quests = len(self._quests)
        done_count = sum(1 for q in self._quests.values() if q["status"] == "done")

        embed = discord.Embed(
            title="✅ Hoàn thành!",
            description=f"Đã xử lý xong **{done_count}/{total_quests}** quest.",
            color=COLOR_SUCCESS,
        )
        embed.add_field(name="Token", value=f"`...{self.token_hint}`", inline=True)
        embed.add_field(name="⏱️ Tổng thời gian", value=time_str, inline=True)

        # Final quest list
        lines = []
        for qid, q in self._quests.items():
            icon = "✅" if q["status"] == "done" else "❌"
            dur = q.get("duration", 0)
            dur_str = f" ({dur}s)" if dur else ""
            lines.append(f"{icon} {q['name']} [{q['task_type']}]{dur_str}")

        if lines:
            embed.add_field(
                name="📋 Kết quả",
                value="\n".join(lines),
                inline=False,
            )

        if summary:
            stats_lines = []
            if "total" in summary:
                stats_lines.append(f"Tổng quest: {summary['total']}")
            if "completed_now" in summary:
                stats_lines.append(f"Hoàn thành lần này: {summary['completed_now']}")
            if stats_lines:
                embed.add_field(
                    name="📊 Thống kê",
                    value="\n".join(stats_lines),
                    inline=False,
                )

        embed.set_footer(text="CTDOTEAM — Discord Quest Bot")
        return embed
