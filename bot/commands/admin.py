import discord
from bot.constants import MODE_CODE, MODE_COMIC
from bot.db import Database
from bot.logger import logger
from discord import app_commands
from discord.ext import commands
from utils.logger import LogLevel


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db  = db

    @app_commands.command(name='enable_parse_code', description='Enable code parsing mode for this channel')
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.channel_id)
    async def cmd_enable_parse_code(self, interaction: discord.Interaction):
        if await self.db.enable_mode(interaction.channel_id, MODE_CODE):
            logger.print(f'Channel {interaction.channel_id}: code parsing enabled', LogLevel.OK)
            await interaction.response.send_message('Code parsing is now **enabled** for this channel.')
        else:
            logger.print(f'Channel {interaction.channel_id}: code parsing already enabled', LogLevel.WARN)
            await interaction.response.send_message('Code parsing is already enabled for this channel.', ephemeral=True)

    @app_commands.command(name='enable_parse_comic', description='Enable comic parsing mode for this channel')
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.channel_id)
    async def cmd_enable_parse_comic(self, interaction: discord.Interaction):
        if await self.db.enable_mode(interaction.channel_id, MODE_COMIC):
            logger.print(f'Channel {interaction.channel_id}: comic parsing enabled', LogLevel.OK)
            await interaction.response.send_message('Comic parsing is now **enabled** for this channel.')
        else:
            logger.print(f'Channel {interaction.channel_id}: comic parsing already enabled', LogLevel.WARN)
            await interaction.response.send_message('Comic parsing is already enabled for this channel.', ephemeral=True)

    @app_commands.command(name='disable_parse_code', description='Disable code parsing mode for this channel')
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.channel_id)
    async def cmd_disable_parse_code(self, interaction: discord.Interaction):
        if await self.db.disable_mode(interaction.channel_id, MODE_CODE):
            logger.print(f'Channel {interaction.channel_id}: code parsing disabled', LogLevel.INFO)
            await interaction.response.send_message('Code parsing is now **disabled** for this channel.')
        else:
            logger.print(f'Channel {interaction.channel_id}: code parsing not enabled', LogLevel.WARN)
            await interaction.response.send_message('Code parsing is not enabled for this channel.', ephemeral=True)

    @app_commands.command(name='disable_parse_comic', description='Disable comic parsing mode for this channel')
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.channel_id)
    async def cmd_disable_parse_comic(self, interaction: discord.Interaction):
        if await self.db.disable_mode(interaction.channel_id, MODE_COMIC):
            logger.print(f'Channel {interaction.channel_id}: comic parsing disabled', LogLevel.INFO)
            await interaction.response.send_message('Comic parsing is now **disabled** for this channel.')
        else:
            logger.print(f'Channel {interaction.channel_id}: comic parsing not enabled', LogLevel.WARN)
            await interaction.response.send_message('Comic parsing is not enabled for this channel.', ephemeral=True)

    @app_commands.command(name='guild_status', description='Show parsing status for all channels in this server')
    @app_commands.default_permissions(administrator=True)
    async def cmd_guild_status(self, interaction: discord.Interaction):
        all_modes         = await self.db.get_all_modes()
        guild_channel_ids = {c.id for c in interaction.guild.channels}

        lines = [
            f'<#{cid}>: {", ".join(sorted(modes))}'
            for cid, modes in sorted(all_modes.items())
            if cid in guild_channel_ids and modes
        ]

        if lines:
            embed = discord.Embed(title='Guild Parsing Status', color=discord.Color.blue())
            embed.description = '\n'.join(lines)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message('No channels have parsing enabled in this server.', ephemeral=True)
