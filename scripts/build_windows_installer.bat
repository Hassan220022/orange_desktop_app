@echo off
setlocal

:: Build Alarm Viewer executable and Windows installer (.exe).
:: Requirements: Python 3.9+, Inno Setup (iscc), Windows.

pushd %~dp0..

echo ============================================
echo  Alarm Viewer ^| Windows Installer Build
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH. Install Python 3.9+ and try again.
    popd & exit /b 1
)

where iscc >nul 2>&1
if errorlevel 1 (
    echo ERROR: Inno Setup compiler (iscc) not found on PATH.
    echo Install Inno Setup 6 and ensure iscc is available.
    popd & exit /b 1
)

echo [1/6] Creating virtual environment...
python -m venv .venv_build
call .venv_build\Scripts\activate.bat

echo.
echo [2/6] Installing dependencies...
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo.
echo [3/6] Building standalone EXE with PyInstaller...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "AlarmViewer" ^
    --icon assets\app_icon.ico ^
    --add-data "assets\app_icon.png;assets" ^
    --paths .. ^
    --collect-submodules alarm_app ^
    --distpath dist ^
    --workpath build ^
    --specpath . ^
    --hidden-import pandas ^
    --hidden-import openpyxl ^
    --hidden-import xlrd ^
    --hidden-import pyarrow ^
    --hidden-import python_calamine ^
    scripts/pyinstaller_entry.py

echo.
echo [4/6] Building installer with Inno Setup...
iscc installer\windows\AlarmViewer.iss

echo.
echo [5/6] Cleaning up build artefacts...
rmdir /s /q build 2>nul
del /q AlarmViewer.spec 2>nul

echo.
echo [6/6] Done!
echo.
echo   EXE:      dist\AlarmViewer.exe
echo   Installer: dist\AlarmViewer-Setup.exe
echo.

call deactivate
popd

if /I "%CI%"=="true" goto :eof
if /I "%NO_PAUSE%"=="1" goto :eof
pause
