"""
/autoquests slash commands — save token, auto-schedule, manage tokens.
"""

import discord
from discord import app_commands
from discord.ext import commands
import re
from datetime import datetime, timezone, timedelta

from bot.core.discord_api import DiscordAPI, fetch_latest_build_number
from bot.core.quest_engine import QuestEngine
from bot.core.task_manager import TaskManager
from bot.services.crypto import encrypt_token, decrypt_token, get_token_hint
from bot.services.progress_message import ProgressMessage
from bot.db.database import Database
from bot.utils.formatter import token_list_embed, success_embed, error_embed, warning_embed
from bot.utils.logger import get_logger
from bot.config import AUTO_RUN_INTERVAL_DAYS

logger = get_logger("cog.autoquests")

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]{50,}$")


class AutoQuestsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /autoquests save ─────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests",
        description="Lưu token và tự động chạy quest mỗi 2 ngày",
    )
    @app_commands.describe(
        token="Discord user token của bạn",
        label="Tên gợi nhớ cho token (mặc định: 'default')",
    )
    async def autoquests(
        self,
        interaction: discord.Interaction,
        token: str,
        label: str = "default",
    ):
        uid = str(interaction.user.id)
        hint = get_token_hint(token)

        await interaction.response.send_message(
            f"⏳ Đang xử lý token `{hint}`...", ephemeral=True
        )

        if not TOKEN_PATTERN.match(token):
            await interaction.followup.send(
                embed=error_embed("Token không đúng định dạng."), ephemeral=True
            )
            return

        db: Database = self.bot.db

        # Check duplicate label
        existing = await db.get_token_by_label(uid, label)
        if existing:
            await interaction.followup.send(
                embed=warning_embed(
                    f"Label `{label}` đã tồn tại. Dùng label khác hoặc "
                    f"`/autoquests-remove` để xóa trước."
                ),
                ephemeral=True,
            )
            return

        # Validate token
        build_number = await fetch_latest_build_number()
        api = DiscordAPI(token, build_number)
        valid = await api.validate_token()
        await api.close()

        if not valid:
            await interaction.followup.send(
                embed=error_embed("Token không hợp lệ hoặc đã hết hạn."),
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
                f"Đã lưu token `{hint}` với tên **{label}**.\n"
                f"Lần chạy tự động tiếp theo: <t:{int(next_run.timestamp())}:R>"
            ),
            ephemeral=True,
        )

        # Run immediately in background
        try:
            dm_channel = await interaction.user.create_dm()
            await self._run_token(uid, token_id, token, label, hint, dm_channel)
        except discord.HTTPException:
            logger.warning("Cannot DM user %s for first run", uid)

    # ── /autoquests-list ─────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-list",
        description="Xem danh sách token đã lưu",
    )
    async def autoquests_list(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        tokens = await db.get_tokens(uid)
        embed = token_list_embed(tokens)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /autoquests-remove ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-remove",
        description="Xóa token đã lưu",
    )
    @app_commands.describe(label="Tên token cần xóa")
    async def autoquests_remove(
        self, interaction: discord.Interaction, label: str
    ):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        removed = await db.remove_token(uid, label)
        if removed:
            await interaction.response.send_message(
                embed=success_embed(f"Đã xóa token **{label}**."),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token với label `{label}`."),
                ephemeral=True,
            )

    # ── /autoquests-rename ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-rename",
        description="Đổi tên token đã lưu",
    )
    @app_commands.describe(label="Tên hiện tại", new_label="Tên mới")
    async def autoquests_rename(
        self, interaction: discord.Interaction, label: str, new_label: str
    ):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        renamed = await db.rename_token(uid, label, new_label)
        if renamed:
            await interaction.response.send_message(
                embed=success_embed(f"Đã đổi tên **{label}** → **{new_label}**."),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token với label `{label}`."),
                ephemeral=True,
            )

    # ── /autoquests-status ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-status",
        description="Xem trạng thái token",
    )
    @app_commands.describe(label="Tên token (để trống = tất cả)")
    async def autoquests_status(
        self, interaction: discord.Interaction, label: str = ""
    ):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        if label:
            token_data = await db.get_token_by_label(uid, label)
            if not token_data:
                await interaction.response.send_message(
                    embed=error_embed(f"Không tìm thấy token `{label}`."),
                    ephemeral=True,
                )
                return
            tokens = [token_data]
        else:
            tokens = await db.get_tokens(uid)

        if not tokens:
            await interaction.response.send_message(
                embed=error_embed("Chưa có token nào."), ephemeral=True
            )
            return

        task_manager: TaskManager = self.bot.task_manager
        user_stats = await db.get_user_stats(uid)

        embed = discord.Embed(title="📊 Trạng thái", color=0x5865F2)
        embed.add_field(
            name="Tổng quest đã hoàn thành",
            value=str(user_stats.get("total", 0)),
            inline=True,
        )

        for t in tokens:
            active = "🟢 Active" if t.get("is_active") else "🔴 Paused"
            running = "▶️ Đang chạy" if task_manager.is_running(uid, t["id"]) else ""
            hint = t.get("token_hint", "????")

            embed.add_field(
                name=f"{t['label']} (`...{hint}`)",
                value=(
                    f"Trạng thái: {active} {running}\n"
                    f"Lần chạy cuối: {t.get('last_run_at', 'Chưa')}\n"
                    f"Lần chạy tiếp: {t.get('next_run_at', 'N/A')}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /autoquests-run ──────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-run",
        description="Chạy quest thủ công ngay (không chờ lịch)",
    )
    @app_commands.describe(label="Tên token cần chạy")
    async def autoquests_run(
        self, interaction: discord.Interaction, label: str = "default"
    ):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        token_data = await db.get_token_by_label(uid, label)
        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token `{label}`."),
                ephemeral=True,
            )
            return

        if not token_data.get("is_active"):
            await interaction.response.send_message(
                embed=warning_embed(f"Token `{label}` đang bị tạm dừng. Dùng `/autoquests-resume` trước."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"⏳ Đang chạy quest cho **{label}**...", ephemeral=True
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
                embed=error_embed("Không thể gửi DM. Hãy bật DM từ server."),
                ephemeral=True,
            )

    # ── /autoquests-pause ────────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-pause",
        description="Tạm dừng auto-schedule cho token",
    )
    @app_commands.describe(label="Tên token")
    async def autoquests_pause(
        self, interaction: discord.Interaction, label: str = "default"
    ):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        token_data = await db.get_token_by_label(uid, label)
        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token `{label}`."),
                ephemeral=True,
            )
            return

        await db.set_token_active(token_data["id"], False)
        await interaction.response.send_message(
            embed=success_embed(f"Đã tạm dừng auto-schedule cho **{label}**."),
            ephemeral=True,
        )

    # ── /autoquests-resume ───────────────────────────────────────────────────

    @app_commands.command(
        name="autoquests-resume",
        description="Bật lại auto-schedule cho token",
    )
    @app_commands.describe(label="Tên token")
    async def autoquests_resume(
        self, interaction: discord.Interaction, label: str = "default"
    ):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        token_data = await db.get_token_by_label(uid, label)
        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token `{label}`."),
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
                f"Đã bật lại auto-schedule cho **{label}**.\n"
                f"Lần chạy tiếp: <t:{int(next_run.timestamp())}:R>"
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

        async def _task():
            progress = ProgressMessage(
                channel=dm_channel, token_hint=hint, user_name=""
            )
            api = None
            try:
                build_number = await fetch_latest_build_number()
                api = DiscordAPI(token, build_number)

                if not await api.validate_token():
                    await db.set_token_active(token_id, False)
                    await dm_channel.send(
                        f"❌ Token **{label}** (`...{hint}`) không hợp lệ. "
                        "Auto-schedule đã bị tắt."
                    )
                    return

                await progress.start()

                engine = QuestEngine(
                    api=api,
                    on_progress=lambda qid, name, tt, done, total: _on_progress(
                        progress, qid, name, tt, done, total
                    ),
                    on_complete=lambda qid, name, tt, dur: _on_complete(
                        progress, qid, name, tt, dur
                    ),
                )

                summary = await engine.run_once()
                await engine.wait_all()
                await progress.finish(summary)

                # Update run times
                now = datetime.now(timezone.utc)
                next_run = now + timedelta(days=AUTO_RUN_INTERVAL_DAYS)
                await db.update_run_times(token_id, now, next_run)

                # Save stats
                for qid in engine.completed_ids:
                    quest_info = next(
                        (q for q in summary.get("quests", []) if q["id"] == qid),
                        None,
                    )
                    if quest_info:
                        await db.save_quest_stat(
                            token_id=token_id,
                            discord_uid=uid,
                            quest_id=qid,
                            quest_name=quest_info.get("name", ""),
                            task_type=quest_info.get("task_type", ""),
                            duration_secs=0,
                            run_mode="auto",
                        )
                await db.increment_global_stat(
                    "total_quests_done", len(engine.completed_ids)
                )

            except Exception as e:
                logger.error("Auto-quest run failed for %s/%s: %s", uid, label, e)
                await progress.finish_error(f"Lỗi: {e}")
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


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoQuestsCog(bot))
