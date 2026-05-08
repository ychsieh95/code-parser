

import httpx
import asyncio
from typing import List, Optional
from telegram import InputMediaPhoto
from telegram.ext import Application


class TelegramBot:
    '''
    Telegram Bot utility for sending messages, media, and managing chat state with retry logic.
    '''
    def __init__(self, token: str, chat_id: str, retry_num: int = 3):
        self.token: str = token
        self.chat_id: str = chat_id
        self.application = Application.builder().token(token).build()
        self.message_id: Optional[int] = None
        self.retry_num: int = retry_num
        self.debug: bool = False


    async def send_message(self, text: str, disable_notification: bool = False) -> int:
        '''Send a message with retry logic and error logging.'''
        for i in range(self.retry_num):
            try:
                message = await self.application.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    disable_notification=disable_notification
                )
                self.message_id = message.message_id
                return self.message_id
            except Exception as e:
                await self._handle_retry_error('send_message', i, e)


    async def send_media_group(self, medias: List[InputMediaPhoto], disable_notification: bool = False) -> int:
        '''Send a media group with retry logic.'''
        for i in range(self.retry_num):
            try:
                messages = await self.application.bot.send_media_group(
                    chat_id=self.chat_id,
                    media=medias,
                    disable_notification=disable_notification
                )
                self.message_id = messages[0].message_id
                return self.message_id
            except Exception as e:
                await self._handle_retry_error('send_media_group', i, e)


    async def pin_message(self, message_id: Optional[int] = None, disable_notification: bool = False) -> None:
        '''Pin a message in the chat. If message_id is None, pin the last message.'''
        mid = message_id if message_id is not None else self.message_id
        for i in range(self.retry_num):
            try:
                await self.application.bot.pin_chat_message(
                    chat_id=self.chat_id,
                    message_id=mid,
                    disable_notification=disable_notification
                )
                return
            except Exception as e:
                await self._handle_retry_error('pin_message', i, e)


    async def unpin_all_messages(self) -> None:
        '''Unpin all messages in the chat.'''
        for i in range(self.retry_num):
            try:
                await self.application.bot.unpin_all_chat_messages(chat_id=self.chat_id)
                return
            except Exception as e:
                await self._handle_retry_error('unpin_all_messages', i, e)


    async def delete_message(self, message_id: Optional[int] = None) -> None:
        '''Delete a message in the chat. If message_id is None, delete the last message.'''
        mid = message_id if message_id is not None else self.message_id
        for i in range(self.retry_num):
            try:
                await self.application.bot.delete_message(chat_id=self.chat_id, message_id=mid)
                return
            except Exception as e:
                await self._handle_retry_error('delete_message', i, e)


    async def edit_message(self, message_id: Optional[int] = None, new_text: str = "") -> None:
        '''Edit a sent message. If message_id is None, edit the last message.'''
        mid = message_id if message_id is not None else self.message_id
        for i in range(self.retry_num):
            try:
                await self.application.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=mid,
                    text=new_text
                )
                return
            except Exception as e:
                await self._handle_retry_error('edit_message', i, e)


    async def get_last_message_id(self) -> Optional[int]:
        '''Get the last message id.'''
        return self.message_id


    async def get_update_json(self) -> dict:
        '''Get the update in JSON format.'''
        for i in range(self.retry_num):
            try:
                async with httpx.AsyncClient() as client:
                    url = f'https://api.telegram.org/bot{self.token}/getUpdates'
                    response = await client.get(url)
                    return response.json()
            except Exception as e:
                await self._handle_retry_error('get_update_json', i, e)


    async def _handle_retry_error(self, func_name: str, i: int, e: Exception):
        if self.debug:
            if i < self.retry_num - 1:
                print(f"{func_name} failed (attempt {i+1}/{self.retry_num}), retrying... Error: {e}")
                await asyncio.sleep(5)
            else:
                print(f"{func_name} failed after {self.retry_num} attempts. Error: {e}")
                raise
        elif i == self.retry_num - 1:
            raise