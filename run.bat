@echo off
setlocal

echo Starting Film Studio desktop application...
python app.py %*
if errorlevel 1 (
    echo.
    echo Film Studio exited with error. Press any key to close.
    pause >nul
)
