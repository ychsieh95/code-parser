import asyncio
import os
import re
import discord
from discord.ext import commands
from utils.comic_parser import ComicType, ComicParser, NhentaiComicParser
from utils.code_parser import CodeParser
from utils.logger import LogLevel
from bot.constants import MODE_CODE, MODE_COMIC
from bot.db import Database
from bot.logger import logger
from config.settings import COVER_SAVE_DIR as _COVER_DIRS

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
        self.bot          = bot
        self.db           = db
        self.code_parser  = code_parser
        self.comic_parser = comic_parser

        os.makedirs(_CODE_COVER_DIR, exist_ok=True)
        for comic_dir in _COMIC_COVER_DIRS.values():
            os.makedirs(comic_dir, exist_ok=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
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
                work.append(('fetch', self._fetch_code(self.code_parser.fix_code(line))))
            else:
                work.append(('fail', line))

        await self._delete_message(message)

        # Run all fetches concurrently; gather preserves slot order
        fetch_slots = [(i, coro) for i, (kind, coro) in enumerate(work) if kind == 'fetch']
        if fetch_slots:
            indices, coros = zip(*fetch_slots)
            raw_results = await asyncio.gather(*coros, return_exceptions=True)
            fetch_results = dict(zip(indices, raw_results))
        else:
            fetch_results = {}

        # Send results in original input order
        for i, (kind, payload) in enumerate(work):
            if kind == 'fetch':
                result = fetch_results[i]
                if isinstance(result, BaseException):
                    logger.print(f'Handler raised an unhandled exception: {result}', LogLevel.WARN)
                    continue
                content, cover_path = result
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

    async def _fetch_code(self, code: str) -> tuple[str, str | None]:
        cover_path = f'{_CODE_COVER_DIR}/{code}.jpg'

        title_flag, title = await asyncio.to_thread(self.code_parser.get_title, code)
        logger.print(f'Parsed code "{code}": title_flag={title_flag}, title="{title}"', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
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
