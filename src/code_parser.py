import cloudscraper
import os
import requests
import typing
from bs4 import BeautifulSoup


class ParseStatus(typing.TypedDict):
    found: bool
    title: str


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
        return cloudscraper.create_scraper(delay=5, browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    def get_url(self, code: str) -> str:
        return f'{self.video_url_prefix}/{code}'

    def get_title(self, code: str) -> ParseStatus:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent'  : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                            'Chrome/91.0.4472.124 Safari/537.36',
            'headerser'   : 'https://google.com'}
        content = self.scraper.get(f'{self.video_url_prefix}/{code}', proxies=self.proxy, headers=headers)
        try:
            content.raise_for_status()
        except requests.exceptions.HTTPError:
            return [False, None]

        soup = BeautifulSoup(content.text, 'html.parser')
        title_tag = soup.find('h1', class_='text-base lg:text-lg text-nord6')
        if title_tag:
            return [True, title_tag.text.replace(code, '').strip()]
        else:
            return [True, None]

    def download_cover(self, code: str, cover_save_path: str) -> bool:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent'  : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                            'Chrome/91.0.4472.124 Safari/537.36',
            'headerser'   : 'https://google.com'}
        counter = 0
        while True:
            match counter:
                case 0: # try to download high resolution cover
                    try:
                        movie_cover_link = f'{self.cover_url_prefix}/{code.lower()}/cover-n.jpg'
                        cover = self.scraper.get(movie_cover_link, proxies=self.proxy, headers=headers)
                        cover.raise_for_status()
                        with open(cover_save_path, 'wb') as f:
                            f.write(cover.content)
                        return True
                    except requests.exceptions.HTTPError:
                        pass
                case 1: # try to download low resolution cover
                    try:
                        movie_cover_link = f'{self.cover_url_prefix}/{code.lower()}/cover-t.jpg'
                        cover = self.scraper.get(movie_cover_link, proxies=self.proxy, headers=headers)
                        cover.raise_for_status()
                        with open(cover_save_path, 'wb') as f:
                            f.write(cover.content)
                        return True
                    except requests.exceptions.HTTPError:
                        pass
                case _: # all attempts failed
                    return False
            counter += 1
