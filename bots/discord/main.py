import discord as discord
import os
from config.settings import COVER_SAVE_DIR, BOT_TOKEN, CHANNEL_IDS
from src.comic_parser.comic_parser import ComicType, ComicParser, NhentaiComicParser, WnacgComicParser, JmComicParser
from src.code_parser.code_parser import CodeParser
from src.utils.logger import LogLevel, Logger

# ── Initialization ───────────────────────────────────────────────────────────
code_parser  = CodeParser()
comic_parser = ComicParser()
logger       = Logger(reserve_line_num=0)

# ─────────────────────────────────────────────────────────────────────────────


intents = discord.Intents.default()
intents.message_content = True          # required to read message content

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    logger.print(f'Logged in as {client.user} (id: {client.user.id})', LogLevel.INFO)


@client.event
async def on_message(message: discord.Message):
    # Ignore the bot's own messages
    if message.author == client.user:
        return

    if message.channel.id in CHANNEL_IDS['codes']:
        code = message.content.strip()
        logger.print(f'Received message: "{code}" from {message.author} in #{message.channel.name}', LogLevel.INFO)

        # Only act on messages that look like a valid code; also normalises it
        code = code_parser.fix_code(code)
        if code is None:
            return
        page_url  = code_parser.get_video_url(code)
        cover_url = code_parser.get_cover_url(code)

        # Delete the user's message first
        try:
            await message.delete()
        except discord.Forbidden:
            logger.print(f'Missing "Manage Messages" permission in #{message.channel.name}', LogLevel.WARN)
        except discord.NotFound:
            pass  # already deleted

        # Ensure the cover directory exists (if we plan to save covers locally)
        if not os.path.isdir(COVER_SAVE_DIR['code']):
            os.makedirs(COVER_SAVE_DIR['code'], exist_ok=True)

        # Use the CodeParser to get the title and download the cover image
        title_flag, title = code_parser.get_title(code)
        has_cover         = code_parser.download_cover(code, f'{COVER_SAVE_DIR["code"]}/{code}.jpg')

        logger.print(f'Parsed code "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            # Couldn't resolve the code — silently ignore or optionally notify
            logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Could not find title for code "{code}"')
            return
        elif has_cover:
            await message.channel.send(content=f'**[{code} | {title}]({page_url})**', file=discord.File(f'{COVER_SAVE_DIR["code"]}/{code}.jpg', filename=f'{code}.jpg'))
        else:
            await message.channel.send(content=f'**[{code} | {title}]({page_url})**')
    elif message.channel.id in CHANNEL_IDS['comics']:
        code = message.content.strip()
        logger.print(f'Received message: "{code}" from {message.author} in #{message.channel.name}', LogLevel.INFO)

        # Only act on messages that look like a valid code; also normalises it
        if code is None:
            return
        match comic_parser.get_comic_type(code):
            case ComicType.NHENTAI: parser = NhentaiComicParser()
            # case ComicType.WNACG  : parser = WnacgComicParser()
            # case ComicType.JM     : parser = JmComicParser()
            case _:
                logger.print(f'Unsupported comic code "{code}"', LogLevel.WARN)
                await message.channel.send(content=f'Unsupported comic code "{code}"')
                return
        page_url  = parser.get_comic_url(code)

        # Delete the user's message first
        try:
            await message.delete()
        except discord.Forbidden:
            logger.print(f'Missing "Manage Messages" permission in #{message.channel.name}', LogLevel.WARN)
        except discord.NotFound:
            pass  # already deleted

        # Ensure the cover directory exists (if we plan to save covers locally)
        if not os.path.isdir(COVER_SAVE_DIR['comic']):
            os.makedirs(COVER_SAVE_DIR['comic'], exist_ok=True)

        # Use the ComicParser to get the title and download the cover image
        title_flag, title = parser.get_title(code)
        has_cover         = parser.download_cover(code, f'{COVER_SAVE_DIR["comic"]}/{code}.jpg')

        logger.print(f'Parsed code "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

        if not title_flag:
            # Couldn't resolve the code — silently ignore or optionally notify
            logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Could not find title for code "{code}"')
            return
        elif has_cover:
            await message.channel.send(content=f'**[{code} | {title}]({page_url})**', file=discord.File(f'{COVER_SAVE_DIR["comic"]}/{code}.jpg', filename=f'{code}.jpg'))
        else:
            await message.channel.send(content=f'**[{code} | {title}]({page_url})**')



client.run(BOT_TOKEN)