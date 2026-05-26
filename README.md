# Code Parser

![Code Parser](assets/bot-banner.png)

A Python toolkit for parsing video/comic codes — fetches titles and cover images, sends notifications to Discord and Telegram, and includes a Discord bot for channel-based monitoring.

## Features

- Parse one or more video codes from command-line arguments or an input file
- Normalize common code formats (e.g. `abc123` → `ABC-123`, `FC2PPV12345` → `FC2-PPV-12345`)
- Download cover images
- Send results to a Discord webhook and/or Telegram channel
- Save results to an output file (existing files are backed up automatically)
- Discord bot with per-channel slash commands for live code/comic monitoring
- Comic support: nhentai (`123456` / `n123456`); WNACG and JM codes are recognized but not yet implemented

## Project Structure

```text
code-parser/
├── assets/
│   └── covers/
│       ├── code/               # Downloaded video covers
│       └── comics/
│           ├── nhentai/
│           ├── wnacg/
│           └── JM/
├── bots/
│   └── discord/
│       ├── config/             # channel_settings.json (auto-created, gitignored)
│       ├── main.py             # Discord bot entry point
│       └── README.md
├── config/
│   └── settings.example.py    # Configuration template (copy to settings.py)
├── deploy/
│   └── discord-bot-code-parser.service
├── scripts/
│   └── cli.py                  # CLI entry point (video codes)
├── src/
│   ├── code_parser/
│   │   ├── code_parser.py      # Video code scraping & cover download
│   │   ├── discord_webhooker.py
│   │   └── telegram_bot.py
│   ├── comic_parser/
│   │   └── comic_parser.py     # Comic code scraping & cover download
│   └── utils/
│       └── logger.py
├── quick-build.sh              # One-step deploy & systemd setup
└── requirements.txt
```

## Requirements

- Python 3.10+
- Internet access to target sites

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Deploy (Linux + systemd)

`quick-build.sh` copies the project to `~/.local/bin/code-parser`, creates a virtualenv, installs dependencies, and enables the Discord bot as a user-level systemd service in one step:

```bash
bash quick-build.sh
```

## Configuration

Copy the example config and fill in your values:

```bash
cp config/settings.example.py config/settings.py
```

| Key                  | Description                                          |
|----------------------|------------------------------------------------------|
| `BOT_TOKEN`          | Discord bot token (used by the Discord bot)          |
| `DISCORD_WEBHOOK_URL`| Discord webhook URL (used by the CLI)                |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (used by the CLI)                 |
| `TELEGRAM_CHANNEL_ID`| Telegram channel ID (used by the CLI)                |
| `COVER_SAVE_DIR`     | Paths for downloaded cover images                    |

> `config/settings.py` is gitignored — never commit it.

## CLI Usage

The CLI handles video codes. Comic parsing is available through the Discord bot.

```bash
# Parse codes directly
python3 -m scripts.cli --codes ABP-123 FC2-PPV-12345

# Parse from a file (one code per line)
python3 -m scripts.cli --input-file codes.txt

# Send notifications
python3 -m scripts.cli --codes ABP-123 --notify discord
python3 -m scripts.cli --codes ABP-123 --notify telegram
python3 -m scripts.cli --codes ABP-123 --notify all

# Save results to a file
python3 -m scripts.cli --codes ABP-123 --output-file result.txt
```

## Discord Bot

See [bots/discord/README.md](bots/discord/README.md) for setup and usage.

```bash
source .venv/bin/activate
python3 -m bots.discord.main
```

## Notes

- Proxy support via `http_proxy` / `https_proxy` environment variables.
- Video covers are saved as `.jpg` under `assets/covers/code/`.
- Comic covers are saved under `assets/covers/comics/{nhentai,wnacg,JM}/`.
- Output files are backed up with a `.bak-YYYYMMDD_HHMMSS` suffix before being overwritten.
- Discord bot channel settings persist in `bots/discord/config/channel_settings.json` and are restored on restart.

## License

MIT License. See [LICENSE](LICENSE) for details.
