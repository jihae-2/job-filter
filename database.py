"""
SQLite 기반 jobs / bookmarks 영속 저장소
- jobs: url UNIQUE — 동일 URL은 upsert (최신 데이터로 갱신)
- bookmarks: url UNIQUE — toggle (추가/제거)
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / 'jobs.db'


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                url              TEXT PRIMARY KEY,
                title            TEXT,
                company          TEXT,
                source           TEXT,
                description      TEXT,
                requirements     TEXT,
                preferred        TEXT,
                experience       TEXT,
                company_size     TEXT,
                posted_date      TEXT,
                tags             TEXT,
                must_have_count  INTEGER DEFAULT 0,
                must_have_matched TEXT DEFAULT '{}',
                scraped_at       TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bookmarks (
                url           TEXT PRIMARY KEY,
                bookmarked_at TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                url        TEXT PRIMARY KEY,
                applied_at TEXT,
                status     TEXT DEFAULT '지원'
            )
        ''')
        # 기존 테이블에 status 컬럼 없으면 추가 (마이그레이션)
        try:
            conn.execute("ALTER TABLE applications ADD COLUMN status TEXT DEFAULT '지원'")
        except Exception:
            pass  # 이미 존재

        # Jobkorea MM/DD 날짜 → YYYY-MM-DD 변환 (일회성 마이그레이션)
        # scraped_at 연도를 기준으로 변환
        mm_dd_rows = conn.execute(
            "SELECT url, posted_date, scraped_at FROM jobs "
            "WHERE source='Jobkorea' AND length(posted_date)=5 AND posted_date LIKE '__/__'"
        ).fetchall()
        for url, pd, scraped_at in mm_dd_rows:
            year = (scraped_at or '')[:4] or str(datetime.now().year)
            try:
                mo, dy = pd.split('/')
                new_date = f'{year}-{mo}-{dy}'
                conn.execute("UPDATE jobs SET posted_date=? WHERE url=?", (new_date, url))
            except Exception:
                conn.execute("UPDATE jobs SET posted_date='' WHERE url=?", (url,))

        conn.commit()


def upsert_jobs(jobs: list[dict]) -> None:
    """필터링된 공고 목록을 DB에 upsert (URL 기준 중복 제거)."""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        for job in jobs:
            conn.execute('''
                INSERT INTO jobs (url, title, company, source, description, requirements,
                    preferred, experience, company_size, posted_date, tags,
                    must_have_count, must_have_matched, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title             = excluded.title,
                    company           = excluded.company,
                    source            = excluded.source,
                    description       = excluded.description,
                    requirements      = excluded.requirements,
                    preferred         = excluded.preferred,
                    experience        = excluded.experience,
                    company_size      = excluded.company_size,
                    posted_date       = excluded.posted_date,
                    tags              = excluded.tags,
                    must_have_count   = excluded.must_have_count,
                    must_have_matched = excluded.must_have_matched,
                    scraped_at        = excluded.scraped_at
            ''', (
                job.get('url', ''),
                job.get('title', ''),
                job.get('company', ''),
                job.get('source', ''),
                job.get('description', ''),
                job.get('requirements', ''),
                job.get('preferred', ''),
                job.get('experience', ''),
                job.get('company_size', ''),
                job.get('posted_date', ''),
                job.get('tags', ''),
                job.get('must_have_count', 0),
                json.dumps(job.get('must_have_matched', {}), ensure_ascii=False),
                now,
            ))
        conn.commit()


def get_jobs() -> list[dict]:
    """저장된 전체 공고 목록 반환 (북마크 여부 포함)."""
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT j.*, (b.url IS NOT NULL) AS is_bookmarked
            FROM jobs j
            LEFT JOIN bookmarks b ON j.url = b.url
            ORDER BY j.must_have_count DESC,
                     CASE WHEN j.posted_date = '' OR j.posted_date IS NULL THEN 1 ELSE 0 END ASC,
                     j.posted_date ASC,
                     j.scraped_at DESC
        ''').fetchall()
    return [_row_to_dict(row) for row in rows]


def get_bookmarks() -> list[dict]:
    """북마크된 공고 목록 반환 (최신 북마크 순)."""
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT j.*, 1 AS is_bookmarked, b.bookmarked_at
            FROM bookmarks b
            JOIN jobs j ON b.url = j.url
            ORDER BY b.bookmarked_at DESC
        ''').fetchall()
    return [_row_to_dict(row) for row in rows]


def toggle_bookmark(url: str) -> str:
    """북마크 추가/제거 토글. 반환값: 'added' | 'removed'."""
    with get_conn() as conn:
        existing = conn.execute(
            'SELECT url FROM bookmarks WHERE url = ?', (url,)
        ).fetchone()
        if existing:
            conn.execute('DELETE FROM bookmarks WHERE url = ?', (url,))
            action = 'removed'
        else:
            conn.execute(
                'INSERT INTO bookmarks (url, bookmarked_at) VALUES (?, ?)',
                (url, datetime.now().isoformat()),
            )
            action = 'added'
        conn.commit()
    return action


def get_applications() -> list[dict]:
    """지원한 공고 목록 반환 (최신 지원순)."""
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT j.*, 1 AS is_bookmarked, a.applied_at, a.status
            FROM applications a
            JOIN jobs j ON a.url = j.url
            ORDER BY a.applied_at DESC
        ''').fetchall()
    return [_row_to_dict(row) for row in rows]


def toggle_application(url: str) -> str:
    """지원 추가/취소 토글. 반환값: 'added' | 'removed'."""
    with get_conn() as conn:
        existing = conn.execute(
            'SELECT url FROM applications WHERE url = ?', (url,)
        ).fetchone()
        if existing:
            conn.execute('DELETE FROM applications WHERE url = ?', (url,))
            action = 'removed'
        else:
            conn.execute(
                "INSERT INTO applications (url, applied_at, status) VALUES (?, ?, '지원')",
                (url, datetime.now().isoformat()),
            )
            action = 'added'
        conn.commit()
    return action


def update_application_status(url: str, status: str) -> None:
    """지원 상태 업데이트."""
    with get_conn() as conn:
        conn.execute(
            'UPDATE applications SET status = ? WHERE url = ?', (status, url)
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d['must_have_matched'] = json.loads(d.get('must_have_matched') or '{}')
    except Exception:
        d['must_have_matched'] = {}
    d['is_bookmarked'] = bool(d.get('is_bookmarked'))
    return d
