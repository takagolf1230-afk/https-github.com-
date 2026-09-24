@echo off
REM 構造くん launcher (ASCII filename - use this)
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

title Kouzokun / 構造くん
echo ========================================
echo   構造くん を起動しています...
echo ========================================
echo   folder: %CD%
echo.

if not exist "tools\pdf_job\app.py" (
  echo [エラー] ソフト本体が見つかりません。
  echo いま開いているフォルダが違います。
  echo.
  echo 正しいZIPをダウンロードして展開してください:
  echo https://github.com/takagolf1230-afk/https-github.com-/archive/refs/heads/cursor/coconala-listing-docs-33f2.zip
  echo.
  echo 展開後、この start_kouzokun.bat があるフォルダで実行してください。
  echo.
  pause
  exit /b 1
)

if not exist "requirements.txt" (
  echo [エラー] requirements.txt がありません。ZIPが不完全です。
  pause
  exit /b 1
)

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY where python3 >nul 2>&1 && set "PY=python3"

if not defined PY (
  echo [エラー] Python が見つかりません。
  echo.
  echo 1. https://www.python.org/downloads/ を開く
  echo 2. Python 3 をインストール
  echo 3. インストール画面で必ずチェック:
  echo    Add python.exe to PATH
  echo 4. PCを再起動して、もう一度このファイルを実行
  echo.
  pause
  exit /b 1
)

echo Python: %PY%
echo 必要な部品を入れています（初回は数分かかることがあります）...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [エラー] pip install に失敗しました。
  echo ネット接続を確認して、もう一度実行してください。
  pause
  exit /b 1
)

echo.
echo ブラウザで http://localhost:8501 を開きます。
echo 止め方: この黒い窓で Ctrl+C、または窓を閉じる
echo.

start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8501/"

%PY% -m streamlit run tools/pdf_job/app.py --server.headless true --browser.gatherUsageStats false
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo [エラー] 起動に失敗しました。コード=%ERR%
  echo 上の赤い/英語のエラー文をメモして教えてください。
)
echo 構造くん を終了しました。
pause
exit /b %ERR%
