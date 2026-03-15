"""
/quests slash command — run quest completion once (no token storage).
"""

import discord
from discord import app_commands
from discord.ext import commands
import re

from bot.core.discord_api import DiscordAPI, fetch_latest_build_number
from bot.core.quest_engine import QuestEngine
from bot.core.task_manager import TaskManager
from bot.services.progress_message import ProgressMessage
from bot.utils.token_mask import mask_token
from bot.utils.logger import get_logger

logger = get_logger("cog.quests")

# Basic token format validation
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]{50,}$")


class QuestsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="quests",
        description="Chạy auto-complete quest một lần (token không được lưu)",
    )
    @app_commands.describe(token="Discord user token của bạn")
    async def quests(self, interaction: discord.Interaction, token: str):
        """Run quest auto-completer once without saving the token."""
        uid = str(interaction.user.id)
        hint = token[-4:] if len(token) > 4 else token

        # Ephemeral reply immediately (hide token from channel)
        await interaction.response.send_message(
            f"⏳ Đang xử lý quest cho token `...{hint}`...\n"
            "Kết quả sẽ được gửi qua DM.",
            ephemeral=True,
        )

        # Validate token format
        if not TOKEN_PATTERN.match(token):
            await interaction.followup.send(
                "❌ Token không đúng định dạng.", ephemeral=True
            )
            return

        # Check task manager
        task_manager: TaskManager = self.bot.task_manager
        if task_manager.is_running(uid, "once"):
            await interaction.followup.send(
                "⚠️ Bạn đã có một task đang chạy. Vui lòng đợi hoàn thành.",
                ephemeral=True,
            )
            return

        # Try to DM the user
        try:
            dm_channel = await interaction.user.create_dm()
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Không thể gửi DM. Hãy bật DM từ server này.",
                ephemeral=True,
            )
            return

        # Run quest completion in background
        async def _run_quests():
            progress = ProgressMessage(
                channel=dm_channel,
                token_hint=hint,
                user_name=interaction.user.display_name,
            )

            try:
                # Get build number
                build_number = await fetch_latest_build_number()
                api = DiscordAPI(token, build_number)

                # Validate token
                if not await api.validate_token():
                    await dm_channel.send("❌ Token không hợp lệ hoặc đã hết hạn.")
                    await api.close()
                    return

                # Create progress message
                await progress.start()

                # Create engine with progress callbacks
                engine = QuestEngine(
                    api=api,
                    on_progress=lambda qid, name, tt, done, total: _on_progress(
                        progress, qid, name, tt, done, total
                    ),
                    on_complete=lambda qid, name, tt, dur: _on_complete(
                        progress, qid, name, tt, dur
                    ),
                )

                # Run
                summary = await engine.run_once()
                await engine.wait_all()

                # Finish
                await progress.finish(summary)

                # Save stats to DB
                db = self.bot.db
                for qid in engine.completed_ids:
                    quest_info = next(
                        (q for q in summary.get("quests", []) if q["id"] == qid),
                        None,
                    )
                    if quest_info:
                        await db.save_quest_stat(
                            token_id=None,
                            discord_uid=uid,
                            quest_id=qid,
                            quest_name=quest_info.get("name", ""),
                            task_type=quest_info.get("task_type", ""),
                            duration_secs=0,
                            run_mode="once",
                        )
                await db.increment_global_stat(
                    "total_quests_done", len(engine.completed_ids)
                )

            except Exception as e:
                logger.error("Quest run failed for %s: %s", uid, e)
                await progress.finish_error(f"Lỗi: {e}")
            finally:
                try:
                    await api.close()
                except Exception:
                    pass

        # Start via task manager
        started = await task_manager.start_task(
            uid=uid,
            token_id="once",
            coro_factory=_run_quests,
            label="quests-once",
        )
        if not started:
            await interaction.followup.send(
                "⚠️ Không thể bắt đầu task.", ephemeral=True
            )


async def _on_progress(
    progress: ProgressMessage,
    qid: str,
    name: str,
    task_type: str,
    done: float,
    total: float,
):
    progress.update_quest(qid, name, task_type, done, total)


async def _on_complete(
    progress: ProgressMessage,
    qid: str,
    name: str,
    task_type: str,
    duration: int,
):
    progress.mark_complete(qid, name, task_type, duration)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuestsCog(bot))
