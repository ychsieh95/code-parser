import hashlib
import hmac
import os
import re
import time
import uuid
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

        self._recombee_base  = 'https://client-rapi-missav.recombee.com'
        self._recombee_db    = 'missav-default'
        self._recombee_token = 'Ikkg568nlM51RHvldlPvc2GzZPE9R4XGzaH9Qj4zK9npbbbTly1gj9K4mgRn0QlV'

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

    def _recombee_sign(self, path: str) -> str:
        n   = f'/{self._recombee_db}{path}?frontend_timestamp={int(time.time())}'
        sig = hmac.new(self._recombee_token.encode(), n.encode(), hashlib.sha1).hexdigest()
        return f'{self._recombee_base}{n}&frontend_sign={sig}'

    _FILTER_EXPRS: dict[str, str] = {
        'jav':              '\'type\' == "jav"',
        'uncensored':       '\'type\' == "uncensored"',
        'uncensored-leak':  '\'type\' == "uncensored-leak"',
        'individual':       '\'type\' == "individual"',
        'chinese-subtitle': "'has_chinese_subtitle' == true",
    }

    def search(self, keywords: str, filter: str | None = None, count: int = 10) -> tuple[bool, list[str]]:
        user_id = str(uuid.uuid4())
        url     = self._recombee_sign(f'/search/users/{user_id}/items/')
        body: dict = {
            'searchQuery':      keywords,
            'count':            count,
            'scenario':         'search',
            'cascadeCreate':    True,
            'returnProperties': False,
        }
        if filter:
            body['filter'] = self._FILTER_EXPRS.get(filter, filter)
        try:
            r = self.scraper.post(url, json=body, proxies=self.proxy, timeout=10)
            r.raise_for_status()
        except Exception:
            return False, []
        data = r.json()
        return True, [item['id'].upper() for item in data.get('recomms', [])]

    def get_latest(self, count: int = 10) -> tuple[bool, list[str]]:
        codes = []
        seen  = set()
        page  = 1
        while len(codes) < count:
            try:
                r = self.scraper.get(f'{self.video_url_prefix}/new?page={page}', proxies=self.proxy, timeout=10)
                r.raise_for_status()
            except Exception:
                return False, []
            soup       = BeautifulSoup(r.text, 'html.parser')
            page_codes = []
            for a in soup.find_all('a', href=True):
                seg = a['href'].rstrip('/').split('/')[-1]
                m   = re.match(r'^((?:fc2-ppv-|[a-zA-Z]{2,5}-)\d+)', seg, re.IGNORECASE)
                if m:
                    code = m.group(1).upper()
                    if code not in seen:
                        seen.add(code)
                        page_codes.append(code)
            if not page_codes:
                break
            codes.extend(page_codes)
            page += 1
        return True, codes[:count]

    def get_suggestion(self, code: str, count: int = 10) -> tuple[bool, list[str]]:
        user_id = str(uuid.uuid4())
        url     = self._recombee_sign(f'/recomms/items/{code.lower()}/items/')
        body    = {
            'targetUserId':     user_id,
            'count':            count,
            'scenario':         'desktop-watch-next-side',
            'cascadeCreate':    True,
            'returnProperties': False,
        }
        try:
            r = self.scraper.post(url, json=body, proxies=self.proxy, timeout=10)
            r.raise_for_status()
        except Exception:
            return False, []
        data = r.json()
        return True, [item['id'].upper() for item in data.get('recomms', [])]
