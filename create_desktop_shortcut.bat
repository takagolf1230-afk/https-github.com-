@echo off
REM Create desktop shortcuts (ASCII filename - use this)
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   デスクトップにショートカットを作ります
echo ========================================
echo.

if not exist "%~dp0start_kouzokun.bat" (
  echo [エラー] start_kouzokun.bat が同じフォルダにありません。
  echo 正しいZIPを展開したフォルダで実行してください。
  echo https://github.com/takagolf1230-afk/https-github.com-/archive/refs/heads/cursor/coconala-listing-docs-33f2.zip
  pause
  exit /b 1
)

set "TARGET=%~dp0start_kouzokun.bat"
set "WORKDIR=%~dp0"

set "DESKTOP="
if exist "%USERPROFILE%\Desktop" set "DESKTOP=%USERPROFILE%\Desktop"
if not defined DESKTOP if exist "%USERPROFILE%\OneDrive\Desktop" set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
if not defined DESKTOP if exist "%USERPROFILE%\OneDrive\デスクトップ" set "DESKTOP=%USERPROFILE%\OneDrive\デスクトップ"
if not defined DESKTOP if exist "%USERPROFILE%\デスクトップ" set "DESKTOP=%USERPROFILE%\デスクトップ"

if not defined DESKTOP (
  echo [エラー] デスクトップフォルダが見つかりません。
  echo 手動で start_kouzokun.bat をダブルクリックして起動できます。
  pause
  exit /b 1
)

echo Desktop: %DESKTOP%
echo Target : %TARGET%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$desktop='%DESKTOP%';" ^
  "$target='%TARGET%';" ^
  "$workdir='%WORKDIR%';" ^
  "$s=New-Object -ComObject WScript.Shell;" ^
  "foreach($name in @('構造くん.lnk','Kouzokun.lnk')){" ^
  "  $path=Join-Path $desktop $name;" ^
  "  $sc=$s.CreateShortcut($path);" ^
  "  $sc.TargetPath=$target;" ^
  "  $sc.WorkingDirectory=$workdir;" ^
  "  $sc.WindowStyle=1;" ^
  "  $sc.Description='Kouzokun PDF to Excel';" ^
  "  $sc.IconLocation='shell32.dll,168';" ^
  "  $sc.Save();" ^
  "  Write-Output ('created: ' + $path)" ^
  "}"

set "OK=0"
if exist "%DESKTOP%\Kouzokun.lnk" set "OK=1"
if exist "%DESKTOP%\構造くん.lnk" set "OK=1"

echo.
if "%OK%"=="1" (
  echo [成功] デスクトップにショートカットを作りました。
  echo   - Kouzokun
  echo   - 構造くん （表示される場合）
  echo.
  echo 次にデスクトップの「Kouzokun」をダブルクリックしてください。
  echo 初回は黒窓で部品インストールのあと、ブラウザが開きます。
) else (
  echo [エラー] ショートカット作成に失敗しました。
  echo 代わりに、このフォルダの start_kouzokun.bat を直接ダブルクリックしてください。
)

echo.
pause
