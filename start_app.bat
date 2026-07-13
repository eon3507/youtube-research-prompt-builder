@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: creating the app environment...
    py -3.11 -m venv .venv
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -c "import streamlit, googleapiclient, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Installing or repairing the app packages...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo A .env file was created. Add your YouTube API key to it, then run this file again.
    notepad ".env"
    pause
    exit /b 0
)

start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
exit /b %errorlevel%

:error
echo.
echo Setup failed. Check the message above and try again.
pause
exit /b 1
