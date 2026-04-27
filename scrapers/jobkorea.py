"""
잡코리아 스크래퍼 — HTML 파싱 + S3 JD 수집
흐름:
  1. 검색 결과 페이지에서 카드 파싱 (제목·회사·경력·URL)
  2. 제목 필터로 디자인 직무만 추려 상세 페이지 요청
  3. 상세 페이지 script 태그에서 S3 서명 URL 추출
  4. S3 OCR/DESCRIPTION HTML 다운로드 → JD 텍스트 확보
  5. JD 텍스트로 Must Have 필터링
"""
from __future__ import annotations
import re
import time
import urllib.parse
from bs4 import BeautifulSoup
from .base import BaseJobScraper, SEARCH_KEYWORDS

# 공고 카드에서 버튼/메뉴 링크 텍스트는 회사명에서 제외
SKIP_TEXTS = {'스크랩', '지원', '즉시지원', '즉시 지원', '관심', '공유', '신고', '로그인'}

# 제목에 이 키워드가 하나도 없으면 상세 JD 수집 생략
TITLE_FILTER = ['디자이너', 'designer', '디자인', 'design', 'ux', 'ui', 'ux/ui', '프로덕트']

# S3 URL 패턴 (OCR 우선, DESCRIPTION 대체)
S3_SUFFIXES = ['_OCR.html', '_DESCRIPTION.html']
S3_PAT = r'https://job-hub-files-prd[^\"\\\\ ]+{suffix}\?[^\"\\\\ ]+'


class JobkoreaScraper(BaseJobScraper):
    SITE_NAME = 'Jobkorea'
    BASE_URL = 'https://www.jobkorea.co.kr'
    # Pf=Y: 경력 조건 ON / Py_From=4: 경력 4년 이상
    SEARCH_BASE = (
        'https://www.jobkorea.co.kr/Search/'
        '?tabType=recruit&Pf=Y&Py_From=4'
    )

    def fetch(self) -> list[dict]:
        seen_urls: set[str] = set()
        jobs: list[dict] = []

        for keyword in SEARCH_KEYWORDS:
            if len(jobs) >= 70:
                break
            for job in self._fetch_keyword(keyword):
                if job['url'] not in seen_urls:
                    seen_urls.add(job['url'])
                    jobs.append(job)
                    if len(jobs) >= 70:
                        break
            time.sleep(0.5)

        return jobs

    # ── 키워드별 검색 ────────────────────────────────────────────── #
    def _fetch_keyword(self, keyword: str) -> list[dict]:
        jobs = []
        encoded = urllib.parse.quote(keyword)
        base = self.SEARCH_BASE + f'&stext={encoded}'

        for page in range(1, 3):   # 최대 2페이지
            url = base + f'&Page_No={page}'
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                raise RuntimeError(f'Jobkorea 요청 실패 ({keyword}, page={page}): {e}')

            soup = BeautifulSoup(resp.text, 'lxml')
            candidates = self._parse_page(soup)
            if not candidates:
                break

            # 제목 필터 + JD 수집
            for cand in candidates:
                title_lower = cand['title'].lower()
                if not any(f in title_lower for f in TITLE_FILTER):
                    continue
                jd = self._fetch_jd(cand['url'])
                if jd:
                    cand['description'] = cand['description'] + ' ' + jd
                jobs.append(cand)
                time.sleep(0.2)

            time.sleep(0.7)

        return jobs

    # ── 검색 결과 페이지 파싱 ────────────────────────────────────── #
    def _parse_page(self, soup: BeautifulSoup) -> list[dict]:
        jobs = []
        seen_hrefs: set[str] = set()

        for a in soup.select('a[href*="Recruit/GI_Read"]'):
            href_clean = a.get('href', '').split('?')[0]
            title = a.get_text(strip=True)
            if href_clean in seen_hrefs or not title or len(title) < 5:
                continue
            seen_hrefs.add(href_clean)

            full_url = (
                href_clean if href_clean.startswith('http')
                else self.BASE_URL + href_clean
            )

            card = self._find_card(a)
            if not card:
                continue
            card_text = card.get_text(' ', strip=True)

            jobs.append(self.normalize({
                'title': title,
                'company': self._extract_company(card, title),
                'description': card_text,
                'experience': self._extract_experience(card_text),
                'company_size': self._extract_size(card_text),
                'url': full_url,
                'posted_date': self._extract_date(card_text),
            }))

        return jobs

    # ── S3 JD 수집 ───────────────────────────────────────────────── #
    def _fetch_jd(self, job_url: str) -> str:
        """상세 페이지 → S3 서명 URL → JD 텍스트 반환. 실패 시 빈 문자열."""
        try:
            resp = self.session.get(job_url, timeout=12)
            # \u0026 을 & 로 교체해야 S3 URL 전체가 한 토큰으로 잡힘
            page_text = resp.text.replace(r'\u0026', '&')

            for suffix in S3_SUFFIXES:
                pat = S3_PAT.format(suffix=re.escape(suffix))
                m = re.search(pat, page_text)
                if not m:
                    continue
                r2 = self.session.get(m.group(0), timeout=12)
                if not r2.ok:
                    continue
                content = BeautifulSoup(r2.content, 'html.parser').get_text(' ', strip=True)
                if len(content) > 50:
                    return content
        except Exception as e:
            print(f'[Jobkorea] JD 수집 실패 ({job_url}): {e}')
        return ''

    # ── 헬퍼 ─────────────────────────────────────────────────────── #
    def _find_card(self, anchor) -> object | None:
        node = anchor
        for _ in range(8):
            if not node.parent:
                break
            node = node.parent
            if len(node.get_text(' ', strip=True)) > 80:
                return node
        return None

    def _extract_company(self, card, job_title: str) -> str:
        for lnk in card.find_all('a'):
            text = lnk.get_text(strip=True)
            if text and text != job_title and text not in SKIP_TEXTS and 2 < len(text) < 40:
                return text
        return ''

    def _extract_experience(self, text: str) -> str:
        m = re.search(r'경력\s*(\d+년)[↑이상]*', text)
        if m:
            return f'경력 {m.group(1)} 이상'
        if re.search(r'경력\s*무관', text):
            return '경력무관'
        if '신입' in text:
            return '신입'
        return ''

    def _extract_date(self, text: str) -> str:
        """등록일 추출 → YYYY-MM-DD 형식 반환 (연도는 현재 연도 기준)."""
        m = re.search(r'(\d{2}/\d{2})\([월화수목금토일]\)\s*등록', text)
        if not m:
            return ''
        from datetime import date
        today = date.today()
        try:
            mo, dy = map(int, m.group(1).split('/'))
            return date(today.year, mo, dy).isoformat()
        except ValueError:
            return ''

    def _extract_size(self, text: str) -> str:
        m = re.search(r'(\d[\d,]+)\s*명', text)
        return m.group(0) if m else ''
