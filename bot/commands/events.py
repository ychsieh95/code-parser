import asyncio
import os
import re
import discord
from discord.ext import commands
from utils.comic_parser import ComicType, ComicParser, NhentaiComicParser
from utils.code_parser import CodeParser
from utils.logger import LogLevel, Logger
from bot.db import Database

_CODE_PATTERNS = [
    re.compile(r'^([a-zA-Z]{2,5})[-]?(\d{3,5})$'),
    re.compile(r'^(FC2)[-]?(PPV)?[-]?(\d+)$'),
]

COVER_SAVE_DIR = {
    'code'  : './assets/covers/code',
    'comic' : {
        ComicType.NHENTAI: './assets/covers/comics/nhentai',
        ComicType.WNACG  : './assets/covers/comics/wnacg',
        ComicType.JM     : './assets/covers/comics/JM',
    }
}

MODE_CODE  = "code"
MODE_COMIC = "comic"

logger = Logger(clear_previous=False, reserve_line_num=0)


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database, code_parser: CodeParser, comic_parser: ComicParser):
        self.bot          = bot
        self.db           = db
        self.code_parser  = code_parser
        self.comic_parser = comic_parser

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
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

        for kind, line, extra in tasks:
            if kind == 'code':
                await self._handle_code(message, self.code_parser.fix_code(line))
            else:
                await self._handle_comic(message, line, extra)

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
        cover_path = f'{COVER_SAVE_DIR["code"]}/{code}.jpg'
        os.makedirs(COVER_SAVE_DIR['code'], exist_ok=True)

        title_flag, title = await asyncio.to_thread(self.code_parser.get_title, code)
        has_cover         = await asyncio.to_thread(self.code_parser.download_cover, code, cover_path)
        logger.print(f'Parsed code "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Could not find title for code "{code}"')
            return

        content = f'**[{code} | {title}]({self.code_parser.get_video_url(code)})**'
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

        comic_dir  = COVER_SAVE_DIR['comic'][comic_type]
        cover_path = f'{comic_dir}/{code}.jpg'
        os.makedirs(comic_dir, exist_ok=True)

        title_flag, title = await asyncio.to_thread(parser.get_title, code)
        has_cover         = await asyncio.to_thread(parser.download_cover, code, cover_path)
        logger.print(f'Parsed comic "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            logger.print(f'Could not find title for comic "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Could not find title for comic "{code}"')
            return

        content = f'**[{code} | {title}]({parser.get_comic_url(code)})**'
        if has_cover and os.path.isfile(cover_path):
            await message.channel.send(content=content, file=discord.File(cover_path, filename=f'{code}.jpg'))
        else:
            await message.channel.send(content=content)
