"""Language preference command."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.i18n import tr


class LanguageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="language",
        description="Change the language used in bot messages",
    )
    @app_commands.describe(language="Choose English or Vietnamese")
    @app_commands.choices(language=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Tiếng Việt", value="vi"),
    ])
    async def language(
        self,
        interaction: discord.Interaction,
        language: app_commands.Choice[str],
    ):
        uid = str(interaction.user.id)
        await self.bot.db.set_user_language(uid, language.value)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=tr(language.value, "language_title"),
                description=tr(language.value, "language_saved"),
                color=0x5865F2,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LanguageCog(bot))
