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

logger = get_logger("cog.admin")


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        app_info = await self.bot.application_info()
        return interaction.user.id == app_info.owner.id

    @app_commands.command(
        name="admin-stats",
        description="[Admin] Xem thống kê hệ thống",
    )
    async def admin_stats(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                embed=error_embed("Bạn không có quyền admin."), ephemeral=True
            )
            return

        db: Database = self.bot.db
        task_manager: TaskManager = self.bot.task_manager

        total_users = await db.count_unique_users()
        total_quests = await db.count_total_quests_done()
        task_status = task_manager.get_status()

        embed = discord.Embed(title="🔧 Admin Stats", color=0xED4245)
        embed.add_field(name="Unique Users", value=str(total_users), inline=True)
        embed.add_field(name="Total Quests Done", value=str(total_quests), inline=True)
        embed.add_field(
            name="Running Tasks",
            value=f"{task_status['active_tasks']}/{task_status['max_concurrent']}",
            inline=True,
        )
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="admin-force-run",
        description="[Admin] Chạy quest cho user cụ thể",
    )
    @app_commands.describe(user_id="Discord user ID", label="Token label")
    async def admin_force_run(
        self,
        interaction: discord.Interaction,
        user_id: str,
        label: str = "default",
    ):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                embed=error_embed("Bạn không có quyền admin."), ephemeral=True
            )
            return

        db: Database = self.bot.db
        token_data = await db.get_token_by_label(user_id, label)

        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token cho user {user_id}/{label}."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed(f"Đang force-run cho user {user_id}/{label}..."),
            ephemeral=True,
        )

        # Trigger the scheduler's auto-run logic
        logger.info("Admin force-run: %s/%s", user_id, label)

    @app_commands.command(
        name="admin-deactivate",
        description="[Admin] Tắt token của một user",
    )
    @app_commands.describe(user_id="Discord user ID", label="Token label")
    async def admin_deactivate(
        self,
        interaction: discord.Interaction,
        user_id: str,
        label: str = "default",
    ):
        if not await self._is_owner(interaction):
            await interaction.response.send_message(
                embed=error_embed("Bạn không có quyền admin."), ephemeral=True
            )
            return

        db: Database = self.bot.db
        token_data = await db.get_token_by_label(user_id, label)

        if not token_data:
            await interaction.response.send_message(
                embed=error_embed(f"Không tìm thấy token cho user {user_id}/{label}."),
                ephemeral=True,
            )
            return

        await db.set_token_active(token_data["id"], False)
        await interaction.response.send_message(
            embed=success_embed(f"Đã deactivate token {user_id}/{label}."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
