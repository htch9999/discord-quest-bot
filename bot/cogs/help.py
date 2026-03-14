"""
Help command — comprehensive usage guide for users.
"""

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import VERSION
from bot.utils.logger import get_logger

logger = get_logger("cog.help")


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Hướng dẫn sử dụng chi tiết tất cả lệnh của bot",
    )
    async def help_command(self, interaction: discord.Interaction):
        # ── Page 1: Overview ──
        embed1 = discord.Embed(
            title="Discord Quest Bot — Hướng dẫn sử dụng",
            description=(
                "Bot tự động hoàn thành mọi quest Discord cho bạn.\n"
                "Bảo mật AES-256-GCM · Song song · Real-time progress\n\n"
                f"**Phiên bản:** v{VERSION}"
            ),
            color=0x5865F2,
        )

        # ── Quick Start ──
        embed1.add_field(
            name="Bắt đầu nhanh",
            value=(
                "**Chạy 1 lần (không lưu token):**\n"
                "`/quests <discord_token>`\n\n"
                "**Tự động (lưu token, chạy mỗi 2 ngày):**\n"
                "`/autoquests <discord_token> [label]`"
            ),
            inline=False,
        )

        # ── Page 2: All Commands ──
        embed2 = discord.Embed(
            title="Danh sách lệnh",
            color=0x5865F2,
        )

        embed2.add_field(
            name="/quests `<token>`",
            value="Chạy quest một lần. Token **không** được lưu lại.",
            inline=False,
        )

        embed2.add_field(
            name="/autoquests `<token>` `[label]`",
            value=(
                "Lưu token (mã hoá AES-256-GCM) và tự động chạy quest mỗi 2 ngày.\n"
                "`label` = tên hiển thị (mặc định: `default`)."
            ),
            inline=False,
        )

        embed2.add_field(
            name="/autoquests run `[label]`",
            value="Chạy thủ công ngay lập tức (không chờ scheduler).",
            inline=True,
        )

        embed2.add_field(
            name="/autoquests pause `[label]`",
            value="Tạm dừng auto-schedule.",
            inline=True,
        )

        embed2.add_field(
            name="/autoquests resume `[label]`",
            value="Bật lại auto-schedule.",
            inline=True,
        )

        embed2.add_field(
            name="/autoquests list",
            value="Xem danh sách token đã lưu.",
            inline=True,
        )

        embed2.add_field(
            name="/autoquests remove `<label>`",
            value="Xoá token + tất cả thống kê liên quan.",
            inline=True,
        )

        embed2.add_field(
            name="/autoquests rename `<old>` `<new>`",
            value="Đổi tên label.",
            inline=True,
        )

        embed2.add_field(
            name="/autoquests status `[label]`",
            value="Xem trạng thái chi tiết token.",
            inline=True,
        )

        # ── Page 3: Info + Security ──
        embed3 = discord.Embed(
            title="Thông tin & Bảo mật",
            color=0x5865F2,
        )

        embed3.add_field(
            name="/autoquests-info",
            value="Thống kê cá nhân: tổng quest, token đã lưu, phiên chạy.",
            inline=True,
        )

        embed3.add_field(
            name="/info",
            value="Thông tin bot: version, uptime, server, memory.",
            inline=True,
        )

        embed3.add_field(
            name="/help",
            value="Trang hướng dẫn này.",
            inline=True,
        )

        embed3.add_field(
            name="Bảo mật token",
            value=(
                "• Token mã hoá **AES-256-GCM** với key dẫn xuất từ Discord user ID\n"
                "• Token **không bao giờ** xuất hiện trong log\n"
                "• Tất cả lệnh đều **ephemeral** (chỉ bạn nhìn thấy)\n"
                "• Token hiển thị dạng masked: `MTA...xyz`\n"
                "• Xoá bất cứ lúc nào với `/autoquests remove`"
            ),
            inline=False,
        )

        embed3.add_field(
            name="Loại quest hỗ trợ",
            value=(
                "`WATCH_VIDEO` · `WATCH_VIDEO_ON_MOBILE`\n"
                "`PLAY_ON_DESKTOP` · `STREAM_ON_DESKTOP`\n"
                "`PLAY_ACTIVITY`"
            ),
            inline=False,
        )

        embed3.set_footer(text="@htch9999 — Discord Quest Bot · Open Source")

        await interaction.response.send_message(
            embeds=[embed1, embed2, embed3],
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
