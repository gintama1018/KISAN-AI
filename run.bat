@echo off
:: ═══════════════════════════════════════════════════════════════
:: KISAN AI — Windows Startup Script
:: Starts Pathway stream engine + Flask web server
:: ═══════════════════════════════════════════════════════════════

echo.
echo  ██╗  ██╗██╗███████╗ █████╗ ███╗   ██╗    █████╗ ██╗
echo  ██║ ██╔╝██║██╔════╝██╔══██╗████╗  ██║   ██╔══██╗██║
echo  █████╔╝ ██║███████╗███████║██╔██╗ ██║   ███████║██║
echo  ██╔═██╗ ██║╚════██║██╔══██║██║╚██╗██║   ██╔══██║██║
echo  ██║  ██╗██║███████║██║  ██║██║ ╚████║   ██║  ██║██║
echo  ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚═╝  ╚═╝╚═╝
echo.
echo  Real-Time AI Platform for Indian Village Farmers
echo  Powered by ISRO + NASA Satellite Data + Pathway
echo  ═══════════════════════════════════════════════════
echo.

:: Detect Python — prefer .venv if available
set PYTHON=python
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    echo  Using virtual environment: .venv
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
    echo  Using virtual environment: venv
)

%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Run setup.ps1 first.
    pause
    exit /b 1
)

:: Check .env file
if not exist ".env" (
    echo INFO: .env not found. Copying from .env.example...
    copy .env.example .env
    echo INFO: Edit .env to add your API keys ^(optional for demo^)
    echo.
)

:: Set ALERTS_FILE for Windows (local temp folder)
set ALERTS_FILE=%TEMP%\kisan_alerts.jsonl

:: Try Pathway stream engine (optional — app works without it)
where pathway >nul 2>&1
if not errorlevel 1 (
    echo [1/2] Starting Pathway stream engine...
    echo       Polls ISRO + NASA APIs every hour
    echo       Output: %ALERTS_FILE%
    echo.
    start "Kisan AI - Pathway Stream" /min %PYTHON% pipeline\stream.py
    timeout /t 3 /nobreak >nul
) else (
    echo [1/2] Pathway not installed - running Flask in direct API mode ^(still uses real satellite data^)
    echo.
)

:: Start Flask web server
echo [2/2] Starting Flask web server...
echo.
echo  ═══════════════════════════════════════════════════
echo   Dashboard: http://localhost:5000
echo  ═══════════════════════════════════════════════════
echo.
%PYTHON% app.py

pause
