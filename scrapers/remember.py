"""
Remember 채용 스크래퍼 — career-api.rememberapp.co.kr POST API 활용
키워드 + 디자인/UX 직무 카테고리 + 경력 4년+ 필터 적용하여 수집
"""
from __future__ import annotations
import random
import time
from .base import BaseJobScraper, SEARCH_KEYWORDS

API_URL = 'https://career-api.rememberapp.co.kr/job_postings/search'

JOB_CATEGORIES = [
    {'level1': '디자인/UX', 'level2': 'IT프로덕트/UX디자인'},
    {'level1': '디자인/UX', 'level2': 'UI/GUI 디자인'},
    {'level1': '디자인/UX', 'level2': 'UX리서치'},
    {'level1': '디자인/UX', 'level2': 'UX라이터'},
    {'level1': '디자인/UX', 'level2': '디자인/UX 기타'},
]


class RememberScraper(BaseJobScraper):
    SITE_NAME = 'Remember'
    BASE_URL = 'https://career.rememberapp.co.kr'

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': 'https://career.rememberapp.co.kr/',
            'Origin': 'https://career.rememberapp.co.kr',
        })

    def fetch(self) -> list[dict]:
        seen_ids: set[int] = set()
        jobs: list[dict] = []

        for keyword in SEARCH_KEYWORDS:
            if len(jobs) >= 70:
                break
            for job in self._fetch_keyword(keyword):
                if job.get('_id') not in seen_ids:
                    seen_ids.add(job['_id'])
                    del job['_id']
                    jobs.append(job)
                    if len(jobs) >= 70:
                        break
            time.sleep(0.4)

        return jobs

    def _fetch_keyword(self, keyword: str) -> list[dict]:
        jobs = []
        seed = random.randint(1_000_000, 9_999_999)

        for page in range(1, 3):   # 최대 2페이지 (페이지당 30건)
            body = {
                'search': {
                    'organization_type': 'all',
                    'application_type': 'all',
                    'keywords': [keyword],
                    'job_category_names': JOB_CATEGORIES,
                    'min_experience': 4,
                    'max_experience': 15,
                    'include_applied_job_posting': False,
                },
                'sort': 'starts_at_desc',
                'ai_new_model': False,
                'page': page,
                'per': 30,
                'new_function_score': True,
                'seed': seed,
            }
            try:
                resp = self.session.post(API_URL, json=body, timeout=12)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                raise RuntimeError(f'Remember API 실패 ({keyword}, page={page}): {e}')

            raw_jobs = data.get('data', [])
            if not raw_jobs:
                break

            for raw in raw_jobs:
                company = raw.get('company') or {}
                emp = company.get('employee_count') or company.get('size') or ''
                min_exp = raw.get('min_experience')
                max_exp = raw.get('max_experience')
                if min_exp is not None and max_exp is not None:
                    exp_text = f'{min_exp}~{max_exp}년'
                elif min_exp is not None:
                    exp_text = f'{min_exp}년 이상'
                else:
                    exp_text = str(raw.get('career_description', ''))

                description = ' '.join(filter(None, [
                    raw.get('introduction', ''),
                    raw.get('job_description', ''),
                    raw.get('qualifications', ''),
                    raw.get('preferred_qualifications', ''),
                ]))

                job = self.normalize({
                    'title': raw.get('title', ''),
                    'company': company.get('name', '') or raw.get('company_name', ''),
                    'description': description,
                    'requirements': raw.get('qualifications', ''),
                    'preferred': raw.get('preferred_qualifications', ''),
                    'experience': exp_text,
                    'company_size': str(emp) if emp else '',
                    'url': f'{self.BASE_URL}/job/posting/{raw.get("id", "")}',
                    'posted_date': (raw.get('starts_at') or '')[:10],
                    'tags': '',
                })
                job['_id'] = raw.get('id', 0)
                jobs.append(job)

            if len(raw_jobs) < 30:
                break
            time.sleep(0.3)

        return jobs
