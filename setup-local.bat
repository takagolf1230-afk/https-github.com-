@echo off
setlocal EnableExtensions
cd /d "%~dp0"

for /f "delims=" %%D in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"') do set "DESKTOP=%%D"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"

set "DEV=%DESKTOP%\keiba-next"
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

if /I "%SRC%"=="%DEV%" goto :setup

echo デスクトップに開発フォルダを作ります:
echo %DEV%
if not exist "%DEV%" mkdir "%DEV%"
if not exist "%DEV%" goto :fail
robocopy "%SRC%" "%DEV%" /E /XD .git .venv venv __pycache__ out /XF *.db /NFL /NDL /NJH /NJS /nc /ns /np
if errorlevel 8 goto :fail
cd /d "%DEV%"
call "%DEV%\setup-local.bat"
exit /b %errorlevel%

:setup
echo 開発フォルダ: %DEV%
cd /d "%DEV%\next"

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
echo 開発フォルダはここです:
echo %DEV%
echo サンプルは動きました。jv_data.db はこのフォルダに置かないでください。
echo python -m keiba_next inspect --db "C:\path\to\jv_data.db"
echo python -m keiba_next train --db "C:\path\to\jv_data.db" --until 20260101 --model out/ranker.txt
echo.
echo 開発チャットには docs\dev-assistant-brief.md を貼ってください。印は出させません。
pause
exit /b 0

:fail
echo 開発フォルダの作成か起動確認に失敗しました。この画面の文を開発チャットに貼ってください。
pause
exit /b 1
