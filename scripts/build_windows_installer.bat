@echo off
setlocal

:: Build Alarm Viewer as an installed-product Windows bundle and installer.
:: Requirements: Python 3.11+, Inno Setup (iscc), Windows.

pushd %~dp0..

echo ============================================
echo  Alarm Viewer ^| Windows Installer Build
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH. Install Python 3.11+ and try again.
    popd & exit /b 1
)

uv --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv not found on PATH. Install uv and try again.
    popd & exit /b 1
)

where iscc >nul 2>&1
if errorlevel 1 (
    echo ERROR: Inno Setup compiler (iscc) not found on PATH.
    echo Install Inno Setup 6 and ensure iscc is available.
    popd & exit /b 1
)

echo [1/7] Creating virtual environment...
uv venv .venv_build --python python
call .venv_build\Scripts\activate.bat

echo.
echo [2/7] Installing dependencies...
uv pip install -r requirements.txt -q

echo.
echo [3/7] Cleaning previous bundle output...
if /I not "%ALARM_SKIP_CLOUDFLARED_DOWNLOAD%"=="1" python scripts\install_cloudflared.py
rmdir /s /q dist\AlarmViewer 2>nul
rmdir /s /q build 2>nul

echo.
echo [4/7] Building installed app bundle with PyInstaller spec...
pyinstaller --noconfirm AlarmViewer.spec

echo.
echo [5/7] Smoke testing bundled app...
dist\AlarmViewer\AlarmViewer.exe --version
dist\AlarmViewer\AlarmViewer.exe --smoke-test

echo.
echo [6/7] Building installer with Inno Setup...
iscc installer\windows\AlarmViewer.iss

echo.
echo [7/7] Done!
echo.
echo   Bundle:    dist\AlarmViewer\
echo   Installer: dist\AlarmViewer-Setup.exe
echo.
echo The installed app bootstraps local SQLite, DuckDB, blobs, and logs
echo under %%USERPROFILE%%\.alarm_viewer on first launch.
echo.

call deactivate
popd

if /I "%CI%"=="true" goto :eof
if /I "%NO_PAUSE%"=="1" goto :eof
pause
