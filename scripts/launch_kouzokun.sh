#!/usr/bin/env bash
# Linux / macOS launcher for 構造くん
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Python が見つかりません" >&2
  exit 1
fi

"$PY" -m pip install -r requirements.txt -q
(sleep 2; command -v xdg-open >/dev/null && xdg-open http://localhost:8501/ || open http://localhost:8501/ || true) &
exec "$PY" -m streamlit run tools/pdf_job/app.py --server.headless true --browser.gatherUsageStats false
