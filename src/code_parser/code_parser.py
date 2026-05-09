import os
import re
import typing
from curl_cffi import requests
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
        return requests.Session(impersonate='chrome')

    def get_url(self, code: str) -> str:
        return f'{self.video_url_prefix}/{code}'

    def get_title(self, code: str) -> ParseStatus:
        content = self.scraper.get(f'{self.video_url_prefix}/{code}', proxies=self.proxy)
        try:
            content.raise_for_status()
        except requests.HTTPError:
            return [False, None]

        soup = BeautifulSoup(content.text, 'html.parser')
        title_tag = soup.find('h1', class_='text-base lg:text-lg text-nord6')
        if title_tag:
            return [True, title_tag.text.replace(code, '').strip()]
        else:
            return [True, None]

    def download_cover(self, code: str, cover_save_path: str) -> bool:
        counter = 0
        while True:
            match counter:
                case 0: # try to download high resolution cover
                    try:
                        movie_cover_link = f'{self.cover_url_prefix}/{code.lower()}/cover-n.jpg'
                        cover = self.scraper.get(movie_cover_link, proxies=self.proxy)
                        cover.raise_for_status()
                        with open(cover_save_path, 'wb') as f:
                            f.write(cover.content)
                        return True
                    except requests.HTTPError:
                        pass
                case 1: # try to download low resolution cover
                    try:
                        movie_cover_link = f'{self.cover_url_prefix}/{code.lower()}/cover-t.jpg'
                        cover = self.scraper.get(movie_cover_link, proxies=self.proxy)
                        cover.raise_for_status()
                        with open(cover_save_path, 'wb') as f:
                            f.write(cover.content)
                        return True
                    except requests.HTTPError:
                        pass
                case _: # all attempts failed
                    return False
            counter += 1

    def fix_code(self, code: str) -> str:
        code = code.strip().upper()
        if matches:=re.match(r'^([a-zA-Z]{2,5})[-]?(\d{3,5})$', code):
            return f'{matches.group(1)}-{matches.group(2)}'
        elif matches:=re.match(r'^(FC2)[-]?(PPV)?[-]?(\d+)$', code):
            return f'FC2-PPV-{matches.group(3)}'
        else:
            return code

    def fix_codes(self, codes: list[str]) -> list[str]:
        fixed_codes = []
        for code in codes:
            fixed_codes.append(self.fix_code(code))
        return fixed_codes