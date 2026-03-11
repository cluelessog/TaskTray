@echo off
echo.
echo  ◆ TASKTRAY — Setup
echo  ─────────────────────
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Create virtual environment
echo [1/3] Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

:: Install dependencies
echo [2/3] Installing dependencies...
pip install -r requirements.txt --quiet

:: Create data directory
echo [3/3] Setting up data directory...
if not exist "data" mkdir data

echo.
echo  ✓ Setup complete!
echo.
echo  NEXT STEPS:
echo  1. Edit config.yaml — set your project directories and Obsidian vault path
echo  2. Run: start.bat (or: python server.py)
echo  3. Native window opens with your dashboard
echo  4. System tray icon appears — click to show/hide, right-click to quit
echo.
pause
