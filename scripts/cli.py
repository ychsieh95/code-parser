import argparse
import asyncio
import os
from config.settings import COVER_SAVE_DIR, DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from datetime import datetime
from src.code_parser.code_parser import CodeParser
from src.code_parser.discord_webhooker import DiscordWebhooker
from src.code_parser.logger import Logger, LogLevel
from src.code_parser.telegram_bot import TelegramBot


dc_bot      = DiscordWebhooker(url=DISCORD_WEBHOOK_URL, retry_num=1)
tg_bot      = TelegramBot(token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHANNEL_ID, retry_num=1)

code_parser = CodeParser()
logger      = Logger(reserve_line_num=0)


def append_to_file(file_path: str, message: str) -> None:
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(message + '\n')


def init_directories() -> None:
    if not os.path.exists(COVER_SAVE_DIR):
        os.makedirs(COVER_SAVE_DIR)


def get_full_log(code: str, title: str) -> str:
    return f'{code} | {title}\nUrl: {CodeParser().get_url(code)}'


def get_discord_log(code: str, title: str) -> str:
    title = title.replace('_', '\\_') \
                 .replace('*', '\\*') \
                 .replace('`', '\\`') \
                 .replace('~', '\\~') \
                 .replace('[', '［') \
                 .replace(']', '］')
    return f'**[{code} | {title}]({CodeParser().get_url(code)})**'


async def main() -> None:
    parser = argparse.ArgumentParser(description='Code Parser Script')
    parser.add_argument('--codes'      , nargs='+', type=str, help='Codes to parse')
    parser.add_argument('--input-file' ,            type=str, help='Path to the input file containing codes')
    parser.add_argument('--notify'     , nargs='?', type=str, default=None, choices=['discord', 'telegram', 'all'])
    parser.add_argument('--output-file',            type=str, help='Path to the output file to save results')
    args = parser.parse_args()
    logger.print(args, level=LogLevel.INFO)


    # Validate input arguments
    if not args.codes and not args.input_file:
        logger.print('Please provide either a code or an input file!', LogLevel.FAILED)
        exit(1)

    # Read codes from input argument and input file
    codes = []
    if args.codes:
        codes = args.codes
    if args.input_file:
        if not os.path.exists(args.input_file):
            logger.print(f'{args.input_file} file not found!', LogLevel.FAILED)
            exit(1)
        with open(args.input_file, 'r') as file:
            [codes.append(line.strip()) for line in file if line.strip()]
    codes = [code.upper() for code in codes]
    codes = sorted(list(set(codes)))

    # Check if any codes were found, and fix codes
    if not codes:
        logger.print('No codes found in the input file!', LogLevel.FAILED)
        exit(1)
    codes = code_parser.fix_codes(codes)

    # Backup existing output file
    if args.output_file:
        if os.path.exists(args.output_file):
            os.rename(args.output_file, f'{args.output_file}.bak-{datetime.now().strftime("%Y%m%d_%H%M%S")}')

    # Process each code
    init_directories()
    for code in codes:
        title_flag, title = code_parser.get_title(code)
        cover_path        = f'{COVER_SAVE_DIR}/{code}.jpg'
        message           = ''
        if title_flag:
            _       = code_parser.download_cover(code, cover_path)
            message = f'{code} | {title}'
        else:
            message = f'{code} | 404 NOT FOUND'

        if title_flag:
            logger.print(message, level=LogLevel.OK)
            if args.notify in ['discord', 'all']:
                await dc_bot.send_message(text=get_discord_log(code=code, title=title), image_paths=[cover_path] if os.path.exists(cover_path) else [])
                await asyncio.sleep(1)  # To avoid hitting Discord rate limits
            if args.notify in ['telegram', 'all']:
                await tg_bot.send_message(text=get_full_log(code=code, title=title), image_path=cover_path if os.path.exists(cover_path) else None)
                await asyncio.sleep(1)  # To avoid hitting Telegram rate limits
            if args.output_file:
                append_to_file(args.output_file, message)
        else:
            logger.print(message, level=LogLevel.OK)
            if args.notify in ['discord', 'all']:
                await dc_bot.send_message(text=message, image_paths=[cover_path] if os.path.exists(cover_path) else [])
                await asyncio.sleep(1)  # To avoid hitting Discord rate limits
            if args.notify in ['telegram', 'all']:
                await tg_bot.send_message(text=message, image_path=cover_path if os.path.exists(cover_path) else None)
                await asyncio.sleep(1)  # To avoid hitting Telegram rate limits
            if args.output_file:
                append_to_file(args.output_file, message)
        if code != codes[-1]:
            if args.output_file:
                append_to_file(args.output_file, '\n\n')


if __name__ == '__main__':
    asyncio.run(main())