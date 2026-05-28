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

_CODE_PATTERNS = [
    re.compile(r'^([a-zA-Z]{2,5})[-]?(\d{3,5})$'),
    re.compile(r'^(FC2)[-]?(PPV)?[-]?(\d+)$'),
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

        tasks    = []
        failures = []
        for line in lines:
            logger.print(f'Processing line: "{line}"', LogLevel.INFO)
            if MODE_CODE in active_modes and self._is_valid_code(line):
                tasks.append(('code', line, None))
            elif MODE_COMIC in active_modes:
                comic_type = self.comic_parser.get_comic_type(line)
                if comic_type != ComicType.UNKNOWN:
                    tasks.append(('comic', line, comic_type))
                else:
                    failures.append(line)
            else:
                failures.append(line)

        await self._delete_message(message)

        coros = []
        for kind, line, extra in tasks:
            if kind == 'code':
                coros.append(self._handle_code(message, self.code_parser.fix_code(line)))
            else:
                coros.append(self._handle_comic(message, line, extra))
        if coros:
            results = await asyncio.gather(*coros, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    logger.print(f'Handler raised an unhandled exception: {result}', LogLevel.WARN)

        for line in failures:
            if MODE_CODE in active_modes:
                await message.channel.send(
                    f'{message.author.mention} `{line}` is not a valid code format. '
                    'Expected formats: `ABC-123`, `FC2-PPV-123456`, etc.'
                )
            elif MODE_COMIC in active_modes:
                await message.channel.send(
                    f'{message.author.mention} `{line}` is not a recognized comic code.'
                )

    @staticmethod
    def _is_valid_code(code: str) -> bool:
        return any(p.match(code.upper()) for p in _CODE_PATTERNS)

    @staticmethod
    async def _delete_message(message: discord.Message):
        try:
            await message.delete()
        except discord.Forbidden:
            logger.print(f'Missing "Manage Messages" permission in #{message.channel.name}', LogLevel.WARN)
        except discord.NotFound:
            pass

    async def _handle_code(self, message: discord.Message, code: str):
        cover_path = f'{_CODE_COVER_DIR}/{code}.jpg'
        parser = CodeParser()

        title_flag, title = await asyncio.to_thread(parser.get_title, code)
        logger.print(f'Parsed code "{code}": title_flag={title_flag}, title="{title}"', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Could not find title for code "{code}"')
            return

        has_cover = await asyncio.to_thread(parser.download_cover, code, cover_path)
        logger.print(f'Parsed code "{code}": has_cover={has_cover}', LogLevel.INFO)

        title = title or code
        escaped_title = discord.utils.escape_markdown(title)
        content = f'**[{code} | {escaped_title}]({self.code_parser.get_video_url(code)})**'
        if has_cover and os.path.isfile(cover_path):
            await message.channel.send(content=content, file=discord.File(cover_path, filename=f'{code}.jpg'))
        else:
            await message.channel.send(content=content)

    async def _handle_comic(self, message: discord.Message, code: str, comic_type: ComicType):
        match comic_type:
            case ComicType.NHENTAI:
                parser = NhentaiComicParser()
            case ComicType.WNACG | ComicType.JM:
                await message.channel.send(content=f'`{code}` ({comic_type.name}) is not supported yet.')
                return
            case _:
                logger.print(f'Unsupported comic type for code "{code}"', LogLevel.WARN)
                await message.channel.send(content=f'Unsupported comic code "{code}"')
                return

        cover_path = f'{_COMIC_COVER_DIRS[comic_type]}/{code}.jpg'

        title_flag, title, has_cover = await asyncio.to_thread(
            parser.fetch_and_save, code, cover_path
        )
        logger.print(f'Parsed comic "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for comic "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Could not find title for comic "{code}"')
            return

        title = title or code
        escaped_title = discord.utils.escape_markdown(title)
        content = f'**[{code} | {escaped_title}]({parser.get_comic_url(code)})**'
        if has_cover and os.path.isfile(cover_path):
            await message.channel.send(content=content, file=discord.File(cover_path, filename=f'{code}.jpg'))
        else:
            await message.channel.send(content=content)
