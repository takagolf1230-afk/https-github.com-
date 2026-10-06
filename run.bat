@echo off
rem Radiology duty roster - one-click launcher
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ was not found. Please install Python first.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
  echo Creating virtual environment...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"

if not exist ".venv\.installed" (
  echo Installing libraries...
  if exist "wheelhouse" (
    pip install --no-index --find-links=wheelhouse -r requirements.txt
  ) else (
    pip install -r requirements.txt
  )
  if errorlevel 1 (
    echo Library installation failed. See README.md for offline setup.
    pause
    exit /b 1
  )
  echo done> ".venv\.installed"
)

rem skip the first-run e-mail prompt of Streamlit
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  mkdir "%USERPROFILE%\.streamlit" 2>nul
  (echo [general]& echo email = "") > "%USERPROFILE%\.streamlit\credentials.toml"
)

streamlit run app.py
pause
