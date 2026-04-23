@echo off
setlocal
:: ─────────────────────────────────────────────────────────────
:: Build Alarm Viewer as an installed-product Windows bundle.
:: Requirements: Python 3.11+ installed and on PATH.
:: The output bundle will be at alarm_app\dist\AlarmViewer\
:: Run from anywhere — script navigates to project root.
:: ─────────────────────────────────────────────────────────────

:: Navigate to project root (two levels up from alarm_app\scripts\)
pushd %~dp0..\..

echo ============================================
echo  Alarm Viewer  ^|  Windows Build Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH. Install Python 3.9+ and try again.
    popd & pause & exit /b 1
)

echo [1/5] Creating virtual environment...
python -m venv .venv_build
call .venv_build\Scripts\activate.bat

echo.
echo [2/5] Installing dependencies...
pip install --upgrade pip -q
pip install -r alarm_app\requirements.txt -q

echo.
echo [3/5] Building installed bundle with PyInstaller spec...
rmdir /s /q alarm_app\dist\AlarmViewer 2>nul
rmdir /s /q alarm_app\build 2>nul
pushd alarm_app
pyinstaller --noconfirm AlarmViewer.spec
popd

echo.
echo [4/5] Cleaning up build artefacts...
rmdir /s /q alarm_app\build 2>nul

echo.
echo [5/5] Done!
echo.
echo   Bundle ready at:  alarm_app\dist\AlarmViewer\
echo   Launch with:      alarm_app\dist\AlarmViewer\AlarmViewer.exe
echo   First launch bootstraps %%USERPROFILE%%\.alarm_viewer storage.
echo.
call deactivate
popd
if /I "%CI%"=="true" goto :eof
if /I "%NO_PAUSE%"=="1" goto :eof
pause
