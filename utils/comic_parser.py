import hashlib
import os
import re
from curl_cffi import requests
from enum import IntEnum
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image


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
    """18comic.vip (禁漫天堂). Page images are scrambled into shuffled horizontal strips
    as anti-scraping; _descramble() reassembles them using the site's own algorithm
    (segment count derived from a hash of the album id + page filename)."""

    # Below this album id, images aren't scrambled at all; below this, scrambling
    # always uses 10 segments. These thresholds and the segment-count formula mirror
    # the site's own (reverse-engineered) scrambling scheme.
    _SCRAMBLE_268850 = 268850
    _SCRAMBLE_421926 = 421926

    _RE_SCRAMBLE_ID = re.compile(r'var scramble_id = (\d+);')
    _RE_TITLE       = re.compile(r'<h1[^>]*class="pull-left"[^>]*>([\s\S]*?)<')
    _RE_FIRST_IMAGE = re.compile(r'data-original="(.*?)"[^>]*?id="album_photo[^>]*?data-page="0"')

    def __init__(self):
        super().__init__()
        self.url_prefix = 'https://18comic.vip/photo'

    def get_comic_url(self, code: str) -> str:
        return f'{self.url_prefix}/{code}'

    def get_title(self, code: str) -> tuple[bool, str | None]:
        try:
            content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return False, None
        return True, self._parse_title(content.text)

    def download_cover(self, code: str, cover_save_path: str) -> bool:
        try:
            content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return False
        return self._download_first_image(code, content.text, cover_save_path)

    def fetch_and_save(self, code: str, cover_save_path: str) -> tuple[bool, str | None, bool]:
        """Fetch title and cover in a single page request."""
        try:
            content = self.scraper.get(f'{self.url_prefix}/{code}', proxies=self.proxy, timeout=10)
            content.raise_for_status()
        except Exception:
            return False, None, False

        title       = self._parse_title(content.text)
        cover_saved = self._download_first_image(code, content.text, cover_save_path)
        return True, title, cover_saved

    @classmethod
    def _parse_title(cls, html: str) -> str | None:
        m = cls._RE_TITLE.search(html)
        return m.group(1).strip().rstrip('|').strip() if m else None

    def _download_first_image(self, code: str, html: str, cover_save_path: str) -> bool:
        img_match = self._RE_FIRST_IMAGE.search(html)
        if not img_match:
            return False
        image_url = img_match.group(1)

        scramble_match = self._RE_SCRAMBLE_ID.search(html)
        scramble_id     = scramble_match.group(1) if scramble_match else '0'
        filename        = os.path.splitext(os.path.basename(image_url))[0]

        try:
            image_resp = self.scraper.get(
                image_url, proxies=self.proxy, timeout=10,
                headers={'Referer': f'{self.url_prefix}/{code}'},
            )
            image_resp.raise_for_status()
            image = Image.open(BytesIO(image_resp.content)).convert('RGB')
        except Exception:
            return False

        num = self._segment_count(scramble_id, code, filename)
        self._descramble(num, image).save(cover_save_path)
        return True

    @classmethod
    def _segment_count(cls, scramble_id: str, aid: str, filename: str) -> int:
        scramble_id = int(scramble_id)
        aid         = int(aid)
        if aid < scramble_id:
            return 0
        if aid < cls._SCRAMBLE_268850:
            return 10
        divisor = 10 if aid < cls._SCRAMBLE_421926 else 8
        digest  = hashlib.md5(f'{aid}{filename}'.encode()).hexdigest()
        return (ord(digest[-1]) % divisor) * 2 + 2

    @staticmethod
    def _descramble(num: int, image: Image.Image) -> Image.Image:
        if num == 0:
            return image
        w, h   = image.size
        result = Image.new('RGB', (w, h))
        block  = h // num
        over   = h % num
        for i in range(num):
            move  = block + over if i == 0 else block
            y_src = h - (block * (i + 1)) - over
            y_dst = 0 if i == 0 else block * i + over
            result.paste(image.crop((0, y_src, w, y_src + move)), (0, y_dst, w, y_dst + move))
        return result
