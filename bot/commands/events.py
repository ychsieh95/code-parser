import asyncio
import discord
import os
import re
from bot.constants import MODE_CODE, MODE_COMIC
from bot.db import Database
from bot.logger import logger
from config.settings import COVER_SAVE_DIR as _COVER_DIRS
from discord import app_commands
from discord.ext import commands
from utils.comic_parser import ComicType, ComicParser, NhentaiComicParser
from utils.code_parser import CodeParser
from utils.logger import LogLevel

_COMIC_CODE_PATTERNS = [
    re.compile(r'^N?[\d]+$'),     # Nhentai: 123456 or N123456
    re.compile(r'^W[\d]+$'),      # WNACG: W123456
    re.compile(r'^JM?[\d]+$'),    # JM: J123456 or JM123456
]

_CODE_COVER_DIR   = _COVER_DIRS['code']
_COMIC_COVER_DIRS = {
    ComicType.NHENTAI: _COVER_DIRS['comic']['nhentai'],
    ComicType.WNACG  : _COVER_DIRS['comic']['wnacg'],
    ComicType.JM     : _COVER_DIRS['comic']['jm'],
}


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database, code_parser: CodeParser, comic_parser: ComicParser):
        self.bot               = bot
        self.db                = db
        self.code_parser       = code_parser
        self.comic_parser      = comic_parser
        self.fetch_retries     = 3
        self.fetch_retry_delay = 2.0

        os.makedirs(_CODE_COVER_DIR, exist_ok=True)
        for comic_dir in _COMIC_COVER_DIRS.values():
            os.makedirs(comic_dir, exist_ok=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        active_modes = self.db.get_modes(message.channel.id)
        if not active_modes:
            return

        lines = [line.strip() for line in message.content.splitlines() if line.strip()]

        if not lines:
            await self._delete_message(message)
            await message.channel.send(f'{message.author.mention} Invalid input: message contains no valid content.')
            return

        logger.print(f'Received {len(lines)} line(s) from {message.author} in #{message.channel.name}', LogLevel.INFO)

        # Build ordered work list in input order: ('fetch', coro) | ('fail', line)
        work = []
        for line in lines:
            logger.print(f'Processing line: "{line}"', LogLevel.INFO)
            if MODE_COMIC in active_modes and self._is_valid_comic_code(line):
                comic_type = self.comic_parser.get_comic_type(line)
                if comic_type != ComicType.UNKNOWN:
                    work.append(('fetch', self._fetch_comic(line, comic_type)))
                else:
                    work.append(('fail', line))
            elif MODE_CODE in active_modes:
                work.append(('fetch', self._fetch_code(self.code_parser.fix_code(line), self.fetch_retries, self.fetch_retry_delay)))
            else:
                work.append(('fail', line))

        await self._delete_message(message)

        def progress_bar(done: int, total: int, width: int = 20) -> str:
            filled = done * width // total
            return '█' * filled + '░' * (width - filled)

        fetch_total = sum(1 for kind, _ in work if kind == 'fetch')

        def build_status(done: int) -> str:
            bar = progress_bar(done, fetch_total)
            return (
                f'{message.author.mention} Received {len(lines)} code(s)\n'
                f'Processing {bar} ({done}/{fetch_total})'
            )

        processing_msg = None
        if fetch_total:
            processing_msg = await message.channel.send(build_status(0))

        completed = 0
        for kind, payload in work:
            if kind == 'fetch':
                if completed > 0:
                    await asyncio.sleep(1.0)
                try:
                    content, cover_path = await payload
                except BaseException as e:
                    logger.print(f'Handler raised an unhandled exception: {e}', LogLevel.WARN)
                    completed += 1
                    if processing_msg:
                        await processing_msg.edit(content=build_status(completed))
                    continue
                completed += 1
                if processing_msg:
                    await processing_msg.edit(content=build_status(completed))
                if cover_path:
                    await message.channel.send(
                        content=content,
                        file=discord.File(cover_path, filename=os.path.basename(cover_path))
                    )
                else:
                    await message.channel.send(content=content)
            else:
                line = payload
                if active_modes == {MODE_CODE}:
                    await message.channel.send(
                        f'{message.author.mention} `{line}` is not a valid code format. '
                        'Expected formats: `ABC-123`, `FC2-PPV-123456`, etc.'
                    )
                elif active_modes == {MODE_COMIC}:
                    await message.channel.send(
                        f'{message.author.mention} `{line}` is not a recognized comic code.'
                    )
                else:
                    await message.channel.send(
                        f'{message.author.mention} `{line}` is not a recognized code or comic code.'
                    )

        if processing_msg:
            await processing_msg.delete()

    @app_commands.command(name='set_latency', description='Set retry delay (seconds) between fetch attempts for code parsing')
    @app_commands.describe(seconds='Delay in seconds between retries (0.0 – 60.0)')
    @app_commands.default_permissions(administrator=True)
    async def cmd_set_latency(self, interaction: discord.Interaction, seconds: float):
        if not (0.0 <= seconds <= 60.0):
            await interaction.response.send_message('Retry delay must be between 0.0 and 60.0 seconds.', ephemeral=True)
            return
        self.fetch_retry_delay = seconds
        logger.print(f'fetch retry_delay set to {seconds}s', LogLevel.INFO)
        await interaction.response.send_message(f'Retry delay set to **{seconds}s**.', ephemeral=True)

    @app_commands.command(name='set_retry_num', description='Set number of fetch attempts for code parsing')
    @app_commands.describe(count='Number of attempts (1 – 10)')
    @app_commands.default_permissions(administrator=True)
    async def cmd_set_retry_num(self, interaction: discord.Interaction, count: int):
        if not (1 <= count <= 10):
            await interaction.response.send_message('Retry count must be between 1 and 10.', ephemeral=True)
            return
        self.fetch_retries = count
        logger.print(f'fetch retries set to {count}', LogLevel.INFO)
        await interaction.response.send_message(f'Retry count set to **{count}**.', ephemeral=True)

    @staticmethod
    def _is_valid_comic_code(code: str) -> bool:
        return any(p.match(code.upper()) for p in _COMIC_CODE_PATTERNS)

    @staticmethod
    async def _delete_message(message: discord.Message):
        try:
            await message.delete()
        except discord.Forbidden:
            logger.print(f'Missing "Manage Messages" permission in #{message.channel.name}', LogLevel.WARN)
        except discord.NotFound:
            pass

    async def _fetch_code(self, code: str, retries: int = 3, retry_delay: float = 2.0) -> tuple[str, str | None]:
        cover_path = f'{_CODE_COVER_DIR}/{code}.jpg'

        title_flag, title = False, None
        for attempt in range(1, retries + 1):
            title_flag, title = await asyncio.to_thread(self.code_parser.get_title, code)
            logger.print(f'Parsed code "{code}" (attempt {attempt}/{retries}): title_flag={title_flag}, title="{title}"', LogLevel.INFO)
            if title_flag:
                break
            if attempt < retries:
                logger.print(f'Retrying code "{code}" in {retry_delay}s...', LogLevel.WARN)
                await asyncio.sleep(retry_delay)

        if not title_flag:
            logger.print(f'Could not find title for code "{code}" after {retries} attempt(s)', LogLevel.WARN)
            return (f'Could not find title for code "{code}"', None)

        has_cover = await asyncio.to_thread(self.code_parser.download_cover, code, cover_path)
        logger.print(f'Parsed code "{code}": has_cover={has_cover}', LogLevel.INFO)

        title = title or code
        escaped_title = discord.utils.escape_markdown(title)
        content = f'**[{code} | {escaped_title}]({self.code_parser.get_video_url(code)})**'
        actual_cover = cover_path if has_cover and os.path.isfile(cover_path) else None
        return (content, actual_cover)

    async def _fetch_comic(self, code: str, comic_type: ComicType) -> tuple[str, str | None]:
        match comic_type:
            case ComicType.NHENTAI:
                parser = NhentaiComicParser()
            case ComicType.WNACG | ComicType.JM:
                return (f'`{code}` ({comic_type.name}) is not supported yet.', None)
            case _:
                logger.print(f'Unsupported comic type for code "{code}"', LogLevel.WARN)
                return (f'Unsupported comic code "{code}"', None)

        cover_path = f'{_COMIC_COVER_DIRS[comic_type]}/{code}.jpg'

        title_flag, title, has_cover = await asyncio.to_thread(
            parser.fetch_and_save, code, cover_path
        )
        logger.print(f'Parsed comic "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for comic "{code}"', LogLevel.WARN)
            return (f'Could not find title for comic "{code}"', None)

        title = title or code
        escaped_title = discord.utils.escape_markdown(title)
        content = f'**[{code} | {escaped_title}]({parser.get_comic_url(code)})**'
        actual_cover = cover_path if has_cover and os.path.isfile(cover_path) else None
        return (content, actual_cover)
