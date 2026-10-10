@echo off
rem SNS survey server - one-click launcher
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ was not found. Please install Python first.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" python -m venv .venv
call ".venv\Scripts\activate.bat"
if not exist ".venv\.installed" (
  pip install -r requirements.txt
  if errorlevel 1 ( pause & exit /b 1 )
  echo done> ".venv\.installed"
)

rem ---- admin password (edit here, or set ADMIN_PASSWORD beforehand) ----
if "%ADMIN_PASSWORD%"=="" set /p ADMIN_PASSWORD=Admin password: 
if "%ADMIN_PASSWORD%"=="" ( echo Password is required. & pause & exit /b 1 )

echo.
echo Survey:  http://localhost:8000/
echo Admin:   http://localhost:8000/admin   (user: any, password: the one above)
echo Stop with Ctrl+C or close this window.
echo.
waitress-serve --listen=127.0.0.1:8000 app:app
pause
