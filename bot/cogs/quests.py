"""
/quests slash command — run quest completion once (no token storage).
"""

import discord
from discord import app_commands
from discord.ext import commands
import re

from bot.core.discord_api import DiscordAPI, fetch_latest_build_number
from bot.core.quest_engine import (
    QuestEngine,
    get_quest_name,
    get_task_type,
    get_seconds_needed,
)
from bot.core.task_manager import TaskManager
from bot.services.progress_message import ProgressMessage
from bot.db.database import Database
from bot.utils.token_mask import mask_token
from bot.utils.logger import get_logger
from bot.utils.i18n import tr

logger = get_logger("cog.quests")

# Basic token format validation
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]{50,}$")


class QuestsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="quests",
        description="Run quests once without saving your token",
    )
    @app_commands.describe(token="Your Discord user token")
    async def quests(self, interaction: discord.Interaction, token: str):
        """Run quest auto-completer once without saving the token."""
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        hint = token[-4:] if len(token) > 4 else token

        # Ephemeral reply immediately (hide token from channel)
        await interaction.response.send_message(
            tr(language, "working", hint=hint),
            ephemeral=True,
        )

        # Track user interaction
        db: Database = self.bot.db
        await db.track_user(uid)

        # Validate token format
        if not TOKEN_PATTERN.match(token):
            await interaction.followup.send(
                tr(language, "bad_token_format"), ephemeral=True
            )
            return

        # Check task manager
        task_manager: TaskManager = self.bot.task_manager
        if task_manager.is_running(uid, "once"):
            await interaction.followup.send(
                tr(language, "already_running"),
                ephemeral=True,
            )
            return

        # Try to DM the user
        try:
            dm_channel = await interaction.user.create_dm()
        except discord.HTTPException:
            await interaction.followup.send(
                tr(language, "dm_disabled"),
                ephemeral=True,
            )
            return

        # Run quest completion in background
        async def _run_quests():
            db = self.bot.db
            quest_mode = await db.get_user_quest_mode(uid)
            progress = ProgressMessage(
                channel=dm_channel,
                token_hint=hint,
                user_name=interaction.user.display_name,
                language=language,
                quest_mode=quest_mode,
            )

            try:
                # Get build number
                build_number = await fetch_latest_build_number()
                api = DiscordAPI(token, build_number)

                # Validate token
                valid, status = await api.validate_token_status()
                if not valid:
                    await dm_channel.send(embed=discord.Embed(
                        title=tr(language, "error"),
                        description=tr(
                            language,
                            "invalid_token" if status == 401 else "temporary_validation",
                        ),
                        color=0xED4245,
                    ))
                    await api.close()
                    return

                # Create progress message
                await progress.start()

                async def on_start(actionable):
                    for quest in actionable:
                        progress.update_quest(
                            str(quest.get("id")),
                            get_quest_name(quest),
                            get_task_type(quest) or "Quest",
                            0,
                            get_seconds_needed(quest),
                            status="queued",
                        )

                # Create engine with progress callbacks
                engine = QuestEngine(
                    api=api,
                    on_progress=lambda qid, name, tt, done, total: _on_progress(
                        progress, qid, name, tt, done, total
                    ),
                    on_complete=lambda qid, name, tt, dur: _on_complete(
                        progress, qid, name, tt, dur
                    ),
                    on_start=on_start,
                    on_quest_start=lambda qid, name, tt: _on_quest_start(
                        progress, qid, name, tt
                    ),
                    run_mode=quest_mode,
                )

                # Register engine for active quest tracking
                task_manager.register_engine(uid, "once", engine)

                # Run
                summary = await engine.run_once()
                await engine.wait_all()

                # Finish
                await progress.finish(summary)

                # Save stats to DB
                newly_completed = 0
                for qid in engine.completed_ids:
                    quest_info = next(
                        (q for q in summary.get("quests", []) if q["id"] == qid),
                        None,
                    )
                    if quest_info:
                        try:
                            inserted = await db.save_quest_stat(
                                token_id=None,
                                discord_uid=uid,
                                quest_id=qid,
                                quest_name=quest_info.get("name", ""),
                                task_type=quest_info.get("task_type", ""),
                                duration_secs=0,
                                run_mode="once",
                            )
                            newly_completed += int(bool(inserted))
                        except Exception as e:
                            logger.error("Failed to save quest stat: %s", e)
                try:
                    await db.increment_global_stat(
                        "total_quests_done", newly_completed
                    )
                except Exception as e:
                    logger.error("Failed to increment global stat: %s", e)

            except Exception as e:
                logger.error("Quest run failed for %s: %s", uid, e)
                await progress.finish_error(tr(language, "run_failed"))
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
                tr(language, "could_not_start"), ephemeral=True
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


async def _on_quest_start(
    progress: ProgressMessage,
    qid: str,
    name: str,
    task_type: str,
):
    progress.mark_running(qid, name, task_type)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuestsCog(bot))
