import traceback
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date, datetime as _dt

from flask import Flask, render_template, jsonify, request

from scrapers import WantedScraper, JobkoreaScraper, RememberScraper
from filter import JobFilter
from database import init_db, upsert_jobs, get_jobs, get_bookmarks, toggle_bookmark, get_applications, toggle_application, update_application_status

app = Flask(__name__)
init_db()

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'settings.json')

DEFAULT_SETTINGS = {
    'roles': [
        {'id': 'ux',      'label': 'UX 디자이너'},
        {'id': 'product', 'label': '프로덕트 디자이너'},
        {'id': 'uiux',    'label': 'UI/UX 디자이너'},
    ],
    'must_have': [
        {'key': 'size',          'label': '기업 30명↑',          'type': 'size'},
        {'key': 'ux_ui',         'label': 'UX 설계 + UI 디자인'},
        {'key': 'pm_collab',     'label': 'PM·개발자 협업'},
        {'key': 'data_driven',   'label': '데이터 기반 문제 정의'},
        {'key': 'user_research', 'label': '사용자 리서치'},
    ],
}


def _exclude_expired(jobs: list) -> list:
    """posted_date가 오늘 이전인 공고를 API 응답 시점에 제외."""
    today = _date.today()
    result = []
    for job in jobs:
        pd = job.get('posted_date')
        if pd:
            try:
                if _dt.fromisoformat(str(pd).replace('Z', '+00:00')).date() < today:
                    continue
            except Exception:
                pass  # 파싱 불가 → 제외하지 않음
        result.append(job)
    return result


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SETTINGS

SCRAPERS = {
    'wanted':   WantedScraper,
    'jobkorea': JobkoreaScraper,
    'remember': RememberScraper,
}


# ── 라우트 ─────────────────────────────────────────────────────────── #
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/jobs', methods=['GET'])
def cached_jobs():
    """DB에 저장된 마지막 수집 결과 반환 (만료 공고 제외)."""
    jobs = _exclude_expired(get_jobs())
    return jsonify({'jobs': jobs, 'total': len(jobs)})


@app.route('/api/scrape', methods=['POST'])
def scrape():
    """선택한 사이트에서 공고 수집 → 필터링 → DB upsert → 반환."""
    body = request.get_json(silent=True) or {}
    selected = body.get('sites', list(SCRAPERS.keys()))

    all_jobs, errors = [], {}

    def _scrape_site(site):
        return site, SCRAPERS[site]().fetch()

    valid_sites = [s for s in selected if s in SCRAPERS]
    with ThreadPoolExecutor(max_workers=len(valid_sites)) as executor:
        futures = {executor.submit(_scrape_site, s): s for s in valid_sites}
        for future in as_completed(futures):
            site = futures[future]
            try:
                _, jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                errors[site] = str(e)
                traceback.print_exc()

    cfg = load_settings()
    filtered = JobFilter(cfg.get('must_have', [])).filter_and_sort(all_jobs)

    # DB upsert (URL 기준 중복 자동 처리)
    upsert_jobs(filtered)

    # 북마크 여부 포함한 최신 목록 반환 (만료 공고 제외)
    jobs_with_bm = _exclude_expired(get_jobs())

    return jsonify({
        'jobs': jobs_with_bm,
        'errors': errors,
        'total_collected': len(all_jobs),
        'total_filtered': len(filtered),
    })


@app.route('/api/parse-manual', methods=['POST'])
def parse_manual():
    """수동으로 붙여넣은 공고 텍스트를 파싱·필터링하여 반환."""
    import re
    body = request.get_json(silent=True) or {}
    text = (body.get('text') or '').strip()
    source = (body.get('source') or '수동 입력').strip()

    if not text:
        return jsonify({'jobs': [], 'total': 0})

    exp_m = re.search(r'경력[^\n]{0,20}', text)
    size_m = re.search(r'\d[\d,]*\s*명[^\n]{0,20}', text)

    job = {
        'title': source,
        'company': source,
        'description': text,
        'requirements': '',
        'preferred': '',
        'experience': exp_m.group(0) if exp_m else '',
        'company_size': size_m.group(0) if size_m else '',
        'url': '',
        'source': '수동 입력',
        'posted_date': '',
        'tags': '',
    }

    cfg = load_settings()
    filtered = JobFilter(cfg.get('must_have', [])).filter_and_sort([job])

    # 수동 입력은 url이 없어서 북마크 여부는 항상 False
    bookmarked_urls = {b['url'] for b in get_bookmarks()}
    for j in filtered:
        j['is_bookmarked'] = j.get('url', '') in bookmarked_urls

    return jsonify({'jobs': filtered, 'total': len(filtered)})


# ── 설정 API ───────────────────────────────────────────────────────── #
@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(load_settings())


@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': '데이터 없음'}), 400
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True})


# ── 북마크 API ─────────────────────────────────────────────────────── #
@app.route('/api/bookmarks', methods=['GET'])
def list_bookmarks():
    return jsonify(get_bookmarks())


@app.route('/api/bookmarks', methods=['POST'])
def toggle_bookmark_route():
    """북마크 토글 (URL 기준). 반환: {action, total}"""
    body = request.get_json(silent=True) or {}
    url = (body.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'url 필요'}), 400

    action = toggle_bookmark(url)
    total = len(get_bookmarks())
    return jsonify({'action': action, 'total': total})


# ── 지원현황 API ───────────────────────────────────────────────────── #
@app.route('/api/applications', methods=['GET'])
def list_applications():
    return jsonify(get_applications())


@app.route('/api/applications', methods=['POST'])
def toggle_application_route():
    """지원 추가/취소 토글 (URL 기준). 반환: {action, total}"""
    body = request.get_json(silent=True) or {}
    url = (body.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'url 필요'}), 400
    action = toggle_application(url)
    total = len(get_applications())
    return jsonify({'action': action, 'total': total})


@app.route('/api/applications/status', methods=['POST'])
def update_status_route():
    """지원 상태 변경 (지원/서류합격/면접/최종합격/불합격)."""
    VALID = {'지원', '서류합격', '면접', '최종합격', '불합격'}
    body = request.get_json(silent=True) or {}
    url = (body.get('url') or '').strip()
    status = (body.get('status') or '').strip()
    if not url or status not in VALID:
        return jsonify({'error': '잘못된 요청'}), 400
    update_application_status(url, status)
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    print(f'서버 시작: http://localhost:{port}')
    app.run(debug=True, port=port, host='0.0.0.0')
