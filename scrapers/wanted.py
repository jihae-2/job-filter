"""
Wanted 스크래퍼 — 공개 API 활용
- 목록 API: /api/v4/jobs  (query 파라미터로 키워드 검색)
- 상세 API: /api/v4/jobs/{id}  (detail, skill_tags 포함)
- 기업 규모: Wanted API 미제공 → requirements 텍스트 파싱으로 보완
"""
from __future__ import annotations
import time
from .base import BaseJobScraper, SEARCH_KEYWORDS

# 직무명에 이 키워드가 하나도 없으면 상세 API 호출 생략
TITLE_FILTER = ['디자이너', 'designer', 'design', '디자인']


class WantedScraper(BaseJobScraper):
    SITE_NAME = 'Wanted'
    API_BASE = 'https://www.wanted.co.kr/api/v4'
    JOB_BASE = 'https://www.wanted.co.kr/wd'

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Referer': 'https://www.wanted.co.kr/',
            'Origin': 'https://www.wanted.co.kr',
            'Accept': 'application/json, text/plain, */*',
        })

    # ------------------------------------------------------------------ #
    def fetch(self) -> list[dict]:
        seen_ids: set[int] = set()
        candidate_ids: list[int] = []

        # 4개 키워드로 목록 수집 → 직무명 기본 필터
        for kw in SEARCH_KEYWORDS:
            for job_id, position in self._fetch_list(kw):
                if job_id not in seen_ids:
                    title_lower = position.lower()
                    if any(f in title_lower for f in TITLE_FILTER):
                        seen_ids.add(job_id)
                        candidate_ids.append(job_id)
            time.sleep(0.4)

        # 후보 공고마다 상세 API 호출 (최대 70건)
        jobs = []
        for job_id in candidate_ids[:70]:
            job = self._fetch_detail(job_id)
            if job:
                jobs.append(job)
            time.sleep(0.2)

        return jobs

    def _fetch_list(self, query: str) -> list[tuple[int, str]]:
        """(job_id, position) 목록 반환."""
        results = []
        offset, limit, max_fetch = 0, 20, 70

        while offset < max_fetch:
            try:
                resp = self.session.get(
                    f'{self.API_BASE}/jobs',
                    params={
                        'job_sort': 'job.latest_order',
                        'years': -1,
                        'query': query,
                        'limit': limit,
                        'offset': offset,
                        'country': 'kr',
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                raise RuntimeError(f'Wanted 목록 API 실패 ({query}): {e}')

            items = data.get('data', [])
            if not items:
                break
            for item in items:
                results.append((item['id'], item.get('position', '')))
            if len(items) < limit:
                break
            offset += limit
            time.sleep(0.2)

        return results

    def _fetch_detail(self, job_id: int) -> dict | None:
        try:
            resp = self.session.get(
                f'{self.API_BASE}/jobs/{job_id}',
                timeout=10,
            )
            resp.raise_for_status()
            raw = resp.json().get('job', resp.json())
        except Exception as e:
            print(f'[Wanted] 상세 API 실패 (id={job_id}): {e}')
            return None

        try:
            company = raw.get('company', {}) or {}
            detail = raw.get('detail', {}) or {}
            skill_tags = raw.get('skill_tags', []) or []
            tags = ' '.join(t.get('title', '') for t in skill_tags)

            description = ' '.join(filter(None, [
                detail.get('intro', ''),
                detail.get('main_tasks', ''),
                tags,
            ]))
            requirements = detail.get('requirements', '')
            preferred = detail.get('preferred_points', '')

            # 경력: requirements 텍스트에서 파싱
            from filter import parse_experience_years
            exp_years = parse_experience_years(requirements + ' ' + description)
            exp_text = f'{exp_years}년 이상' if exp_years is not None else '정보 없음'

            return self.normalize({
                'title': raw.get('position', ''),
                'company': company.get('name', ''),
                'description': description,
                'requirements': requirements,
                'preferred': preferred,
                'experience': exp_text,
                'company_size': '',   # Wanted API 미제공
                'url': f'{self.JOB_BASE}/{job_id}',
                'posted_date': raw.get('due_time', ''),
                'tags': tags,
            })
        except Exception as e:
            print(f'[Wanted] 파싱 오류 (id={job_id}): {e}')
            return None
