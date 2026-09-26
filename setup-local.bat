@echo off
setlocal
cd /d "%~dp0next"

set "PY=python"
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"

if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Python 3.10 以上が見つかりません。
    echo https://www.python.org/ から入れ、インストール時に PATH を有効にしてください。
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo パッケージのインストールに失敗しました。
  pause
  exit /b 1
)

if not exist out mkdir out
python -m keiba_next fixture --out out/fixture.db
if errorlevel 1 goto :fail
python -m keiba_next ping --db out/fixture.db
if errorlevel 1 goto :fail
python -m unittest discover -s tests -v
if errorlevel 1 goto :fail

echo.
echo サンプルは動きました。次は本番DBです。jv_data.db はこのフォルダに置かないでください。
echo python -m keiba_next inspect --db "C:\path\to\jv_data.db"
echo python -m keiba_next train --db "C:\path\to\jv_data.db" --until 20260101 --model out/ranker.txt
echo.
echo 開発チャットには docs\dev-assistant-brief.md を貼ってください。印は出させません。
pause
exit /b 0

:fail
echo 起動確認に失敗しました。この画面の文を開発チャットに貼ってください。
pause
exit /b 1
