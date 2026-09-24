@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "TARGET=%~dp0構造くんを起動.bat"
set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
if not exist "%DESKTOP%" (
  echo [エラー] デスクトップフォルダが見つかりません。
  pause
  exit /b 1
)

set "LNK=%DESKTOP%\構造くん.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = New-Object -ComObject WScript.Shell;" ^
  "$sc = $s.CreateShortcut('%LNK%');" ^
  "$sc.TargetPath = '%TARGET%';" ^
  "$sc.WorkingDirectory = '%~dp0';" ^
  "$sc.WindowStyle = 1;" ^
  "$sc.Description = '構造くん - PDF表をExcelに整える';" ^
  "$sc.IconLocation = 'shell32.dll,168';" ^
  "$sc.Save()"

if exist "%LNK%" (
  echo.
  echo デスクトップに「構造くん」ショートカットを作りました。
  echo 場所: %LNK%
  echo.
  echo あとはデスクトップのアイコンをダブルクリックするだけです。
) else (
  echo [エラー] ショートカットを作れませんでした。
)

echo.
pause
