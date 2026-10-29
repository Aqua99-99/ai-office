#!/usr/bin/env bash
# 트레이딩 사무실 실행 환경 준비. 성공하면 마지막 줄에 쓸 파이썬 경로를 출력한다.
#   PY=$(bash setup.sh | tail -n 1)
# 이미 준비돼 있으면 몇 초 안에 끝난다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"   # 플러그인(저장소) 맨 위
REQ="$ROOT/requirements.txt"
VENV="${TRADING_OFFICE_VENV:-$HOME/.trading-office-venv}"

ok() { "$1" -c "import sys, tradingagents, markdown_it, yfinance; assert sys.version_info >= (3, 11)" >/dev/null 2>&1; }

# 1) 이미 쓸 수 있는 파이썬 (GitHub Actions 등에서 미리 설치한 경우)
for cand in "${TRADING_OFFICE_PYTHON:-}" python3 python; do
  [ -n "$cand" ] && command -v "$cand" >/dev/null 2>&1 && ok "$cand" && { command -v "$cand"; exit 0; }
done
# 2) 전에 만들어 둔 가상환경
[ -x "$VENV/bin/python" ] && ok "$VENV/bin/python" && { echo "$VENV/bin/python"; exit 0; }

# 3) 새로 만들기 (TradingAgents는 Python 3.11 이상이 필요)
echo "실행 환경을 처음 준비해요 (1~3분)..." >&2
if command -v uv >/dev/null 2>&1; then
  uv venv -q --python 3.12 "$VENV" >&2
  VIRTUAL_ENV="$VENV" uv pip install -q -r "$REQ" >&2
else
  PYBIN=""
  for v in python3.13 python3.12 python3.11 python3; do
    if command -v "$v" >/dev/null 2>&1 && "$v" -c "import sys; assert sys.version_info >= (3, 11)" 2>/dev/null; then PYBIN="$v"; break; fi
  done
  if [ -z "$PYBIN" ]; then
    echo "Python 3.11 이상이 없어요. 'pip install uv' 후 다시 시도하거나 Python 3.12를 설치하세요." >&2
    exit 1
  fi
  "$PYBIN" -m venv "$VENV" >&2
  "$VENV/bin/python" -m pip install -q --upgrade pip >&2
  "$VENV/bin/python" -m pip install -q -r "$REQ" >&2
fi
ok "$VENV/bin/python" || { echo "설치가 끝났지만 불러오기에 실패했어요." >&2; exit 1; }
echo "$VENV/bin/python"
