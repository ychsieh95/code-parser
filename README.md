# Code Parser

A Python CLI tool that parses video codes, fetches titles and cover images, and optionally sends notifications to Discord and Telegram.

## Features

- Parse one or more codes from command-line arguments
- Parse codes from an input text file
- Normalize common code formats (for example: `abc123` -> `ABC-123`, `FC2PPV12345` -> `FC2-PPV-12345`)
- Download cover images into the covers folder
- Send results to Discord webhook and/or Telegram channel
- Save results to an output file (with automatic backup if the file already exists)

## Project Structure

- main.py: CLI entry point
- src/code_parser.py: scraping, title lookup, and cover download logic
- src/discord_webhooker.py: Discord webhook sender with retry logic
- src/telegram_bot.py: Telegram sender with retry logic
- config/configs.py: runtime configuration values
- covers/: downloaded cover images

## Requirements

- Linux/macOS/Windows
- Python 3.10+
- Internet access to target sites and APIs

## Installation

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The project currently reads values from config/configs.py.

Required values:

- DISCORD_WEBHOOK_URL
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHANNEL_ID
- COVER_SAVE_DIR

Important:

- Replace existing tokens/webhook URLs with your own values before running.
- Do not commit real secrets to source control.
- If any secrets were previously exposed, rotate/revoke them immediately.

## Usage

Run with direct codes:

```bash
python main.py --codes ABP-123 FC2-PPV-12345
```

Run with an input file (one code per line):

```bash
python main.py --input-file codes.txt
```

Send notifications:

```bash
python main.py --codes ABP-123 --notify discord
python main.py --codes ABP-123 --notify telegram
python main.py --codes ABP-123 --notify all
```

Write results to output file:

```bash
python main.py --codes ABP-123 --output-file result.txt
```

Combine options:

```bash
python main.py --input-file codes.txt --notify all --output-file result.txt
```

## CLI Arguments

- --codes: list of codes to parse
- --input-file: path to text file containing codes
- --notify: discord, telegram, or all
- --output-file: path to output text file

## Notes

- Covers are saved as JPG files in the configured covers directory.
- Existing output files are renamed with a .bak-YYYYMMDD_HHMMSS suffix before new output is written.
- Optional proxy support is available through environment variables:
  - http_proxy
  - https_proxy

## Troubleshooting

- No results found:
  - verify code format and internet connectivity
- Notification failed:
  - verify webhook/token/chat ID values and permissions
- Cover download failed:
  - source may not provide an image for that code

## License

This project is licensed under the MIT License. See the LICENSE file for details.
