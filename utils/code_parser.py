import os
import re
from curl_cffi import requests
from bs4 import BeautifulSoup


class CodeParser:
    def __init__(self):
        if os.environ.get('http_proxy') is not None and os.environ.get('https_proxy') is not None:
            self.proxy = {'http': os.environ.get('http_proxy'), 'https': os.environ.get('https_proxy')}
        else:
            self.proxy = None
        self.scraper = self.get_scraper()

        self.video_url_prefix = 'https://missav.ws'
        self.cover_url_prefix = 'https://fourhoi.com'

    @staticmethod
    def get_scraper():
        return requests.Session(impersonate='chrome')

    def get_video_url(self, code: str) -> str:
        return f'{self.video_url_prefix}/{code}'

    def get_cover_url(self, code: str) -> str:
        return f'{self.cover_url_prefix}/{code}/cover-n.jpg'

    def get_title(self, code: str) -> tuple[bool, str | None]:
        try:
            content = self.scraper.get(f'{self.video_url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return False, None

        soup      = BeautifulSoup(content.text, 'html.parser')
        title_tag = soup.find('h1', class_='text-base lg:text-lg text-nord6')
        if title_tag:
            return True, title_tag.text.replace(code, '').strip()
        return True, None

    def download_cover(self, code: str, cover_save_path: str) -> bool:
        for suffix in ('cover-n.jpg', 'cover-t.jpg'):
            try:
                url   = f'{self.cover_url_prefix}/{code.lower()}/{suffix}'
                cover = self.scraper.get(url, proxies=self.proxy, timeout=10)
                cover.raise_for_status()
                with open(cover_save_path, 'wb') as f:
                    f.write(cover.content)
                return True
            except Exception:
                continue
        return False

    def fix_code(self, code: str) -> str:
        code = code.strip().upper()
        if m := re.match(r'^([a-zA-Z]{2,5})[-]?(\d{3,5})$', code):
            return f'{m.group(1)}-{m.group(2)}'
        if m := re.match(r'^(FC2)[-]?(PPV)?[-]?(\d+)$', code):
            return f'FC2-PPV-{m.group(3)}'
        return code

    def fix_codes(self, codes: list[str]) -> list[str]:
        return [self.fix_code(c) for c in codes]
