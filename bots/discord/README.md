# Discord Bot

A Discord bot that listens for video codes in designated channels, looks up the title via `CodeParser`, downloads the cover image, and posts a formatted message.

## How It Works

1. A user posts a code (e.g. `ssis-531`) in an allowed channel.
2. The bot normalises the code via `CodeParser.fix_code()`.
3. The user's original message is deleted.
4. The bot fetches the title from `missav.ws` and downloads the cover from `fourhoi.com`.
5. It replies with the title as a bold markdown link, attaching the cover image if available.

## Configuration

Edit the constants at the top of `bot.py`:

| Constant             | Description                                      |
|----------------------|--------------------------------------------------|
| `BOT_TOKEN`          | Discord bot token                                |
| `ALLOWED_CHANNEL_IDS`| Set of channel IDs the bot will respond in       |
| `PAGE_URL`           | URL template for the video page                  |
| `COVER_URL`          | URL template for the cover image                 |

`COVER_SAVE_DIR` is read from `config/configs.py` (default: `./covers`).

## Running

```bash
source .venv/bin/activate
python3 -m bot.discord.bot
```

## Required Permissions

The bot requires the following Discord permissions:

- **Read Messages / View Channels** — to receive messages
- **Send Messages** — to post the result
- **Manage Messages** — to delete the user's original message
- **Attach Files** — to send the cover image

Enable the **Message Content Intent** in the Discord Developer Portal under your application's *Bot* settings.
