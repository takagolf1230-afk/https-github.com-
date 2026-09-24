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
echo この黒い窓のメッセージを最後まで読んでください。
echo.

if not exist "%~dp0start_kouzokun.bat" (
  echo [エラー] 正しいフォルダではありません。
  echo 下のZIPをダウンロード→展開して、その中の
  echo 1_FIRST_SETUP.bat を実行してください。
  echo.
  echo https://github.com/takagolf1230-afk/https-github.com-/archive/refs/heads/cursor/coconala-listing-docs-33f2.zip
  echo.
  pause
  exit /b 1
)

echo [1/2] デスクトップにアイコンを作ります...
call "%~dp0create_desktop_shortcut.bat"
echo.
echo [2/2] このまま起動も試しますか？
echo.
choice /C YN /M "今すぐ起動する (Y) / あとでデスクトップから起動 (N)"
if errorlevel 2 goto end
if errorlevel 1 goto startnow

:startnow
call "%~dp0start_kouzokun.bat"
goto end

:end
echo.
echo セットアップ処理はここまでです。
echo デスクトップに「Kouzokun」があれば成功です。
pause
