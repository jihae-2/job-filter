from __future__ import annotations
import requests
from abc import ABC, abstractmethod

# 모든 스크래퍼가 공유하는 검색 키워드
SEARCH_KEYWORDS = [
    'UX 디자이너',
    'UI/UX 디자이너',
    '프로덕트 디자이너',
    'Product Designer',
]


class BaseJobScraper(ABC):
    SITE_NAME = ""

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    @abstractmethod
    def fetch(self) -> list[dict]:
        pass

    def normalize(self, raw: dict) -> dict:
        return {
            'title': raw.get('title', ''),
            'company': raw.get('company', ''),
            'description': raw.get('description', ''),
            'requirements': raw.get('requirements', ''),
            'preferred': raw.get('preferred', ''),
            'experience': raw.get('experience', ''),
            'company_size': raw.get('company_size', ''),
            'url': raw.get('url', ''),
            'source': self.SITE_NAME,
            'posted_date': raw.get('posted_date', ''),
            'tags': raw.get('tags', ''),
        }
