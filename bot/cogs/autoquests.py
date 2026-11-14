"""
/autoquests slash commands — save token, auto-schedule, manage tokens.
"""

import discord
from discord import app_commands
from discord.ext import commands
import re
from datetime import datetime, timezone, timedelta

from bot.core.discord_api import DiscordAPI, fetch_latest_build_number
from bot.core.quest_engine import (
    QuestEngine,
    get_quest_name,
    get_task_type,
    get_seconds_needed,
)
from bot.core.task_manager import TaskManager
from bot.services.crypto import encrypt_token, decrypt_token, get_token_hint
from bot.services.progress_message import ProgressMessage
from bot.db.database import Database
from bot.utils.formatter import (
    token_list_embed,
    success_embed,
    error_embed,
    warning_embed,
    token_invalid_embed,
    token_deleted_embed,
)
from bot.utils.logger import get_logger
from bot.utils.i18n import tr, mode_text
from bot.config import AUTO_RUN_INTERVAL_DAYS, TOKEN_MAX_FAILURES

logger = get_logger("cog.autoquests")

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]{50,}$")


class AutoQuestsCog(commands.Cog):
    autoquests_group = app_commands.Group(
        name="autoquests",
        description="Save tokens and configure automatic quest runs",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /autoquests save ─────────────────────────────────────────────────────

    @autoquests_group.command(
        name="save",
        description="Save a token and automatically run quests every two days",
    )
    @app_commands.describe(
        token="Your Discord user token",
        label="A name for this token (default: 'default')",
    )
    async def autoquests_save(
        self,
        interaction: discord.Interaction,
        token: str,
        label: str = "default",
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        hint = get_token_hint(token)

        await interaction.response.send_message(
            tr(language, "working", hint=hint), ephemeral=True
        )

        # Track user interaction
        db: Database = self.bot.db
        await db.track_user(uid)

        if not TOKEN_PATTERN.match(token):
            await interaction.followup.send(
                embed=error_embed(tr(language, "bad_token_format"), language), ephemeral=True
            )
            return

        db: Database = self.bot.db

        # Check duplicate label
        existing = await db.get_token_by_label(uid, label)
        if existing:
            await interaction.followup.send(
                embed=warning_embed(
                    tr(language, "duplicate_label", label=label), language
                ),
                ephemeral=True,
            )
            return

        # Validate token
        build_number = await fetch_latest_build_number()
        api = DiscordAPI(token, build_number)
        try:
            valid, status = await api.validate_token_status()
        finally:
            await api.close()

        if not valid:
            message = tr(language, "invalid_token") if status == 401 else tr(language, "temporary_validation")
            await interaction.followup.send(
                embed=error_embed(message, language),
                ephemeral=True,
            )
            return

        # Encrypt & save
        encrypted = encrypt_token(token, uid)
        next_run = datetime.now(timezone.utc) + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
        token_id = await db.save_token(
            discord_uid=uid,
            label=label,
            token_enc=encrypted.encode("utf-8"),
            token_hint=token[-4:],
            next_run_at=next_run,
        )

        await interaction.followup.send(
            embed=success_embed(
                tr(language, "token_saved", hint=hint, label=label, timestamp=int(next_run.timestamp()))
            ),
            ephemeral=True,
        )

        # Run immediately in background
        try:
            dm_channel = await interaction.user.create_dm()
            await self._run_token(uid, token_id, token, label, hint, dm_channel)
        except discord.HTTPException:
            logger.warning("Cannot DM user %s for first run", uid)

    @autoquests_group.command(
        name="mode",
        description="Choose sequential or parallel quest execution",
    )
    @app_commands.describe(mode="Execution mode for future quest runs")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Single", value="single"),
            app_commands.Choice(name="Multi", value="multi"),
        ]
    )
    async def autoquests_mode(
        self,
        interaction: discord.Interaction,
        mode: app_commands.Choice[str],
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        await self.bot.db.track_user(uid)
        await self.bot.db.set_user_quest_mode(uid, mode.value)
        mode_name = mode_text(language, mode.value)
        await interaction.response.send_message(
            embed=success_embed(tr(language, "mode_saved", mode=mode_name), language),
            ephemeral=True,
        )

    # ── /autoquests-list ─────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-list",
        description="List your saved tokens",
    )
    async def autoquests_list(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        language = await db.get_user_language(uid)
        tokens = await db.get_tokens(uid)
        embed = token_list_embed(tokens, language)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /autoquests-remove ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-remove",
        description="Remove a saved token",
    )
    @app_commands.describe(label="Token label to remove")
    async def autoquests_remove(
        self, interaction: discord.Interaction, label: str
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        db: Database = self.bot.db

        removed = await db.remove_token(uid, label)
        if removed:
            await interaction.response.send_message(
                embed=success_embed(tr(language, "token_removed", label=label), language),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "token_not_found", label=label), language),
                ephemeral=True,
            )

    # ── /autoquests-rename ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-rename",
        description="Rename a saved token",
    )
    @app_commands.describe(label="Current label", new_label="New label")
    async def autoquests_rename(
        self, interaction: discord.Interaction, label: str, new_label: str
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        db: Database = self.bot.db

        renamed = await db.rename_token(uid, label, new_label)
        if renamed:
            await interaction.response.send_message(
                embed=success_embed(tr(language, "token_renamed", old=label, new=new_label), language),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "token_not_found", label=label), language),
                ephemeral=True,
            )

    # ── /autoquests-status ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-status",
        description="View saved token status",
    )
    @app_commands.describe(label="Token label (leave empty for all)")
    async def autoquests_status(
        self, interaction: discord.Interaction, label: str = ""
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        db: Database = self.bot.db

        if label:
            token_data = await db.get_token_by_label(uid, label)
            if not token_data:
                await interaction.response.send_message(
                    embed=error_embed(tr(language, "token_not_found", label=label), language),
                    ephemeral=True,
                )
                return
            tokens = [token_data]
        else:
            tokens = await db.get_tokens(uid)

        if not tokens:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "no_tokens"), language), ephemeral=True
            )
            return

        task_manager: TaskManager = self.bot.task_manager
        user_stats = await db.get_user_stats(uid)
        quest_mode = await db.get_user_quest_mode(uid)
        mode_name = mode_text(language, quest_mode, include_hint=True)

        embed = discord.Embed(title=tr(language, "status"), color=0x5865F2)
        embed.add_field(
            name=tr(language, "quests_done"),
            value=str(user_stats.get("total", 0)),
            inline=True,
        )
        embed.add_field(
            name=tr(language, "mode_label"),
            value=mode_name,
            inline=True,
        )

        for t in tokens:
            active = tr(language, "active") if t.get("is_active") else tr(language, "paused")
            running = tr(language, "running") if task_manager.is_running(uid, t["id"]) else ""
            hint = t.get("token_hint", "????")

            last_run = tr(language, "never")
            if t.get('last_run_at'):
                try:
                    lr_dt = datetime.fromisoformat(str(t['last_run_at']))
                    last_run = f"<t:{int(lr_dt.timestamp())}:R>"
                except Exception:
                    last_run = str(t['last_run_at'])

            next_run = tr(language, "not_available")
            if t.get('next_run_at'):
                try:
                    nr_dt = datetime.fromisoformat(str(t['next_run_at']))
                    next_run = f"<t:{int(nr_dt.timestamp())}:R>"
                except Exception:
                    next_run = str(t['next_run_at'])

            embed.add_field(
                name=f"{t['label']} (`...{hint}`)",
                value=(
                    f"{tr(language, 'status')}: {active}{f' ({running})' if running else ''}\n"
                    f"{tr(language, 'last_run')}: {last_run}\n"
                    f"{tr(language, 'next_run_short')}: {next_run}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /autoquests-run ──────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-run",
        description="Run quests now without waiting for the schedule",
    )
    @app_commands.describe(label="Token label to run")
    async def autoquests_run(
        self, interaction: discord.Interaction, label: str = "default"
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        db: Database = self.bot.db

        token_data = await db.get_token_by_label(uid, label)
        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "token_not_found", label=label), language),
                ephemeral=True,
            )
            return

        if not token_data.get("is_active"):
            await interaction.response.send_message(
                embed=warning_embed(tr(language, "token_paused", label=label), language),
                ephemeral=True,
            )
            return

        quest_mode = await db.get_user_quest_mode(uid)
        mode_name = mode_text(language, quest_mode, include_hint=True)
        await interaction.response.send_message(
            f"{tr(language, 'run_start', label=label)}\n"
            f"{tr(language, 'mode_label')}: {mode_name}",
            ephemeral=True,
        )

        # Decrypt token
        token = decrypt_token(
            token_data["token_enc"].decode("utf-8")
            if isinstance(token_data["token_enc"], bytes)
            else token_data["token_enc"],
            uid,
        )
        hint = token_data.get("token_hint", "????")

        try:
            dm_channel = await interaction.user.create_dm()
            await self._run_token(uid, token_data["id"], token, label, hint, dm_channel)
        except discord.HTTPException:
            await interaction.followup.send(
                embed=error_embed(tr(language, "dm_disabled"), language),
                ephemeral=True,
            )

    # ── /autoquests-pause ────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-pause",
        description="Pause automatic runs for a token",
    )
    @app_commands.describe(label="Token label")
    async def autoquests_pause(
        self, interaction: discord.Interaction, label: str = "default"
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        db: Database = self.bot.db

        token_data = await db.get_token_by_label(uid, label)
        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "token_not_found", label=label), language),
                ephemeral=True,
            )
            return

        await db.set_token_active(token_data["id"], False)
        await interaction.response.send_message(
            embed=success_embed(tr(language, "schedule_paused", label=label), language),
            ephemeral=True,
        )

    # ── /autoquests-resume ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-resume",
        description="Resume automatic runs for a token",
    )
    @app_commands.describe(label="Token label")
    async def autoquests_resume(
        self, interaction: discord.Interaction, label: str = "default"
    ):
        uid = str(interaction.user.id)
        language = await self.bot.db.get_user_language(uid)
        db: Database = self.bot.db

        token_data = await db.get_token_by_label(uid, label)
        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "token_not_found", label=label), language),
                ephemeral=True,
            )
            return

        next_run = datetime.now(timezone.utc) + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
        await db.set_token_active(token_data["id"], True)
        await db.update_run_times(
            token_data["id"],
            last_run=datetime.now(timezone.utc),
            next_run=next_run,
        )
        await interaction.response.send_message(
            embed=success_embed(
                tr(language, "schedule_resumed", label=label, timestamp=int(next_run.timestamp()))
            ),
            ephemeral=True,
        )

    # ── Helper: run a saved token ────────────────────────────────────────────

    async def _run_token(
        self,
        uid: str,
        token_id: int,
        token: str,
        label: str,
        hint: str,
        dm_channel: discord.DMChannel,
    ):
        task_manager: TaskManager = self.bot.task_manager
        db: Database = self.bot.db
        language = await db.get_user_language(uid)

        async def _task():
            quest_mode = await db.get_user_quest_mode(uid)
            progress = ProgressMessage(
                channel=dm_channel,
                token_hint=hint,
                user_name="",
                language=language,
                quest_mode=quest_mode,
            )
            api = None
            try:
                build_number = await fetch_latest_build_number()
                api = DiscordAPI(token, build_number)

                valid, status = await api.validate_token_status()
                if not valid:
                    if status != 401:
                        await dm_channel.send(
                            embed=error_embed(
                                tr(language, "temporary_validation"), language
                            )
                        )
                        return

                    failures = await db.record_token_failure(token_id)
                    await db.set_token_active(token_id, False)
                    if failures >= TOKEN_MAX_FAILURES:
                        await db.delete_token_by_id(token_id)
                        logger.warning(
                            "Token %s/%s auto-removed after %d failed checks",
                            uid, label, failures,
                        )
                        await dm_channel.send(
                            embed=token_deleted_embed(
                                label, hint,
                                language=language,
                            )
                        )
                    else:
                        await dm_channel.send(
                            embed=token_invalid_embed(
                                label, hint, failures, TOKEN_MAX_FAILURES, language,
                            )
                        )
                    return

                await db.reset_token_failures(token_id)

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
                task_manager.register_engine(uid, token_id, engine)

                summary = await engine.run_once()
                await engine.wait_all()

                # Update run times
                now = datetime.now(timezone.utc)
                next_run = now + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
                await db.update_run_times(token_id, now, next_run)
                await progress.finish(summary, next_run)

                # Save stats
                newly_completed = 0
                for qid in engine.completed_ids:
                    quest_info = next(
                        (q for q in summary.get("quests", []) if q["id"] == qid),
                        None,
                    )
                    if quest_info:
                        try:
                            inserted = await db.save_quest_stat(
                                token_id=token_id,
                                discord_uid=uid,
                                quest_id=qid,
                                quest_name=quest_info.get("name", ""),
                                task_type=quest_info.get("task_type", ""),
                                duration_secs=0,
                                run_mode="auto",
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
                logger.error("Auto-quest run failed for %s/%s: %s", uid, label, e)
                await progress.finish_error(tr(language, "run_failed"))
            finally:
                if api:
                    try:
                        await api.close()
                    except Exception:
                        pass

        await task_manager.start_task(
            uid=uid, token_id=token_id, coro_factory=_task, label=label
        )


async def _on_progress(progress, qid, name, tt, done, total):
    progress.update_quest(qid, name, tt, done, total)


async def _on_complete(progress, qid, name, tt, dur):
    progress.mark_complete(qid, name, tt, dur)


async def _on_quest_start(progress, qid, name, task_type):
    progress.mark_running(qid, name, task_type)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoQuestsCog(bot))
