# code-parser

A Discord bot and CLI tool that detects video/comic codes in messages, fetches titles and cover images, and posts formatted results.

---

## Project Structure

```
code-parser/
├── bot/                    # Discord bot
│   ├── main.py             # Entry point
│   ├── db.py               # SQLite persistence (channel settings)
│   └── commands/
│       ├── admin.py        # Enable/disable parsing, guild status
│       ├── events.py       # Message handler (on_message)
│       └── general.py      # /help, /status, /updatelog
├── utils/                  # Shared utilities
│   ├── code_parser.py      # Video code scraper (missav.ws)
│   ├── comic_parser.py     # Comic scraper (nhentai, wnacg, jm)
│   ├── discord_webhooker.py
│   ├── telegram_bot.py
│   └── logger.py
├── scripts/
│   └── cli.py              # Batch CLI for code parsing
├── config/
│   ├── settings.py         # Tokens and directory config
│   └── settings.example.py
├── assets/
│   └── images/             # Bot icon and banner
└── deploy/
    └── discord-bot-code-parser.service  # systemd unit
```

---

## Setup

**1. Create a virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Configure settings**

```bash
cp config/settings.example.py config/settings.py
```

Edit `config/settings.py` and fill in:

| Key | Description |
|---|---|
| `BOT_TOKEN` | Discord bot token |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL (CLI notify) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (CLI notify) |
| `TELEGRAM_CHANNEL_ID` | Telegram channel ID (CLI notify) |
| `COVER_SAVE_DIR` | Local path to save cover images |

---

## Discord Bot

### Running

```bash
python3 -m bot.main
```

For development (instant slash command sync to a single guild):

```bash
DEV_GUILD_ID=123456789 python3 -m bot.main
```

### Slash Commands

**Admin** (requires Administrator permission)

| Command | Description |
|---|---|
| `/enable_parse_code` | Enable video code parsing for the current channel |
| `/disable_parse_code` | Disable video code parsing for the current channel |
| `/enable_parse_comic` | Enable comic parsing for the current channel |
| `/disable_parse_comic` | Disable comic parsing for the current channel |
| `/guild_status` | Show parsing status for all channels in the server |

**General**

| Command | Description |
|---|---|
| `/status` | Show active parsing modes for the current channel |
| `/help` | Show available commands |
| `/updatelog` | Show recent update history |

### How It Works

When a parsing mode is enabled for a channel, the bot:
1. Intercepts every message in that channel
2. Deletes the original message
3. Looks up the title and cover image for each code
4. Posts a formatted reply with a link and cover image

**Supported code formats**

| Type | Examples |
|---|---|
| Video | `ABC-123`, `ABCD-1234`, `FC2-PPV-123456` |
| Comic (nhentai) | `123456`, `n123456` |
| Comic (wnacg) | `w123456` *(not yet supported)* |
| Comic (JM) | `jm123456` *(not yet supported)* |

### systemd Deployment

Copy the service file and enable it:

```bash
cp deploy/discord-bot-code-parser.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now discord-bot-code-parser
```

---

## CLI

Batch-process codes and optionally notify via Discord webhook or Telegram.

```bash
python3 -m scripts.cli --codes ABC-123 DEF-456
python3 -m scripts.cli --input-file codes.txt --output-file results.txt
python3 -m scripts.cli --input-file codes.txt --notify discord
python3 -m scripts.cli --input-file codes.txt --notify all
```

**Arguments**

| Argument | Description |
|---|---|
| `--codes` | One or more codes to process |
| `--input-file` | Path to a text file with one code per line |
| `--output-file` | Path to save results (existing file is backed up) |
| `--notify` | Send results via `discord`, `telegram`, or `all` |

---

## Requirements

| Package | Used for |
|---|---|
| `aiosqlite` | Async SQLite for channel settings |
| `beautifulsoup4` | HTML parsing for title/cover scraping |
| `curl_cffi` | HTTP client with browser impersonation |
| `discord.py` | Discord bot framework |
| `discord-webhook` | Discord webhook client (CLI) |
| `httpx` | Async HTTP for Telegram API |
| `python-telegram-bot` | Telegram bot client |
| `requests` | HTTP exceptions used by webhook client |
