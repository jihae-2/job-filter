from __future__ import annotations
import re
from datetime import datetime, date as _date

# Must Have 항목 정의
MUST_HAVE = {
    'ux_ui': {
        'label': 'UX 설계 + UI 디자인',
        'keywords': [
            'ux', 'ui', 'ux/ui', 'ui/ux', 'ux 설계', 'ui 디자인', 'ux설계', 'ui디자인',
            '화면 설계', '화면설계', '와이어프레임', 'wireframe', '프로토타입', 'prototype',
            '사용자 경험', '인터랙션 디자인', 'interaction design', '정보구조', '정보 구조',
            'information architecture', '서비스 디자인', '프로덕트 디자인', 'product design',
            'ux design', 'ui design', 'gui', '플로우 설계', 'user flow', '스크린 디자인',
        ],
    },
    'pm_collab': {
        'label': 'PM·개발자 협업',
        'keywords': [
            'pm', 'po', '개발자 협업', '개발 협업', '개발팀 협업', '커뮤니케이션',
            '스프린트', 'sprint', '애자일', 'agile', '스크럼', 'scrum',
            '협업 경험', '개발팀과', '기획팀과', '기획자와', 'pm과', 'po와',
            'cross-functional', '크로스펑셔널', '이해관계자', 'stakeholder',
            '협업하여', '협업하며', '엔지니어와', '개발자와', '설계부터 개발까지',
        ],
    },
    'data_driven': {
        'label': '데이터 기반 문제 정의·지표 개선',
        'keywords': [
            '데이터 기반', '데이터기반', '데이터 분석', '데이터 드리븐', 'data-driven', 'data driven',
            'a/b 테스트', 'ab테스트', 'a/b테스트', '퍼널', 'funnel',
            '전환율', 'conversion', 'kpi', 'okr', '서비스 지표', '핵심 지표',
            'google analytics', 'ga4', 'amplitude', 'mixpanel', '앰플리튜드',
            '정량 분석', '로그 분석', '코호트', 'retention', '리텐션',
            'dau', 'mau', '실험 설계', '지표 개선', '지표를 기반',
        ],
    },
    'user_research': {
        'label': '사용자 리서치 (정성·정량)',
        'keywords': [
            '사용자 리서치', '사용자리서치', 'ux 리서치', 'ux리서치', 'ux research',
            '사용자 인터뷰', '사용자인터뷰', '사용자 조사', '심층 인터뷰',
            '정성 리서치', '정량 리서치', '정성적', '정량적',
            '사용성 테스트', '사용성테스트', 'usability test', 'usability testing',
            'fgi', '포커스 그룹', '컨텍스추얼', 'contextual inquiry',
            '다이어리 스터디', 'diary study', '에스노그라피', '사용자 조사',
        ],
    },
}

MIN_EXPERIENCE = 4    # 최소 경력 (년)
MIN_COMPANY_SIZE = 30  # 최소 기업 규모 (명)
MIN_MUST_HAVE = 3      # Must Have 최소 충족 개수


def parse_experience_years(text: str):
    """경력 요건 텍스트에서 최소 연수 파싱. 알 수 없으면 None 반환."""
    if not text:
        return None
    t = text.lower().replace(' ', '')

    if '신입' in t and '경력' not in t:
        return 0
    if '경력무관' in t or '무관' in t:
        return None

    # "n년이상" / "경력n년" / "n+년"
    for pat in [r'(\d+)년이상', r'경력(\d+)년', r'(\d+)\+년', r'최소(\d+)년']:
        m = re.search(pat, t)
        if m:
            return int(m.group(1))

    # "n~m년" 범위 → 최솟값
    m = re.search(r'(\d+)[~\-～](\d+)년', t)
    if m:
        return int(m.group(1))

    return None


def parse_company_size(text: str):
    """기업 규모 텍스트에서 인원 수 파싱. 알 수 없으면 None 반환."""
    if not text:
        return None
    t = text.replace(',', '').replace(' ', '')

    # "n~m명" 범위 → 최솟값
    m = re.search(r'(\d+)[~\-～](\d+)명', t)
    if m:
        return int(m.group(1))

    # "n명 이상" / "n명"
    m = re.search(r'(\d+)명', t)
    if m:
        return int(m.group(1))

    # 규모 레이블 → 대략 인원 추정
    labels = {
        '스타트업': 15, '소규모': 10, '중소기업': 80,
        '중견기업': 300, '대기업': 1000,
    }
    for label, size in labels.items():
        if label in text:
            return size

    return None


def _build_must_have(items: list | None) -> dict:
    """settings.json의 must_have 배열 → 키워드 dict 변환.
    items가 None이면 하드코딩 기본값(MUST_HAVE) 반환."""
    if items is None:
        return MUST_HAVE
    result = {}
    for item in items:
        key = item['key']
        if item.get('type') == 'size':
            continue  # 기업 규모는 별도 처리
        if key in MUST_HAVE:
            result[key] = MUST_HAVE[key]   # 기본 키워드 배열 유지
        else:
            label = item['label']
            result[key] = {'label': label, 'keywords': [label.lower()]}
    return result


def score_must_have(text: str, must_have_cfg: dict | None = None) -> tuple[dict, int]:
    """Must Have 항목 키워드 매칭 후 {key: label} dict와 점수 반환."""
    cfg = must_have_cfg if must_have_cfg is not None else MUST_HAVE
    if not text:
        return {}, 0
    t = text.lower()
    matched = {}
    for key, data in cfg.items():
        for kw in data['keywords']:
            if kw in t:
                matched[key] = data['label']
                break
    return matched, len(matched)


class JobFilter:
    def __init__(self, must_have_items: list | None = None):
        self._mh = _build_must_have(must_have_items)

    def filter_and_sort(self, jobs: list) -> list:
        filtered = []

        for job in jobs:
            combined = ' '.join(filter(None, [
                job.get('title', ''),
                job.get('description', ''),
                job.get('requirements', ''),
                job.get('preferred', ''),
                job.get('tags', ''),
            ]))

            # Must Have 점수
            matched, count = score_must_have(combined, self._mh)
            if count < MIN_MUST_HAVE:
                continue

            # 경력 필터
            exp_years = parse_experience_years(job.get('experience', ''))
            if exp_years is not None and exp_years < MIN_EXPERIENCE:
                continue

            # 기업 규모 필터
            size_num = parse_company_size(job.get('company_size', ''))
            if size_num is not None and size_num < MIN_COMPANY_SIZE:
                continue

            job = dict(job)
            job['must_have_matched'] = matched
            job['must_have_count'] = count
            job['exp_years_parsed'] = exp_years
            job['company_size_parsed'] = size_num
            filtered.append(job)

        # 정렬: 1순위 must_have_count↓, 2순위 마감일↑(없으면 맨뒤), 3순위 scraped_at↓
        def sort_key(j):
            count = j['must_have_count']
            date_str = j.get('posted_date', '')
            try:
                deadline_ts = datetime.fromisoformat(
                    date_str.replace('Z', '+00:00')
                ).timestamp()
                no_deadline = 0
            except Exception:
                deadline_ts = float('inf')
                no_deadline = 1
            scraped_str = j.get('scraped_at', '')
            try:
                scraped_ts = datetime.fromisoformat(scraped_str).timestamp()
            except Exception:
                scraped_ts = 0
            return (-count, no_deadline, deadline_ts, -scraped_ts)

        filtered.sort(key=sort_key)
        return filtered
