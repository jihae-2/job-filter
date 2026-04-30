# Job Filter — 채용공고 필터링 웹앱

UX/프로덕트 디자이너 채용공고를 자동 수집하고, Must Have 조건으로 필터링해 보여주는 로컬 웹앱입니다.
<img width="1726" height="1203" alt="image" src="https://github.com/user-attachments/assets/74a97468-bc9d-4c8a-831c-902a64cf2315" />

## 주요 기능

- **자동 수집**: 원티드, 잡코리아, 리멤버 채용공고 스크래핑
- **스마트 필터링**: Must Have 항목(UX 설계, PM 협업, 데이터 기반, 사용자 리서치) 키워드 매칭
- **마감일 관리**: 마감 지난 공고 자동 제외, 임박순 정렬
- **북마크**: 관심 공고 저장
- **지원현황 추적**: 지원 → 서류합격 → 면접 → 최종합격/불합격 상태 관리

## 설치

Python 3.9+ 필요

```bash
git clone https://github.com/jihae-2/job-filter.git
cd job-filter
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 실행

```bash
source venv/bin/activate
FLASK_RUN_PORT=5002 python app.py
```

브라우저에서 `http://localhost:5002` 접속

## 필터 설정

`settings.json`에서 Must Have 조건 및 검색 직무를 수정할 수 있습니다.  
(파일이 없으면 기본값으로 자동 생성됩니다)

## 기술 스택

- **Backend**: Flask, SQLite, BeautifulSoup4
- **Frontend**: Vanilla JS, CSS (빌드 도구 없음)
