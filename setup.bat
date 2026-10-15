@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          Film Studio - Environment Setup
echo =======================================================
echo.

:: 1. Verify Python Installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ is not found on your PATH.
    echo Please install Python from https://www.python.org/ or Microsoft Store.
    pause
    exit /b 1
)

echo [1/3] Checking Python version...
python --version

:: 2. Install Dependencies
echo.
echo [2/3] Installing Python dependencies from requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

:: 3. Ensure Offline Vendor Assets for xterm.js
echo.
echo [3/3] Checking offline vendor assets (xterm.js)...
python -c "import os, urllib.request; os.makedirs('static/vendor', exist_ok=True); assets = {'xterm.js': 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js', 'xterm.css': 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css', 'xterm-addon-fit.js': 'https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js'}; [urllib.request.urlretrieve(url, os.path.join('static/vendor', fname)) for fname, url in assets.items() if not os.path.exists(os.path.join('static/vendor', fname))]; print('Vendor assets verified!')"

echo.
echo =======================================================
echo          Setup completed successfully!
echo   Run the desktop application anytime using: run.bat
echo =======================================================
echo.
pause
