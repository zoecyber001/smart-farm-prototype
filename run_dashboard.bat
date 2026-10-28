@echo off
REM ==============================================================================
REM Smart Farm Dashboard Launcher (Windows)
REM Double-click this file to start the dashboard and open it in your browser.
REM ==============================================================================

echo ==========================================================
echo  Starting Smart Farm Operations Dashboard...
echo ==========================================================

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found on your system PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check the box "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Set up virtual environment if needed
if not exist ".venv" (
    echo [INFO] First-time setup: Creating Python environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --quiet --upgrade pip
    pip install --quiet -r farm_ai\requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

REM Open browser after 2 seconds in parallel
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

echo [INFO] Dashboard running at http://localhost:5000
echo [INFO] Press Ctrl+C anytime to stop.
echo ----------------------------------------------------------

python farm_ai\run_demo.py
pause
