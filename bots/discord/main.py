import asyncio
import discord
import json
import os
import re
from pathlib import Path
from discord import app_commands
from config.settings import BOT_TOKEN
from src.comic_parser.comic_parser import ComicType, ComicParser, NhentaiComicParser
from src.code_parser.code_parser import CodeParser
from src.utils.logger import LogLevel, Logger

# ── Initialization ───────────────────────────────────────────────────────────
code_parser  = CodeParser()
comic_parser = ComicParser()
logger       = Logger(clear_previous=False, reserve_line_num=0)

MODE_CODE  = "code"
MODE_COMIC = "comic"

COVER_SAVE_DIR = {
    'code'  : './assets/covers/code',
    'comic' : './assets/covers/comics'
}
SETTINGS_FILE = Path(__file__).parent / "config/channel_settings.json"

# ─────────────────────────────────────────────────────────────────────────────

_CODE_PATTERNS = [
    re.compile(r'^([a-zA-Z]{2,5})[-]?(\d{3,5})$'),
    re.compile(r'^(FC2)[-]?(PPV)?[-]?(\d+)$'),
]


def _is_valid_code(code: str) -> bool:
    return any(p.match(code.upper()) for p in _CODE_PATTERNS)


def _load_channel_modes() -> dict[int, set[str]]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text())
        return {int(cid): set(modes) for cid, modes in data.items()}
    except Exception as e:
        logger.print(f'Failed to load channel settings: {e}', LogLevel.WARN)
        return {}


def _save_channel_modes() -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {str(cid): list(modes) for cid, modes in channel_modes.items() if modes}
        SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.print(f'Failed to save channel settings: {e}', LogLevel.WARN)


channel_modes: dict[int, set[str]] = _load_channel_modes()


def _toggle_mode(channel_id: int, mode: str, enable: bool) -> bool:
    '''Returns True if the state actually changed.'''
    modes = channel_modes.setdefault(channel_id, set())
    if enable:
        if mode in modes:
            logger.print(f'Channel {channel_id}: {mode} parsing already enabled', LogLevel.WARN)
            return False
        modes.add(mode)
        logger.print(f'Channel {channel_id}: {mode} parsing enabled', LogLevel.OK)
    else:
        if mode not in modes:
            logger.print(f'Channel {channel_id}: {mode} parsing already disabled', LogLevel.WARN)
            return False
        modes.discard(mode)
        logger.print(f'Channel {channel_id}: {mode} parsing disabled', LogLevel.INFO)
    _save_channel_modes()
    return True


intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree   = app_commands.CommandTree(client)


@client.event
async def on_ready():
    for guild in client.guilds:
        synced = await tree.sync(guild=guild)
        logger.print(f'Synced {len(synced)} commands to guild {guild.name} ({guild.id})', LogLevel.INFO)
    await tree.sync()
    logger.print(f'Logged in as {client.user} (id: {client.user.id}) — slash commands synced.', LogLevel.INFO)


# ── Slash commands ────────────────────────────────────────────────────────────

@tree.command(name='enable_parse_code', description='Enable code parsing mode for this channel')
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_parse_code(interaction: discord.Interaction):
    if _toggle_mode(interaction.channel_id, MODE_CODE, True):
        await interaction.response.send_message('Code parsing is now **enabled** for this channel.')
    else:
        await interaction.response.send_message('Code parsing is already enabled for this channel.', ephemeral=True)


@tree.command(name='enable_parse_comic', description='Enable comic parsing mode for this channel')
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_parse_comic(interaction: discord.Interaction):
    if _toggle_mode(interaction.channel_id, MODE_COMIC, True):
        await interaction.response.send_message('Comic parsing is now **enabled** for this channel.')
    else:
        await interaction.response.send_message('Comic parsing is already enabled for this channel.', ephemeral=True)


@tree.command(name='disable_parse_code', description='Disable code parsing mode for this channel')
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_disable_parse_code(interaction: discord.Interaction):
    if _toggle_mode(interaction.channel_id, MODE_CODE, False):
        await interaction.response.send_message('Code parsing is now **disabled** for this channel.')
    else:
        await interaction.response.send_message('Code parsing is not enabled for this channel.', ephemeral=True)


