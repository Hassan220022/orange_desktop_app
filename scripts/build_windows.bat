@echo off
setlocal
:: ─────────────────────────────────────────────────────────────
:: Build Alarm Viewer as a standalone Windows .exe
:: Requirements: Python 3.9+ installed and on PATH.
:: The output EXE will be at alarm_app\dist\AlarmViewer.exe
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
echo [3/5] Building standalone EXE with PyInstaller...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "AlarmViewer" ^
    --icon alarm_app\assets\app_icon.ico ^
    --add-data "alarm_app\assets\app_icon.png;assets" ^
    --paths . ^
    --distpath alarm_app\dist ^
    --workpath alarm_app\build ^
    --specpath alarm_app ^
    --hidden-import pandas ^
    --hidden-import openpyxl ^
    --hidden-import xlrd ^
    --hidden-import pyarrow ^
    --hidden-import python_calamine ^
    alarm_app\scripts\pyinstaller_entry.py

echo.
echo [4/5] Cleaning up build artefacts...
rmdir /s /q alarm_app\build 2>nul
del /q alarm_app\AlarmViewer.spec 2>nul

echo.
echo [5/5] Done!
echo.
echo   Executable ready at:  alarm_app\dist\AlarmViewer.exe
echo   Copy that single file to any Windows PC - no Python needed!
echo.
call deactivate
popd
if /I "%CI%"=="true" goto :eof
if /I "%NO_PAUSE%"=="1" goto :eof
pause
