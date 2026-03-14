"""
/info and /autoquests-info commands.
"""

import time
import discord
from discord import app_commands
from discord.ext import commands

from bot.db.database import Database
from bot.utils.formatter import info_embed
from bot.utils.logger import get_logger

logger = get_logger("cog.info")


class InfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="info",
        description="Thông tin server bot",
    )
    async def info(self, interaction: discord.Interaction):
        db: Database = self.bot.db

        total_users = await db.count_unique_users()
        total_quests = await db.count_total_quests_done()
        guild_count = len(self.bot.guilds)
        latency_ms = self.bot.latency * 1000
        uptime_secs = int(time.time() - self.bot.start_time)

        embed = info_embed(
            total_users=total_users,
            total_quests_done=total_quests,
            guild_count=guild_count,
            latency_ms=latency_ms,
            uptime_seconds=uptime_secs,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="autoquests-info",
        description="Thống kê auto-quest cá nhân",
    )
    async def autoquests_info(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        db: Database = self.bot.db

        tokens = await db.get_tokens(uid)
        stats = await db.get_user_stats(uid)

        active_count = sum(1 for t in tokens if t.get("is_active"))
        total_time = stats.get("total_time", 0) or 0
        hours = total_time // 3600
        mins = (total_time % 3600) // 60

        embed = discord.Embed(title="📊 Auto-Quest Stats", color=0x5865F2)
        embed.add_field(
            name="🔑 Token đã lưu",
            value=f"{len(tokens)} (active: {active_count})",
            inline=True,
        )
        embed.add_field(
            name="✅ Tổng quest hoàn thành",
            value=str(stats.get("total", 0)),
            inline=True,
        )
        embed.add_field(
            name="⏱️ Tổng thời gian",
            value=f"{hours}h {mins}m",
            inline=True,
        )

        # Next scheduled run
        next_runs = [
            t["next_run_at"]
            for t in tokens
            if t.get("is_active") and t.get("next_run_at")
        ]
        if next_runs:
            next_runs.sort()
            embed.add_field(
                name="⏰ Lần chạy tự động tiếp theo",
                value=next_runs[0],
                inline=False,
            )

        embed.set_footer(text="@htch9999🌷 — Discord Quest Bot")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCog(bot))
