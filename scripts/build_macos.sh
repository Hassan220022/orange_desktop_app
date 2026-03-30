#!/usr/bin/env bash
set -euo pipefail

# Build Alarm Viewer as a standalone macOS .app bundle.
# Requirements: Python 3.9+ on PATH.
# Output: dist/AlarmViewer.app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "============================================"
echo " Alarm Viewer | macOS Build Script"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH. Install Python 3.9+ and try again."
  exit 1
fi

echo "[1/5] Creating virtual environment..."
python3 -m venv .venv_build
source .venv_build/bin/activate

echo
echo "[2/5] Installing dependencies..."
python -m pip install --upgrade pip -q
python -m pip install PyQt5 pandas numpy openpyxl xlrd pyinstaller -q

echo
echo "[3/5] Building macOS app bundle with PyInstaller..."
pyinstaller \
  --windowed \
  --name "AlarmViewer" \
  --distpath "dist" \
  --workpath "build" \
  --specpath "." \
  --hidden-import pandas \
  --hidden-import openpyxl \
  --hidden-import xlrd \
  scripts/pyinstaller_entry.py

echo
echo "[4/5] Cleaning up build artifacts..."
rm -rf build
rm -f AlarmViewer.spec

echo
echo "[5/5] Done!"
echo
echo "  App bundle ready at: dist/AlarmViewer.app"
echo "  You can run it directly on macOS."
echo

deactivate || true
