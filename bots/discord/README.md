# Discord Bot

A Discord bot that monitors channels for video/comic codes, looks up titles and cover images, and posts formatted results.

## How It Works

1. Enable a parsing mode for a channel via slash command.
2. A user posts a code (e.g. `SSIS-531` or `123456`) in that channel.
3. The bot deletes the original message.
4. The bot fetches the title and downloads the cover image.
5. It replies with a bold markdown link and attaches the cover if available.

Channel settings are persisted in `config/channel_settings.json` and restored on restart.

## Slash Commands

| Command | Permission | Description |
|---|---|---|
| `/enable_parse_code` | Manage Channels | Enable video code parsing for this channel |
| `/enable_parse_comic` | Manage Channels | Enable comic code parsing for this channel |
| `/disable_parse_code` | Manage Channels | Disable video code parsing for this channel |
| `/disable_parse_comic` | Manage Channels | Disable comic code parsing for this channel |
| `/status` | Everyone | Show active parsing modes for this channel |

A channel can have both modes active at the same time. Code mode is checked first.

## Running

```bash
source .venv/bin/activate
python3 -m bots.discord.main
```

## Required Bot Permissions

- **Read Messages / View Channels** — receive messages
- **Send Messages** — post results
- **Manage Messages** — delete the user's original message
- **Attach Files** — send cover images

Enable the **Message Content Intent** in the Discord Developer Portal under your application's *Bot* settings.

## Configuration

`BOT_TOKEN` is read from `config/settings.py` at the project root.

```python
BOT_TOKEN = "your-token-here"
```
