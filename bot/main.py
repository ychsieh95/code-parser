import asyncio
import os
import signal
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import BOT_TOKEN
from utils.comic_parser import ComicParser
from utils.code_parser import CodeParser
from utils.logger import LogLevel, Logger
from bot.db import Database
from bot.commands.admin import AdminCog
from bot.commands.general import GeneralCog
from bot.commands.events import EventsCog

logger = Logger(clear_previous=False, reserve_line_num=0)

# Set DEV_GUILD_ID in your environment for instant per-guild sync during development.
# Leave unset (or 0) for normal global sync in production.
DEV_GUILD_ID: int | None = int(os.getenv('DEV_GUILD_ID', 0)) or None


class CodeParserBot(commands.Bot):
    def __init__(self, db: Database):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        self.db = db

    async def setup_hook(self):
        code_parser  = CodeParser()
        comic_parser = ComicParser()
        await self.add_cog(AdminCog(self, self.db))
        await self.add_cog(GeneralCog(self, self.db))
        await self.add_cog(EventsCog(self, self.db, code_parser, comic_parser))

    async def on_ready(self):
        if DEV_GUILD_ID:
            guild = discord.Object(id=DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.print(f'[DEV] Synced {len(synced)} commands to guild {DEV_GUILD_ID}', LogLevel.INFO)
        else:
            for guild in self.guilds:
                synced = await self.tree.sync(guild=guild)
                logger.print(f'Synced {len(synced)} commands to {guild.name} ({guild.id})', LogLevel.INFO)
            await self.tree.sync()
        logger.print(f'Logged in as {self.user} (id: {self.user.id})', LogLevel.INFO)


async def main():
    db  = Database()
    await db.connect()

    bot = CodeParserBot(db)

    @bot.tree.error
    async def _(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f'This command is on cooldown. Try again in {error.retry_after:.1f}s.', ephemeral=True
            )
        else:
            raise error

    loop = asyncio.get_running_loop()

    def _shutdown():
        loop.create_task(bot.close())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    try:
        async with bot:
            await bot.start(BOT_TOKEN)
    finally:
        await db.close()
        logger.print('Bot shut down cleanly.', LogLevel.INFO)


asyncio.run(main())
