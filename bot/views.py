import discord
from bot.constants import READ_ACTION_AUTO_DELETE
from bot.db import Database

_READ_BUTTON_CUSTOM_ID = 'read_action:mark_read'


class ReadActionView(discord.ui.View):
    """Persistent 'mark as read' checkbox for parsing result messages.

    Read receipts live in the database keyed by message id, not on the view instance,
    so a single registered instance can keep handling clicks on old messages across
    bot restarts (discord.py routes interactions to it by the button's custom_id)."""

    def __init__(self, db: Database, channel: discord.abc.GuildChannel | None = None):
        super().__init__(timeout=None)
        self.db = db
        if channel is not None:
            self.read_button.label = self._label(set(), self._eligible_user_ids(channel))

    @staticmethod
    def _eligible_user_ids(channel) -> set[int]:
        return {m.id for m in getattr(channel, 'members', []) if not m.bot}

    @staticmethod
    def _label(read_by: set[int], eligible: set[int]) -> str:
        return f'☑️ Mark as read ({len(read_by & eligible)}/{len(eligible)})'

    @discord.ui.button(label='☑️ Mark as read', style=discord.ButtonStyle.secondary, custom_id=_READ_BUTTON_CUSTOM_ID)
    async def read_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.bot:
            await interaction.response.defer()
            return

        message  = interaction.message
        channel  = interaction.channel
        await self.db.add_read_receipt(message.id, interaction.user.id)
        read_by  = self.db.get_read_receipts(message.id)
        eligible = self._eligible_user_ids(channel)

        if eligible and eligible.issubset(read_by):
            mode = self.db.read_action(channel.id)
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
            await self.db.clear_read_receipts(message.id)
        else:
            button.label = self._label(read_by, eligible)
            await interaction.response.edit_message(view=self)
