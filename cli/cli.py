import argparse
import asyncio
import os
import sys
from config.settings import COVER_SAVE_DIR, DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from datetime import datetime
from utils.code_parser import CodeParser
from utils.discord_webhooker import DiscordWebhooker
from utils.logger import Logger, LogLevel
from utils.telegram_bot import TelegramBot


logger = Logger(reserve_line_num=0)


def append_to_file(file_path: str, message: str) -> None:
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(message + '\n')


def get_full_log(code: str, title: str, url: str) -> str:
    return f'{code} | {title}\nUrl: {url}'


def get_discord_log(code: str, title: str, url: str) -> str:
    title = title.replace('_', '\\_') \
                 .replace('*', '\\*') \
                 .replace('`', '\\`') \
                 .replace('~', '\\~') \
                 .replace('[', '［') \
                 .replace(']', '］')
    return f'**[{code} | {title}]({url})**'


async def main() -> None:
    parser = argparse.ArgumentParser(description='Code Parser Script')
    parser.add_argument('--codes'      , nargs='+', type=str, help='Codes to parse')
    parser.add_argument('--input-file' ,            type=str, help='Path to the input file containing codes')
    parser.add_argument('--notify'     , nargs='?', type=str, default=None, choices=['discord', 'telegram', 'all'])
    parser.add_argument('--output-file',            type=str, help='Path to the output file to save results')
    args = parser.parse_args()
    logger.print(args, level=LogLevel.INFO)

    if not args.codes and not args.input_file:
        logger.print('Please provide either a code or an input file!', LogLevel.FAILED)
        sys.exit(1)

    codes = list(args.codes or [])
    if args.input_file:
        if not os.path.exists(args.input_file):
            logger.print(f'{args.input_file} file not found!', LogLevel.FAILED)
            sys.exit(1)
        with open(args.input_file, 'r') as file:
            codes.extend(line.strip() for line in file if line.strip())

    codes = sorted(set(code.upper() for code in codes))
    if not codes:
        logger.print('No codes found in the input file!', LogLevel.FAILED)
        sys.exit(1)

    code_parser = CodeParser()
    dc_bot      = DiscordWebhooker(url=DISCORD_WEBHOOK_URL, retry_num=1)
    tg_bot      = TelegramBot(token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHANNEL_ID, retry_num=1)
    codes       = code_parser.fix_codes(codes)

    if args.output_file and os.path.exists(args.output_file):
        os.rename(args.output_file, f'{args.output_file}.bak-{datetime.now().strftime("%Y%m%d_%H%M%S")}')

    os.makedirs(COVER_SAVE_DIR['code'], exist_ok=True)

    for i, code in enumerate(codes):
        title_flag, title = code_parser.get_title(code)
        cover_path        = f'{COVER_SAVE_DIR["code"]}/{code}.jpg'

        if title_flag:
            title = title or code
            has_cover = code_parser.download_cover(code, cover_path)
            message = f'{code} | {title}'
        else:
            has_cover = False
            message = f'{code} | 404 NOT FOUND'

        url           = code_parser.get_video_url(code)
        discord_text  = get_discord_log(code, title, url) if title_flag else message
        telegram_text = get_full_log(code, title, url)    if title_flag else message

        logger.print(message, level=LogLevel.OK)

        if args.notify in ['discord', 'all']:
            await dc_bot.send_message(
                text=discord_text,
                image_paths=[cover_path] if has_cover else []
            )
            await asyncio.sleep(1)

        if args.notify in ['telegram', 'all']:
            if has_cover:
                await tg_bot.send_photo(cover_path, caption=telegram_text)
            else:
                await tg_bot.send_message(text=telegram_text)
            await asyncio.sleep(1)

        if args.output_file:
            append_to_file(args.output_file, message)
            if i < len(codes) - 1:
                append_to_file(args.output_file, '\n\n')


if __name__ == '__main__':
    asyncio.run(main())
