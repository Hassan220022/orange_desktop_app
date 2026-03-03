@echo off
setlocal
:: ─────────────────────────────────────────────────────────────
:: Build Alarm Viewer as a standalone Windows .exe
:: Requirements: Python 3.9+ installed and on PATH.
:: The output EXE will be at dist\AlarmViewer.exe
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
pip install PyQt5 pandas numpy openpyxl xlrd pyinstaller -q

echo.
echo [3/5] Building standalone EXE with PyInstaller...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "AlarmViewer" ^
    --hidden-import pandas ^
    --hidden-import openpyxl ^
    --hidden-import xlrd ^
    alarm_app\main.py

echo.
echo [4/5] Cleaning up build artefacts...
rmdir /s /q build 2>nul
del /q AlarmViewer.spec 2>nul

echo.
echo [5/5] Done!
echo.
echo   Executable ready at:  dist\AlarmViewer.exe
echo   Copy that single file to any Windows PC - no Python needed!
echo.
call deactivate
popd
pause