@tree.command(name='disable_parse_comic', description='Disable comic parsing mode for this channel')
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_disable_parse_comic(interaction: discord.Interaction):
    if _toggle_mode(interaction.channel_id, MODE_COMIC, False):
        await interaction.response.send_message('Comic parsing is now **disabled** for this channel.')
    else:
        await interaction.response.send_message('Comic parsing is not enabled for this channel.', ephemeral=True)


@tree.command(name='status', description='Show current parsing status for this channel')
async def cmd_status(interaction: discord.Interaction):
    modes = channel_modes.get(interaction.channel_id, set())
    if modes:
        tags = ', '.join(sorted(modes))
        await interaction.response.send_message(f'**Parsing status:** {tags}', ephemeral=True)
    else:
        await interaction.response.send_message('No parsing mode is enabled for this channel.', ephemeral=True)


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need the **Manage Channels** permission to use this command.", ephemeral=True
        )
    else:
        raise error


# ── Message handler ───────────────────────────────────────────────────────────

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    active_modes = channel_modes.get(message.channel.id, set())
    if not active_modes:
        return

    code = message.content.strip()
    logger.print(f'Received message: "{code}" from {message.author} in #{message.channel.name}', LogLevel.INFO)

    if MODE_CODE in active_modes and _is_valid_code(code):
        await _handle_code(message, code_parser.fix_code(code))
    elif MODE_COMIC in active_modes and comic_parser.get_comic_type(code) != ComicType.UNKNOWN:
        await _handle_comic(message, code, comic_parser.get_comic_type(code))


async def _delete_message(message: discord.Message):
    try:
        await message.delete()
    except discord.Forbidden:
        logger.print(f'Missing "Manage Messages" permission in #{message.channel.name}', LogLevel.WARN)
    except discord.NotFound:
        pass


async def _handle_code(message: discord.Message, code: str):
    page_url   = code_parser.get_video_url(code)
    cover_path = f'{COVER_SAVE_DIR["code"]}/{code}.jpg'

    await _delete_message(message)
    os.makedirs(COVER_SAVE_DIR['code'], exist_ok=True)

    title_flag, title = await asyncio.to_thread(code_parser.get_title, code)
    has_cover         = await asyncio.to_thread(code_parser.download_cover, code, cover_path)
    logger.print(f'Parsed code "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

    if not title_flag:
        logger.print(f'Could not find title for code "{code}"', LogLevel.WARN)
        await message.channel.send(content=f'Could not find title for code "{code}"')
        return

    content = f'**[{code} | {title}]({page_url})**'
    if has_cover and os.path.isfile(cover_path):
        await message.channel.send(content=content, file=discord.File(cover_path, filename=f'{code}.jpg'))
    else:
        await message.channel.send(content=content)


async def _handle_comic(message: discord.Message, code: str, comic_type: ComicType):
    match comic_type:
        case ComicType.NHENTAI:
            parser = NhentaiComicParser()
        case _:
            logger.print(f'Unsupported comic type for code "{code}"', LogLevel.WARN)
            await message.channel.send(content=f'Unsupported comic code "{code}"')
            return

    page_url   = parser.get_comic_url(code)
    cover_path = f'{COVER_SAVE_DIR["comic"]}/{code}.jpg'

    await _delete_message(message)
    os.makedirs(COVER_SAVE_DIR['comic'], exist_ok=True)

    title_flag, title = await asyncio.to_thread(parser.get_title, code)
    has_cover         = await asyncio.to_thread(parser.download_cover, code, cover_path)
    logger.print(f'Parsed comic "{code}": title="{title}", has_cover={has_cover}', LogLevel.INFO)

    if not title_flag:
        logger.print(f'Could not find title for comic "{code}"', LogLevel.WARN)
        await message.channel.send(content=f'Could not find title for comic "{code}"')
        return

    content = f'**[{code} | {title}]({page_url})**'
    if has_cover and os.path.isfile(cover_path):
        await message.channel.send(content=content, file=discord.File(cover_path, filename=f'{code}.jpg'))
    else:
        await message.channel.send(content=content)


client.run(BOT_TOKEN)
