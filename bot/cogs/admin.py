"""
Admin commands — bot management (owner only).
"""

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.database import Database
from bot.core.task_manager import TaskManager
from bot.utils.formatter import success_embed, error_embed
from bot.utils.logger import get_logger
from bot.utils.i18n import tr

logger = get_logger("cog.admin")


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        app_info = await self.bot.application_info()
        return interaction.user.id == app_info.owner.id

    @app_commands.command(
        name="admin-stats",
        description="[Admin] View system statistics",
    )
    async def admin_stats(self, interaction: discord.Interaction):
        language = await self.bot.db.get_user_language(str(interaction.user.id))
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                embed=error_embed(tr(language, "admin_denied"), language), ephemeral=True
            )
            return

        db: Database = self.bot.db
        task_manager: TaskManager = self.bot.task_manager

        total_users = await db.count_unique_users()
        total_quests = await db.count_total_quests_done()
        task_status = task_manager.get_status()

        embed = discord.Embed(title="Admin statistics" if language == "en" else "Thống kê quản trị", color=0xED4245)
        embed.add_field(name="Unique Users", value=str(total_users), inline=True)
        embed.add_field(name="Total Quests Done", value=str(total_quests), inline=True)
        embed.add_field(
            name=tr(language, "running_tasks"),
            value=f"{task_status['active_tasks']}/{task_status['max_concurrent']}",
            inline=True,
        )
        embed.add_field(name=tr(language, "guilds"), value=str(len(self.bot.guilds)), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="admin-force-run",
        description="[Admin] Run quests for a specific user",
    )
    @app_commands.describe(user_id="Discord user ID", label="Token label")
    async def admin_force_run(
        self,
        interaction: discord.Interaction,
        user_id: str,
        label: str = "default",
    ):
        language = await self.bot.db.get_user_language(str(interaction.user.id))
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                embed=error_embed(tr(language, "admin_denied"), language), ephemeral=True
            )
            return

        db: Database = self.bot.db
        token_data = await db.get_token_by_label(user_id, label)

        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "admin_missing_token", uid=user_id, label=label), language),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed(tr(language, "admin_running", uid=user_id, label=label), language),
            ephemeral=True,
        )

        logger.info("Admin force-run: %s/%s", user_id, label)
        try:
            from bot.services.crypto import decrypt_token

            user = await self.bot.fetch_user(int(user_id))
            dm_channel = await user.create_dm()
            encrypted = token_data["token_enc"]
            if isinstance(encrypted, bytes):
                encrypted = encrypted.decode("utf-8")
            token = decrypt_token(encrypted, user_id)
            cog = self.bot.get_cog("AutoQuestsCog")
            if cog is None:
                raise RuntimeError(tr(language, "force_run_unavailable"))
            await cog._run_token(
                user_id,
                token_data["id"],
                token,
                label,
                token_data.get("token_hint", "????"),
                dm_channel,
            )
        except Exception as exc:
            logger.exception("Admin force-run failed for %s/%s", user_id, label)
            await interaction.followup.send(
                embed=error_embed(tr(language, "admin_force_error", error=exc), language),
                ephemeral=True,
            )

    @app_commands.command(
        name="admin-deactivate",
        description="[Admin] Deactivate a user's token",
    )
    @app_commands.describe(user_id="Discord user ID", label="Token label")
    async def admin_deactivate(
        self,
        interaction: discord.Interaction,
        user_id: str,
        label: str = "default",
    ):
        language = await self.bot.db.get_user_language(str(interaction.user.id))
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                embed=error_embed(tr(language, "admin_denied"), language), ephemeral=True
            )
            return

        db: Database = self.bot.db
        token_data = await db.get_token_by_label(user_id, label)

        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(tr(language, "admin_missing_token", uid=user_id, label=label), language),
                ephemeral=True,
            )
            return

        await db.set_token_active(token_data["id"], False)
        await interaction.response.send_message(
            embed=success_embed(tr(language, "admin_deactivated", uid=user_id, label=label), language),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
