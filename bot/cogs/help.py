"""Localized user guide."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import VERSION
from bot.utils.i18n import tr


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show the bot user guide")
    async def help_command(self, interaction: discord.Interaction):
        language = await self.bot.db.get_user_language(str(interaction.user.id))
        vi = language == "vi"
        embed = discord.Embed(
            title=tr(language, "help_title"),
            description=(
                "Bot tự động hoàn thành Discord Quest cho bạn.\n"
                "Mã hóa AES-256-GCM · Chạy song song · Theo dõi tiến độ trực tiếp"
                if vi else
                "Automatically complete Discord Quests.\n"
                "AES-256-GCM encryption · Parallel runs · Live progress"
            ),
            color=0x5865F2,
        )
        embed.add_field(
            name=tr(language, "help_quick"),
            value=(
                ("**Chạy một lần:** `/quests <token>`\n"
                 "**Lưu và tự động chạy:** `/autoquests save <token> [label]`\n"
                 "**Chọn chế độ chạy:** `/autoquests mode single|multi`\n"
                 "**Chọn ngôn ngữ:** `/language en|vi`\n"
                 "**Thêm token hết hạn/không hoạt động:** tự động dọn theo chính sách cấu hình.")
                if vi else
                ("**Run once:** `/quests <token>`\n"
                 "**Save and schedule:** `/autoquests save <token> [label]`\n"
                 "**Choose execution mode:** `/autoquests mode single|multi`\n"
                 "**Choose a language:** `/language en|vi`\n"
                 "**Expired or inactive tokens:** removed automatically by the configured cleanup policy.")
            ),
            inline=False,
        )
        embed.add_field(
            name=tr(language, "help_commands"),
            value=(
                "/autoquests-list · /autoquests-run · /autoquests-status\n"
                "/autoquests-pause · /autoquests-resume · /autoquests-remove · /autoquests-rename\n"
                "/autoquests-info · /info · /help · /language"
            ),
            inline=False,
        )
        embed.add_field(
            name=tr(language, "help_security"),
            value=(
                ("Token đã lưu được mã hóa AES-256-GCM. Token hiển thị đã được che; "
                 "lệnh trả lời riêng tư. Xóa token bất cứ lúc nào bằng `/autoquests-remove`.")
                if vi else
                ("Saved tokens are encrypted with AES-256-GCM. Tokens are masked in displays, "
                 "and command replies are private. Remove a token with `/autoquests-remove`.")
            ),
            inline=False,
        )
        embed.set_footer(text=f"Discord Quest Bot · v{VERSION}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
