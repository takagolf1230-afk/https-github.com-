@echo off
REM One file to run first on Windows
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

title FIRST SETUP - Kouzokun
echo ========================================
echo   構造くん はじめてセットアップ
echo ========================================
echo.

if not exist "%~dp0start_kouzokun.bat" (
  echo [エラー] 正しいフォルダではありません。
  echo 完全版ZIPを展開した kouzokun フォルダで実行してください。
  echo https://github.com/takagolf1230-afk/https-github.com-/raw/cursor/coconala-listing-docs-33f2/dist/kouzokun_windows.zip
  pause
  exit /b 1
)

if not exist "%~dp0tools\pdf_job\app.py" (
  echo [エラー] tools フォルダがありません。
  echo 完全版ZIPを入れ直してください。
  pause
  exit /b 1
)

echo [1/2] デスクトップに Kouzokun.bat を置きます...
call "%~dp0create_desktop_shortcut.bat"

echo.
echo ----------------------------------------
echo デスクトップに「Kouzokun.bat」があれば成功です。
echo それをダブルクリックすると起動します。
echo.
echo もしデスクトップに無ければ、このフォルダの
echo start_kouzokun.bat をダブルクリックしてください。
echo.
choice /C YN /M "今すぐ起動する (Y) / 後で起動する (N)"
if errorlevel 2 goto end
if errorlevel 1 call "%~dp0start_kouzokun.bat"

:end
echo.
pause
