import asyncio
import discord
import os
import re
from bot.constants import READ_ACTION_NONE, MODE_CODE, MODE_COMIC
from bot.db import Database
from bot.logger import logger
from bot.views import ReadActionView
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

        if message.content.startswith((f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>')):
            return

        active_modes = self.db.get_modes(message.channel.id)
        if not active_modes:
            return

        should_delete = self.db.message_deletion_enabled(message.channel.id)
        lines = [line.strip() for line in message.content.splitlines() if line.strip()]

        if not lines:
            if should_delete:
                await self._delete_message(message)
            await message.channel.send(f'{message.author.mention} Invalid input: message contains no valid content.')
            return

        logger.print(f'Received {len(lines)} line(s) from {message.author} in #{message.channel.name}', LogLevel.INFO)

        if should_delete:
            await self._delete_message(message)
        passed_codes, failed_codes = await self._process_lines(lines, message.channel, active_modes, message.author.mention)
        if len(lines) > 1 or failed_codes:
            summary = self._build_summary(passed_codes, failed_codes)
            await message.channel.send(f'{message.author.mention}\n{summary}')

    @app_commands.command(name='parse', description='Parse one or more codes')
    @app_commands.describe(codes='Codes to parse, separated by spaces')
    async def cmd_parse(self, interaction: discord.Interaction, codes: str):
        active_modes = self.db.get_modes(interaction.channel_id)
        if not active_modes:
            await interaction.response.send_message('No parsing mode is enabled for this channel.', ephemeral=True)
            return

        lines = codes.split()
        if not lines:
            await interaction.response.send_message('No codes provided.', ephemeral=True)
            return

        logger.print(f'Received {len(lines)} code(s) from {interaction.user} in #{interaction.channel.name}', LogLevel.INFO)

        await interaction.response.defer(ephemeral=True)
        passed_codes, failed_codes = await self._process_lines(lines, interaction.channel, active_modes, interaction.user.mention)
        summary = self._build_summary(passed_codes, failed_codes)
        await interaction.followup.send(summary, ephemeral=True)

    @app_commands.command(name='find_code', description='Fetch one or more video codes directly')
    @app_commands.describe(codes='Video codes to fetch, separated by spaces')
    async def cmd_find_code(self, interaction: discord.Interaction, codes: str):
        lines = codes.split()
        if not lines:
            await interaction.response.send_message('No codes provided.', ephemeral=True)
            return

        logger.print(f'Received {len(lines)} code(s) from {interaction.user} in #{interaction.channel.name}', LogLevel.INFO)

        await interaction.response.defer(ephemeral=True)
        passed_codes, failed_codes = await self._process_lines(lines, interaction.channel, {MODE_CODE}, interaction.user.mention)
        summary = self._build_summary(passed_codes, failed_codes)
        await interaction.followup.send(summary, ephemeral=True)

    @app_commands.command(name='find_comic', description='Fetch one or more comic codes directly')
    @app_commands.describe(codes='Comic codes to fetch, separated by spaces')
    async def cmd_find_comic(self, interaction: discord.Interaction, codes: str):
        lines = codes.split()
        if not lines:
            await interaction.response.send_message('No codes provided.', ephemeral=True)
            return

        logger.print(f'Received {len(lines)} comic code(s) from {interaction.user} in #{interaction.channel.name}', LogLevel.INFO)

        await interaction.response.defer(ephemeral=True)
        passed_codes, failed_codes = await self._process_lines(lines, interaction.channel, {MODE_COMIC}, interaction.user.mention)
        summary = self._build_summary(passed_codes, failed_codes)
        await interaction.followup.send(summary, ephemeral=True)

    @app_commands.command(name='search', description='Search for video codes by keywords and fetch each result')
    @app_commands.describe(keywords='Search keywords', num='Number of results to fetch (default 10)')
    async def cmd_search(self, interaction: discord.Interaction, keywords: str, num: int = 10):
        await interaction.response.defer(ephemeral=True)
        ok, codes = await asyncio.to_thread(self.code_parser.search, keywords, None, num)
        if not ok or not codes:
            await interaction.followup.send(f'No results for "{keywords}".', ephemeral=True)
            return
        passed_codes, failed_codes = await self._process_lines(codes, interaction.channel, {MODE_CODE}, interaction.user.mention)
        await interaction.followup.send(self._build_summary(passed_codes, failed_codes), ephemeral=True)

    @app_commands.command(name='get_latest', description='Fetch the latest video codes')
    @app_commands.describe(num='Number of results to fetch (default 10)')
    async def cmd_get_latest(self, interaction: discord.Interaction, num: int = 10):
        await interaction.response.defer(ephemeral=True)
        ok, codes = await asyncio.to_thread(self.code_parser.get_latest, num)
        if not ok or not codes:
            await interaction.followup.send('No latest codes found.', ephemeral=True)
            return
        passed_codes, failed_codes = await self._process_lines(codes, interaction.channel, {MODE_CODE}, interaction.user.mention)
        await interaction.followup.send(self._build_summary(passed_codes, failed_codes), ephemeral=True)

    @app_commands.command(name='get_suggestion', description='Fetch suggested video codes for a given code')
    @app_commands.describe(code='Video code to get suggestions for', num='Number of results to fetch (default 10)')
    async def cmd_get_suggestion(self, interaction: discord.Interaction, code: str, num: int = 10):
        await interaction.response.defer(ephemeral=True)
        ok, codes = await asyncio.to_thread(self.code_parser.get_suggestion, code, num)
        if not ok or not codes:
            await interaction.followup.send(f'No suggestions found for "{code}".', ephemeral=True)
            return
        passed_codes, failed_codes = await self._process_lines(codes, interaction.channel, {MODE_CODE}, interaction.user.mention)
        await interaction.followup.send(self._build_summary(passed_codes, failed_codes), ephemeral=True)

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
    def _build_summary(passed_codes: list[str], failed_codes: list[str]) -> str:
        total = len(passed_codes) + len(failed_codes)

        lines = [
            '### 📊 Execution Summary',
            f"> **Status:** {'❌ Attention Required' if failed_codes else '✅ All Clear'}",
            f'> **Progress:** `{len(passed_codes)}` / `{total}` completed\n'
        ]

        if failed_codes:
            lines.append('**Failed List:**')
            lines.append('```diff')
            lines.extend(f'- {c}' for c in failed_codes)
            lines.append('```')

        return '\n'.join(lines)

    async def _process_lines(
        self,
        lines: list[str],
        channel: discord.abc.Messageable,
        active_modes: set[str],
        author_mention: str,
    ) -> tuple[list[str], list[str]]:
        work = []
        for line in lines:
            logger.print(f'Processing line: "{line}"', LogLevel.INFO)
            if MODE_COMIC in active_modes and self._is_valid_comic_code(line):
                comic_type = self.comic_parser.get_comic_type(line)
                if comic_type != ComicType.UNKNOWN:
                    work.append(('fetch', line, self._fetch_comic(line, comic_type)))
                else:
                    work.append(('fail', line, None))
            elif MODE_CODE in active_modes:
                code = self.code_parser.fix_code(line)
                work.append(('fetch', code, self._fetch_code(code, self.fetch_retries, self.fetch_retry_delay)))
            else:
                work.append(('fail', line, None))

        def progress_bar(done: int, total: int, width: int = 20) -> str:
            filled = done * width // total
            return '█' * filled + '░' * (width - filled)

        fetch_total = sum(1 for kind, _, _ in work if kind == 'fetch')

        def build_status(done: int) -> str:
            bar = progress_bar(done, fetch_total)
            return (
                f'{author_mention} Received {len(lines)} code(s)\n'
                f'Processing {bar} ({done}/{fetch_total})'
            )

        processing_msg = None
        if fetch_total:
            processing_msg = await channel.send(build_status(0))

        passed_codes: list[str] = []
        failed_codes: list[str] = []

        completed = 0
        for kind, code, payload in work:
            if kind == 'fetch':
                if completed > 0:
                    await asyncio.sleep(1.0)
                try:
                    ok, content, cover_path = await payload
                except BaseException as e:
                    logger.print(f'Handler raised an unhandled exception: {e}', LogLevel.WARN)
                    failed_codes.append(code)
                    completed += 1
                    if processing_msg:
                        await processing_msg.edit(content=build_status(completed))
                    continue
                completed += 1
                if processing_msg:
                    await processing_msg.edit(content=build_status(completed))
                if ok:
                    passed_codes.append(code)
                    view = None
                    if self.db.read_action(channel.id) != READ_ACTION_NONE:
                        view = ReadActionView(self.db, channel)
                    if cover_path:
                        await channel.send(
                            content=content,
                            file=discord.File(cover_path, filename=os.path.basename(cover_path)),
                            view=view,
                        )
                    else:
                        await channel.send(content=content, view=view)
                else:
                    failed_codes.append(code)
            else:
                failed_codes.append(code)

        if processing_msg:
            await processing_msg.delete()

        return passed_codes, failed_codes

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

    async def _fetch_code(self, code: str, retries: int = 3, retry_delay: float = 2.0) -> tuple[bool, str, str | None]:
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
            return (False, f'Could not find title for code "{code}"', None)

        has_cover = await asyncio.to_thread(self.code_parser.download_cover, code, cover_path)
        logger.print(f'Parsed code "{code}": has_cover={has_cover}', LogLevel.INFO)

        title = title or code
        escaped_title = discord.utils.escape_markdown(title)
        content = f'**[{code} | {escaped_title}]({self.code_parser.get_video_url(code)})**'
        actual_cover = cover_path if has_cover and os.path.isfile(cover_path) else None
        return (True, content, actual_cover)

    async def _fetch_comic(self, code: str, comic_type: ComicType) -> tuple[bool, str, str | None]:
        match comic_type:
            case ComicType.NHENTAI:
                parser = NhentaiComicParser()
                code = re.sub(r'^[nN]', '', code)
            case ComicType.WNACG | ComicType.JM:
                return (False, f'`{code}` ({comic_type.name}) is not supported yet.', None)
            case _:
                logger.print(f'Unsupported comic type for code "{code}"', LogLevel.WARN)
                return (False, f'Unsupported comic code "{code}"', None)

        cover_path = f'{_COMIC_COVER_DIRS[comic_type]}/{code}.jpg'

        title_flag, title, has_cover = await asyncio.to_thread(
            parser.fetch_and_save, code, cover_path
        )
        logger.print(f'Parsed comic "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for comic "{code}"', LogLevel.WARN)
            return (False, f'Could not find title for comic "{code}"', None)

        title = title or code
        escaped_title = discord.utils.escape_markdown(title)
        content = f'**[{code} | {escaped_title}]({parser.get_comic_url(code)})**'
        actual_cover = cover_path if has_cover and os.path.isfile(cover_path) else None
        return (True, content, actual_cover)
