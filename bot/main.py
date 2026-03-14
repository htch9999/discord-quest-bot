"""
Discord Quest Bot — Main entry point.

Initializes the bot, loads cogs, sets up database, scheduler, task manager,
and runs a FastAPI stats API on port 8099 alongside the bot.
"""

import asyncio
import os
import time
import discord
from discord.ext import commands

from bot.config import BOT_TOKEN, DB_PATH, DEBUG, VERSION
from bot.db.database import Database
from bot.core.task_manager import TaskManager
from bot.services.scheduler import QuestScheduler
from bot.services.rate_limiter import RateLimiter
from bot.utils.logger import get_logger

logger = get_logger("bot")

# ── Config ───────────────────────────────────────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "8099"))
API_HOST = os.getenv("API_HOST", "127.0.0.1")

# ── Cogs to load ─────────────────────────────────────────────────────────────
COGS = [
    "bot.cogs.quests",
    "bot.cogs.autoquests",
    "bot.cogs.info",
    "bot.cogs.admin",
    "bot.cogs.help",
]


class QuestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.db: Database = Database(DB_PATH)
        self.task_manager: TaskManager = TaskManager()
        self.scheduler: QuestScheduler = QuestScheduler(self)
        self.rate_limiter: RateLimiter = RateLimiter()
        self.start_time: float = time.time()

    async def setup_hook(self):
        """Called when the bot is starting up."""
        # Initialize database
        await self.db.init()
        logger.info("Database initialized: %s", DB_PATH)

        # Mark interrupted sessions from previous crash
        await self.db.mark_interrupted_sessions()

        # Load cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info("Loaded cog: %s", cog)
            except Exception as e:
                logger.error("Failed to load cog %s: %s", cog, e)

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash command(s)", len(synced))
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

        # Start scheduler
        self.scheduler.start()

        # Start FastAPI server in background
        asyncio.create_task(self._start_api_server())

    async def _start_api_server(self):
        """Start the FastAPI stats API server."""
        try:
            import uvicorn
            from bot.api.stats_router import create_api

            api = create_api(self)
            config = uvicorn.Config(
                api,
                host=API_HOST,
                port=API_PORT,
                log_level="warning",
            )
            server = uvicorn.Server(config)
            self._api_server = server
            logger.info("API server starting on %s:%d", API_HOST, API_PORT)
            await server.serve()
        except Exception as e:
            logger.error("API server failed: %s", e)

    async def on_ready(self):
        logger.info("=" * 50)
        logger.info("Bot online: %s (ID: %s)", self.user.name, self.user.id)
        logger.info("Version: v%s", VERSION)
        logger.info("Guilds: %d", len(self.guilds))
        logger.info("API: http://%s:%d/v1/health", API_HOST, API_PORT)
        logger.info("=" * 50)

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Discord Quests",
            )
        )

    async def close(self):
        """Clean shutdown."""
        logger.info("Shutting down...")
        # Stop API server
        if hasattr(self, "_api_server"):
            self._api_server.should_exit = True
        self.scheduler.stop()
        await self.task_manager.shutdown()
        await self.db.close()
        await super().close()


def main():
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        logger.error(
            "BOT_TOKEN chưa được cấu hình. Copy .env.example → .env và điền token."
        )
        return

    bot = QuestBot()

    try:
        bot.run(BOT_TOKEN, log_handler=None)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Bot crashed: %s", e)


if __name__ == "__main__":
    main()

