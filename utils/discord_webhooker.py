from discord_webhook import DiscordWebhook
from typing import List, Optional
from pathlib import Path
from requests.exceptions import Timeout


class DiscordWebhooker:
    def __init__(self, url: str, retry_num: int = 3) -> None:
        self.url               = url
        self.retry_num         = retry_num
        self.debug             = False
        self.raise_after_retry = True
        self.webhooks          = {}

    async def send_message(self, text: str, image_paths: Optional[List[str]] = None) -> bool:
        webhook = DiscordWebhook(url=self.url, content=text)
        if image_paths:
            for image_path in image_paths:
                path = Path(image_path)
                try:
                    with path.open('rb') as f:
                        webhook.add_file(file=f.read(), filename=path.name)
                except Exception as file_err:
                    if self.debug:
                        print(f"Failed to attach image '{image_path}': {file_err}")
                    continue

        for attempt in range(1, self.retry_num + 1):
            try:
                response = webhook.execute()
                if response.status_code == 200:
                    self.webhooks[self.__new_webhook_id()] = webhook
                    return True
                elif self.debug:
                    print(f"Attempt {attempt}: Failed to send message, status code: {response.status_code}.")
            except Timeout as err:
                if self.debug:
                    print(f"Attempt {attempt}: Timeout occurred: {err}")
                if attempt == self.retry_num and self.raise_after_retry:
                    raise err
                if attempt == self.retry_num:
                    return False
            except Exception as err:
                if self.debug:
                    print(f"Attempt {attempt}: Unexpected error: {err}")
                if attempt == self.retry_num and self.raise_after_retry:
                    raise err
                if attempt == self.retry_num:
                    return False
        return False

    async def edit_message(self, text: str, webhook_id: Optional[int] = None) -> bool:
        if not self.webhooks:
            if self.debug:
                print("No webhook initialized. Cannot edit message.")
            return False

        if webhook_id is None:
            webhook_id = self.__get_last_webhook_id()
        webhook = self.webhooks.get(webhook_id)
        if webhook is None:
            if self.debug:
                print(f"Webhook id {webhook_id} not found. Cannot edit message.")
            return False

        webhook.content = text
        for attempt in range(1, self.retry_num + 1):
            try:
                response = webhook.execute()
                if response.status_code == 200:
                    return True
                elif self.debug:
                    print(f"Attempt {attempt}: Failed to edit message, status code: {response.status_code}.")
            except Timeout as err:
                if self.debug:
                    print(f"Attempt {attempt}: Timeout occurred: {err}")
                if attempt == self.retry_num and self.raise_after_retry:
                    raise err
                if attempt == self.retry_num:
                    return False
            except Exception as err:
                if self.debug:
                    print(f"Attempt {attempt}: Unexpected error: {err}")
                if attempt == self.retry_num and self.raise_after_retry:
                    raise err
                if attempt == self.retry_num:
                    return False

    async def delete_message(self, webhook_id: Optional[int] = None) -> bool:
        if not self.webhooks:
            if self.debug:
                print("No webhook initialized. Cannot delete message.")
            return False

        if webhook_id is None:
            webhook_id = self.__get_last_webhook_id()
        webhook = self.webhooks.get(webhook_id)
        if webhook is None:
            if self.debug:
                print(f"Webhook id {webhook_id} not found. Cannot delete message.")
            return False

        for attempt in range(1, self.retry_num + 1):
            try:
                response = webhook.delete()
                if response.status_code == 200:
                    del self.webhooks[webhook_id]
                    return True
                elif self.debug:
                    print(f"Attempt {attempt}: Failed to delete message, status code: {response.status_code}.")
            except Timeout as err:
                if self.debug:
                    print(f"Attempt {attempt}: Timeout occurred: {err}")
                if attempt == self.retry_num and self.raise_after_retry:
                    raise err
                if attempt == self.retry_num:
                    return False
            except Exception as err:
                if self.debug:
                    print(f"Attempt {attempt}: Unexpected error: {err}")
                if attempt == self.retry_num and self.raise_after_retry:
                    raise err
                if attempt == self.retry_num:
                    return False

    def __get_last_webhook_id(self) -> int:
        return max(self.webhooks.keys(), default=-1)

    def __new_webhook_id(self) -> int:
        if not self.webhooks:
            return 0
        else:
            return max(self.webhooks.keys(), default=0) + 1
