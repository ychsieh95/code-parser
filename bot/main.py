import asyncio
import discord
import os
import signal
from bot.commands.admin import AdminCog
from bot.commands.events import EventsCog
from bot.commands.general import GeneralCog
from bot.db import Database
from bot.logger import logger
from bot.views import ReadActionView
from config.settings import BOT_TOKEN
from discord import app_commands
from discord.ext import commands
from utils.code_parser import CodeParser
from utils.comic_parser import ComicParser
from utils.logger import LogLevel

# Set DEV_GUILD_ID in your environment for instant per-guild sync during development.
# Leave unset (or 0) for normal global sync in production.
DEV_GUILD_ID: int | None = int(os.getenv('DEV_GUILD_ID', 0)) or None


class CodeParserBot(commands.Bot):
    def __init__(self, db: Database):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members         = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.db = db

    async def setup_hook(self):
        code_parser  = CodeParser()
        comic_parser = ComicParser()
        await self.add_cog(AdminCog(self, self.db))
        await self.add_cog(GeneralCog(self, self.db))
        await self.add_cog(EventsCog(self, self.db, code_parser, comic_parser))

        self.add_view(ReadActionView(self.db))

        if DEV_GUILD_ID:
            guild = discord.Object(id=DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.print(f'[DEV] Synced {len(synced)} commands to guild {DEV_GUILD_ID}', LogLevel.INFO)
        else:
            synced = await self.tree.sync()
            logger.print(f'Synced {len(synced)} global commands', LogLevel.INFO)

    async def on_ready(self):
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


if __name__ == '__main__':
    asyncio.run(main())
