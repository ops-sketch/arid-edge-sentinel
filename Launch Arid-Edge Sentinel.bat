@echo off
REM ============================================================
REM  Arid-Edge Sentinel  -  one-click launcher (Windows)
REM  Double-click this file to boot the demo app.
REM
REM  First run: creates a local .venv, installs requirements,
REM             then launches Streamlit (which auto-opens your
REM             default browser at http://localhost:8501).
REM  Later runs: skips setup and goes straight to launch.
REM
REM  Strategy: install the small "demo" requirement set with
REM  HARD error checking (Streamlit + Plotly + numpy + pandas).
REM  Then best-effort install the geospatial "live API" extras
REM  (rasterio, h5py, etc.) -- which often fail to build on
REM  bare Windows. The app degrades gracefully without them.
REM ============================================================

setlocal enableextensions
cd /d "%~dp0"
title Arid-Edge Sentinel

REM --- Find a Python interpreter -----------------------------
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if "%PYEXE%"=="" (
    where python >nul 2>nul && set "PYEXE=python"
)
if "%PYEXE%"=="" (
    echo.
    echo [ERROR] Python is not installed or not on PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during install.
    echo.
    pause
    exit /b 1
)

REM --- Create venv if missing --------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [setup] First-time setup -- creating virtual environment...
    %PYEXE% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "VENVPY=.venv\Scripts\python.exe"

REM --- Always make sure the demo deps are present ------------
REM (Cheap if already installed -- pip is a no-op then.)
echo [setup] Ensuring core demo dependencies are installed...
"%VENVPY%" -m pip install --upgrade pip --quiet
"%VENVPY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install core requirements ^(streamlit etc.^).
    echo         Check your network connection and try again.
    echo.
    pause
    exit /b 1
)

REM --- Best-effort: install live-API extras ------------------
REM These can fail to wheel-build on Windows; the app handles
REM their absence cleanly (synthetic-data fallback in the UI).
if not exist ".venv\.live-api-installed" (
    echo [setup] Attempting optional live-API extras ^(can be skipped^)...
    "%VENVPY%" -m pip install -r requirements-live.txt
    if errorlevel 1 (
        echo [warn] Live-API extras failed to install -- demo will use
        echo        synthetic data. This is fine for the pitch video.
    ) else (
        echo done > ".venv\.live-api-installed"
    )
)

REM --- Verify streamlit actually imports before launching ----
"%VENVPY%" -c "import streamlit, plotly, dotenv" 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Streamlit / Plotly / dotenv failed to import after install.
    echo         Try deleting the .venv folder and re-running this launcher.
    echo.
    pause
    exit /b 1
)

REM --- Launch Streamlit --------------------------------------
echo.
echo ============================================================
echo   Arid-Edge Sentinel is starting...
echo   The browser will open automatically at http://localhost:8501
echo   Close this window to stop the app.
echo ============================================================
echo.

"%VENVPY%" -m streamlit run app.py ^
    --server.headless=false ^
    --browser.gatherUsageStats=false ^
    --theme.base=light

echo.
echo Streamlit exited. Press any key to close this window.
pause >nul
endlocal
