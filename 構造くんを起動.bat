@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

title 構造くん
echo ========================================
echo   構造くん を起動しています...
echo ========================================
echo.

REM Prefer Windows py launcher, then python, then python3
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY where python3 >nul 2>&1 && set "PY=python3"

if not defined PY (
  echo [エラー] Python が見つかりません。
  echo https://www.python.org/downloads/ から Python 3 を入れてください。
  echo インストール時に「Add python.exe to PATH」にチェックを入れてください。
  echo.
  pause
  exit /b 1
)

echo 必要な部品を確認しています...
%PY% -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo [エラー] 依存関係のインストールに失敗しました。
  pause
  exit /b 1
)

echo.
echo ブラウザで http://localhost:8501 を開きます。
echo 止めたいときは、この黒い窓で Ctrl+C を押してください。
echo.

REM Open browser a moment after server starts
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8501/"

%PY% -m streamlit run tools/pdf_job/app.py --server.headless true --browser.gatherUsageStats false

echo.
echo 構造くん を終了しました。
pause
