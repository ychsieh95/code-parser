import discord as discord
import os
from config.settings import COVER_SAVE_DIR, BOT_TOKEN, ALLOWED_CHANNEL_IDS
from src.code_parser.code_parser import CodeParser
from src.code_parser.logger import LogLevel, Logger


# ── Configuration ────────────────────────────────────────────────────────────
PAGE_URL  = 'https://missav.ws/{code}'
COVER_URL = 'https://fourhoi.com/{code}/cover-n.jpg'

# ── Initialization ───────────────────────────────────────────────────────────
code_parser = CodeParser()
logger      = Logger(reserve_line_num=0)

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

    if message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    code = message.content.strip()
    logger.print(f'Received message: "{code}" from {message.author} in #{message.channel.name}', LogLevel.INFO)

    # Only act on messages that look like a valid code; also normalises it
    code = code_parser.fix_code(code)
    if code is None:
        return
    page_url  = PAGE_URL.format(code=code)
    cover_url = COVER_URL.format(code=code)

    # Delete the user's message first
    try:
        await message.delete()
    except discord.Forbidden:
        logger.print(f'Missing "Manage Messages" permission in #{message.channel.name}', LogLevel.WARN)
    except discord.NotFound:
        pass  # already deleted

    # Ensure the cover directory exists (if we plan to save covers locally)
    if not os.path.isdir(COVER_SAVE_DIR):
        os.makedirs(COVER_SAVE_DIR, exist_ok=True)

    # Use the CodeParser to get the title and download the cover image
    title_flag, title = code_parser.get_title(code)
    has_cover         = code_parser.download_cover(code, f'{COVER_SAVE_DIR}/{code}.jpg')

    logger.print(f'Parsed code "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

    if not title_flag:
        # Couldn't resolve the code — silently ignore or optionally notify
        logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
        await message.channel.send(content=f'Could not find title for code "{code}"')
        return
    elif has_cover:
        await message.channel.send(content=f'**[{code} | {title}]({page_url})**', file=discord.File(f'{COVER_SAVE_DIR}/{code}.jpg', filename=f'{code}.jpg'))
    else:
        await message.channel.send(content=f'**[{code} | {title}]({page_url})**')


client.run(BOT_TOKEN)