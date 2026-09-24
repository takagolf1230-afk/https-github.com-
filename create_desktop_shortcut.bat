@echo off
REM Put a launcher on Desktop that calls this folder's start_kouzokun.bat
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   デスクトップへ起動ファイルを置きます
echo ========================================
echo.

if not exist "%~dp0start_kouzokun.bat" (
  echo [エラー] start_kouzokun.bat がありません。
  echo 完全版ZIPの kouzokun フォルダで実行してください。
  echo https://github.com/takagolf1230-afk/https-github.com-/raw/cursor/coconala-listing-docs-33f2/dist/kouzokun_windows.zip
  pause
  exit /b 1
)

if not exist "%~dp0tools\pdf_job\app.py" (
  echo [エラー] tools フォルダがありません。不完全なコピーです。
  echo 完全版ZIPを入れ直してください。
  pause
  exit /b 1
)

set "TARGET=%~dp0start_kouzokun.bat"
set "WORKDIR=%~dp0"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%I"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" if exist "%USERPROFILE%\OneDrive\Desktop" set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
if not exist "%DESKTOP%" if exist "%USERPROFILE%\OneDrive\デスクトップ" set "DESKTOP=%USERPROFILE%\OneDrive\デスクトップ"
if not exist "%DESKTOP%" if exist "%USERPROFILE%\デスクトップ" set "DESKTOP=%USERPROFILE%\デスクトップ"

echo Desktop : %DESKTOP%
echo App folder: %WORKDIR%
echo.

if not exist "%DESKTOP%" (
  echo [エラー] デスクトップ場所が分かりません。
  echo 代わりに start_kouzokun.bat を直接ダブルクリックしてください。
  explorer "%~dp0"
  pause
  exit /b 1
)

REM Create a tiny launcher on Desktop with absolute path to this install
(
  echo @echo off
  echo rem Auto-generated launcher for Kouzokun
  echo call "%TARGET%"
) > "%DESKTOP%\Kouzokun.bat"

if exist "%DESKTOP%\Kouzokun.bat" (
  echo [成功] デスクトップに Kouzokun.bat を作りました。
) else (
  echo [失敗] Kouzokun.bat をデスクトップに書けませんでした。
)

REM Optional .lnk shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Continue';" ^
  "$desktop='%DESKTOP%';" ^
  "$target='%TARGET%';" ^
  "$workdir='%WORKDIR%';" ^
  "$s=New-Object -ComObject WScript.Shell;" ^
  "foreach($name in @('Kouzokun.lnk','構造くん.lnk')){" ^
  "  try {" ^
  "    $path=Join-Path $desktop $name;" ^
  "    $sc=$s.CreateShortcut($path);" ^
  "    $sc.TargetPath=$target;" ^
  "    $sc.WorkingDirectory=$workdir;" ^
  "    $sc.WindowStyle=1;" ^
  "    $sc.Description='Kouzokun PDF to Excel';" ^
  "    $sc.IconLocation='shell32.dll,168';" ^
  "    $sc.Save();" ^
  "    Write-Output ('shortcut ok: ' + $name)" ^
  "  } catch { Write-Output ('shortcut skip: ' + $name) }" ^
  "}"

(
  echo 構造くんの起動
  echo.
  echo デスクトップの「Kouzokun.bat」をダブルクリックしてください。
  echo.
  echo もしデスクトップに無い場合:
  echo 1. エクスプローラーを開く
  echo 2. 次のフォルダを開く
  echo %WORKDIR%
  echo 3. start_kouzokun.bat をダブルクリック
  echo.
  echo デスクトップ判定パス: %DESKTOP%
) > "%DESKTOP%\Kouzokunの使い方.txt" 2>nul

echo.
echo ----------------------------------------
if exist "%DESKTOP%\Kouzokun.bat" (
  echo 今からデスクトップフォルダを開きます。
  echo ファイル名: Kouzokun.bat
  echo これをダブルクリック = 構造くん起動
  echo.
  explorer "%DESKTOP%"
) else (
  echo デスクトップに書けなかったので、本体フォルダを開きます。
  echo start_kouzokun.bat をダブルクリックしてください。
  explorer "%~dp0"
)

echo.
pause
