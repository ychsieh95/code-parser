import os
import re
from curl_cffi import requests
from enum import IntEnum
from bs4 import BeautifulSoup


class ComicType(IntEnum):
    UNKNOWN = 0
    NHENTAI = 1
    WNACG   = 2
    JM      = 3


class ComicParser:
    def __init__(self):
        if os.environ.get('http_proxy') is not None and os.environ.get('https_proxy') is not None:
            self.proxy = {'http': os.environ.get('http_proxy'), 'https': os.environ.get('https_proxy')}
        else:
            self.proxy = None
        self.scraper = self.get_scraper()

    @staticmethod
    def get_scraper():
        return requests.Session(impersonate='chrome')

    def get_comic_type(self, code: str) -> ComicType:
        if re.match(r'^[nN]?[\d]+$', code):
            return ComicType.NHENTAI
        if re.match(r'^[wW][\d]+$', code):
            return ComicType.WNACG
        if re.match(r'^[jJ][mM]?[\d]+$', code):
            return ComicType.JM
        return ComicType.UNKNOWN


class NhentaiComicParser(ComicParser):
    def __init__(self):
        super().__init__()
        self.url_prefix = 'https://nhentai.net/g'

    def get_comic_url(self, code: str) -> str:
        return f'{self.url_prefix}/{code}'

    def get_cover_url(self, code: str) -> str | None:
        try:
            content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return None

        soup      = BeautifulSoup(content.text, 'html.parser')
        cover_div = soup.find('div', id='cover')
        if cover_div and (img := cover_div.find('img')):
            return img.get('src')
        return None

    def get_title(self, code: str) -> tuple[bool, str | None]:
        try:
            content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return False, None

        soup      = BeautifulSoup(content.text, 'html.parser')
        title_tag = soup.find('title')
        return (True, title_tag.text.strip()) if title_tag else (True, None)

    def download_cover(self, code: str, cover_save_path: str) -> bool:
        cover_url = self.get_cover_url(code)
        if not cover_url:
            return False
        try:
            cover = self.scraper.get(cover_url, proxies=self.proxy, timeout=10)
            cover.raise_for_status()
            with open(cover_save_path, 'wb') as f:
                f.write(cover.content)
            return True
        except Exception:
            return False

    def fetch_and_save(self, code: str, cover_save_path: str) -> tuple[bool, str | None, bool]:
        """Fetch title and cover in a single page request."""
        try:
            content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return False, None, False

        soup = BeautifulSoup(content.text, 'html.parser')

        title_tag = soup.find('title')
        title     = title_tag.text.strip() if title_tag else None

        cover_saved = False
        cover_div   = soup.find('div', id='cover')
        if cover_div and (img := cover_div.find('img')):
            cover_url = img.get('src')
            if cover_url:
                try:
                    cover = self.scraper.get(cover_url, proxies=self.proxy, timeout=10)
                    cover.raise_for_status()
                    with open(cover_save_path, 'wb') as f:
                        f.write(cover.content)
                    cover_saved = True
                except Exception:
                    pass

        return True, title, cover_saved


class WnacgComicParser(ComicParser):
    def get_comic_url(self, code: str) -> str:
        raise NotImplementedError
    def get_title(self, code: str) -> tuple[bool, str | None]:
        raise NotImplementedError
    def download_cover(self, code: str, cover_save_path: str) -> bool:
        raise NotImplementedError
    def fetch_and_save(self, code: str, cover_save_path: str) -> tuple[bool, str | None, bool]:
        raise NotImplementedError


class JmComicParser(ComicParser):
    def get_comic_url(self, code: str) -> str:
        raise NotImplementedError
    def get_title(self, code: str) -> tuple[bool, str | None]:
        raise NotImplementedError
    def download_cover(self, code: str, cover_save_path: str) -> bool:
        raise NotImplementedError
    def fetch_and_save(self, code: str, cover_save_path: str) -> tuple[bool, str | None, bool]:
        raise NotImplementedError
