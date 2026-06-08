import discord
from bot.db import Database
from discord import app_commands
from discord.ext import commands


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db  = db

    @app_commands.command(name='updatelog', description='Show recent bot update history')
    async def cmd_updatelog(self, interaction: discord.Interaction):
        embed = discord.Embed(title='Update Log', color=discord.Color.green())
        embed.add_field(
            name='Latest',
            value=(
                '• Refactored into modular Cog structure\n'
                '• Replaced JSON storage with SQLite (persistent + concurrent-safe)\n'
                '• Added `/guild_status` for server-wide channel overview\n'
                '• Added 5s cooldown on toggle commands\n'
                '• Added SIGTERM graceful shutdown\n'
                '• Added `DEV_GUILD_ID` env var for instant dev sync'
            ),
            inline=False
        )
        embed.add_field(
            name='Previous',
            value=(
                '• Added `/updatelog` command\n'
                '• Moved banner and icon assets to `assets/images/`\n'
                '• README updated with full slash command reference'
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='help', description='Show available commands and usage')
    async def cmd_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title='Bot Commands', color=discord.Color.blurple())
        embed.add_field(
            name='Admin Commands',
            value=(
                '`/enable_parse_code` — Enable video code parsing for this channel\n'
                '`/disable_parse_code` — Disable video code parsing for this channel\n'
                '`/enable_parse_comic` — Enable comic code parsing for this channel\n'
                '`/disable_parse_comic` — Disable comic code parsing for this channel\n'
                '`/enable_message_deletion` — Enable deletion of original messages for this channel\n'
                '`/disable_message_deletion` — Disable deletion of original messages for this channel\n'
                '`/guild_status` — Show parsing status for all channels in this server'
            ),
            inline=False
        )
        embed.add_field(
            name='General Commands',
            value=(
                '`/find_code <codes…>` — Fetch video code(s) directly\n'
                '`/find_comic <codes…>` — Fetch comic code(s) directly\n'
                '`/search <keywords> [num]` — Search for video codes by keywords\n'
                '`/get_latest [num]` — Fetch the latest video codes\n'
                '`/get_suggestion <code> [num]` — Fetch suggested codes for a code\n'
                '`/status` — Show active parsing modes for this channel\n'
                '`/updatelog` — Show recent bot update history\n'
                '`/help` — Show this help message'
            ),
            inline=False
        )
        embed.add_field(
            name='How It Works',
            value=(
                'When a parsing mode is enabled, the bot automatically detects matching codes in messages, '
                'deletes the original, and posts a formatted result with title and cover.'
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name='sync')
    @commands.is_owner()
    async def cmd_sync(self, ctx: commands.Context):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        status = await ctx.send('🔄 Syncing commands...')
        synced = await self.bot.tree.sync()
        await status.edit(content=f'✅ Synced {len(synced)} global commands.')

    @app_commands.command(name='status', description='Show current parsing status for this channel')
    async def cmd_status(self, interaction: discord.Interaction):
        modes     = self.db.get_modes(interaction.channel_id)
        deletion  = self.db.message_deletion_enabled(interaction.channel_id)
        modes_str = ", ".join(sorted(modes)) if modes else 'none'
        await interaction.response.send_message(
            f'**Parsing status:** {modes_str}\n**Message deletion:** {"enabled" if deletion else "disabled"}',
            ephemeral=True
        )
