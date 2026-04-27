#!/bin/bash
cd "$(dirname "$0")"

# 가상환경 없으면 생성
if [ ! -d "venv" ]; then
  echo "가상환경 생성 중..."
  python3 -m venv venv
  venv/bin/pip install -q -r requirements.txt
fi

# 5000번 포트 사용 중이면 5001로 fallback (macOS AirPlay 충돌 대응)
PORT=5000
if lsof -ti:5000 > /dev/null 2>&1; then
  PORT=5001
fi

echo "서버 시작: http://localhost:$PORT"
open "http://localhost:$PORT" 2>/dev/null || true
FLASK_RUN_PORT=$PORT venv/bin/python3 app.py
