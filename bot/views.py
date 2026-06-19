import discord
from bot.constants import READ_ACTION_AUTO_DELETE
from bot.db import Database


class ReadActionView(discord.ui.View):
    """Tracks per-message checkbox clicks; once every non-bot member who can see
    the channel has clicked, applies the channel's configured read-action mode."""

    def __init__(self, db: Database, channel: discord.abc.GuildChannel):
        super().__init__(timeout=None)
        self.db       = db
        self.channel  = channel
        self.read_by: set[int] = set()
        self._refresh_label()

    def _eligible_user_ids(self) -> set[int]:
        return {m.id for m in getattr(self.channel, 'members', []) if not m.bot}

    def _refresh_label(self):
        eligible = self._eligible_user_ids()
        self.read_button.label = f'☑️ Mark as read ({len(self.read_by & eligible)}/{len(eligible)})'

    @discord.ui.button(style=discord.ButtonStyle.secondary)
    async def read_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.bot:
            await interaction.response.defer()
            return

        self.read_by.add(interaction.user.id)
        eligible = self._eligible_user_ids()

        if eligible and eligible.issubset(self.read_by):
            self.stop()
            message = interaction.message
            mode    = self.db.read_action(self.channel.id)
            if mode == READ_ACTION_AUTO_DELETE:
                await interaction.response.edit_message(
                    content=f'[REMOVED] {message.content}', attachments=[], view=None
                )
            else:
                await interaction.response.defer()
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
        else:
            self._refresh_label()
            await interaction.response.edit_message(view=self)
