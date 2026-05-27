import os
import re
import typing
from curl_cffi import requests
from enum import IntEnum
from bs4 import BeautifulSoup


class ParseStatus(typing.TypedDict):
    found: bool
    title: str


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

        self.url_prefix = 'https://nhentai.net/g'

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

    def get_cover_url(self, code: str) -> bool:
        content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy)
        try:
            content.raise_for_status()
        except requests.exceptions.HTTPError:
            return False

        soup = BeautifulSoup(content.text, 'html.parser')
        cover_div = soup.find('div', id='cover')
        if cover_div:
            img = cover_div.find('img')
            if img:
                return img.get('src')
        return False

    def get_title(self, code: str) -> ParseStatus:
        content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy)
        try:
            content.raise_for_status()
        except requests.exceptions.HTTPError:
            return [False, None]

        soup = BeautifulSoup(content.text, 'html.parser')
        title_tag = soup.find('title')
        if title_tag:
            return [True, title_tag.text.strip()]
        else:
            return [True, None]

    def download_cover(self, code: str, cover_save_path: str) -> bool:
        cover_url = self.get_cover_url(code)
        if not cover_url:
            return False

        try:
            cover = self.scraper.get(cover_url, proxies=self.proxy)
            cover.raise_for_status()
            with open(cover_save_path, 'wb') as f:
                f.write(cover.content)
            return True
        except requests.exceptions.HTTPError:
            return False


class WnacgComicParser(ComicParser):
    pass


class JmComicParser(ComicParser):
    pass
