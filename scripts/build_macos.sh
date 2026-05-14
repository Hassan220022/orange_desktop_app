#!/usr/bin/env bash
set -euo pipefail

# Build Alarm Viewer as an installed-product macOS .app bundle.
# Requirements: Python 3.11+ on PATH.
# Output: dist/AlarmViewer.app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "============================================"
echo " Alarm Viewer | macOS Build Script"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH. Install Python 3.11+ and try again."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv not found on PATH. Install uv and try again."
  exit 1
fi

echo "[1/5] Creating virtual environment..."
uv venv .venv_build --python python3
source .venv_build/bin/activate

echo
echo "[2/5] Installing dependencies..."
uv pip install -r requirements.txt -q

echo
echo "[3/5] Building macOS app bundle with PyInstaller spec..."
if [[ "${ALARM_SKIP_CLOUDFLARED_DOWNLOAD:-0}" != "1" ]]; then
  python scripts/install_cloudflared.py
fi
chmod -R u+w dist/AlarmViewer dist/AlarmViewer.app build 2>/dev/null || true
rm -rf dist/AlarmViewer dist/AlarmViewer.app build

pyinstaller --noconfirm AlarmViewer.spec

echo
echo "[4/5] Cleaning up build artifacts..."
rm -rf build

echo
echo "[5/5] Done!"
echo
echo "  App bundle ready at: dist/AlarmViewer.app"
echo "  You can run it directly on macOS."
echo

deactivate || true
