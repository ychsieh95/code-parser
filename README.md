# code-parser

A Discord bot and CLI tool that detects video/comic codes in messages, fetches titles and cover images, and posts formatted results.

---

## Project Structure

```
code-parser/
├── bot/                    # Discord bot
│   ├── main.py             # Entry point
│   ├── db.py               # SQLite persistence (channel settings)
│   ├── constants.py        # Shared mode constants
│   ├── logger.py           # Shared logger instance
│   ├── views.py            # ReadActionView (checkbox button on result messages)
│   └── commands/
│       ├── admin.py        # Enable/disable parsing, guild status, read action
│       ├── events.py       # Message handler (on_message)
│       └── general.py      # /help, /status, /updatelog
├── cli/
│   └── cli.py              # Batch CLI for code parsing
├── utils/                  # Shared utilities
│   ├── code_parser.py      # Video code scraper (missav.ws)
│   ├── comic_parser.py     # Comic scraper (nhentai, wnacg, jm)
│   ├── discord_webhooker.py
│   ├── telegram_bot.py
│   └── logger.py
├── config/
│   ├── settings.py         # Tokens and directory config (gitignored)
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
| `COVER_SAVE_DIR` | Dict of local paths for saving cover images (`code` and `comic` sub-keys) |
| `BOT_TOKEN` | Discord bot token |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL (CLI notify) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (CLI notify) |
| `TELEGRAM_CHANNEL_ID` | Telegram channel ID (CLI notify) |

The bot requires the **Server Members Intent** (privileged) to be enabled in the
[Discord Developer Portal](https://discord.com/developers/applications) for your application —
this is needed to determine who can see a channel for `/set_read_action`.

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
| `/enable_message_deletion` | Enable deletion of original messages for the current channel |
| `/disable_message_deletion` | Disable deletion of original messages for the current channel |
| `/set_read_action <mode>` | Set the action on a parsing result message once every non-bot member who can see the channel has marked it as read (`None` (default) / `Mark for delete` / `Delete`) |
| `/guild_status` | Show parsing status for all channels in the server |
| `/set_retry_num <count>` | Set number of fetch attempts per code (1–10) |
| `/set_latency <seconds>` | Set retry delay between fetch attempts (0.0–60.0s) |

**General**

| Command | Description |
|---|---|
| `/parse <codes…>` | Parse codes using the active modes for this channel |
| `/find_code <codes…>` | Fetch video code(s) directly, regardless of channel mode |
| `/find_comic <codes…>` | Fetch comic code(s) directly, regardless of channel mode |
| `/search <keywords> [num]` | Search for video codes by keywords (default 10 results) |
| `/get_latest [num]` | Fetch the latest video codes (default 10 results) |
| `/get_suggestion <code> [num]` | Fetch suggested codes for a given code (default 10) |
| `/status` | Show active parsing modes for the current channel |
| `/help` | Show available commands |
| `/updatelog` | Show recent update history |

### How It Works

When a parsing mode is enabled for a channel, the bot:

1. Intercepts every human message in that channel (bot and webhook messages are ignored)
2. Deletes the original message
3. Looks up the title and cover image for each code
4. Posts a formatted reply with a link and cover image

If `/set_read_action` is set to something other than `None` for the channel, each result
message also gets a "☑️ Mark as read" button. Once every non-bot member who can see the
channel has clicked it, the bot applies the configured action:

- **Mark for delete** — edits the message to `[REMOVED] <original content>` and strips the cover image
- **Delete** — deletes the message outright

Who has clicked is stored in SQLite (not just in memory), and the button is registered as a
persistent view on startup — so it keeps working, with progress intact, even after a bot restart.

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
python3 -m cli.cli --codes ABC-123 DEF-456
python3 -m cli.cli --input-file codes.txt --output-file results.txt
python3 -m cli.cli --input-file codes.txt --notify discord
python3 -m cli.cli --input-file codes.txt --notify all
```

**Arguments**

| Argument | Description |
|---|---|
| `--codes` | One or more codes to process |
| `--input-file` | Path to a text file with one code per line |
| `--output-file` | Path to save results (existing file is backed up automatically) |
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
