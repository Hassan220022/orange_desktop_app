#!/usr/bin/env bash
set -euo pipefail

# Build Alarm Viewer app bundle and package it into a DMG installer.
# Optional signing/notarization is enabled via environment variables:
#   APPLE_DEVELOPER_ID_APPLICATION
#   APPLE_ID, APPLE_TEAM_ID, APPLE_APP_SPECIFIC_PASSWORD

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "============================================"
echo " Alarm Viewer | macOS Installer Build"
echo "============================================"
echo

echo "[1/5] Building app bundle..."
"${SCRIPT_DIR}/build_macos.sh"

APP_BUNDLE="dist/AlarmViewer.app"
DMG_PATH="dist/AlarmViewer-macOS.dmg"
STAGE_DIR="dist/dmg-root"

if [[ ! -d "${APP_BUNDLE}" ]]; then
  echo "ERROR: App bundle not found at ${APP_BUNDLE}"
  exit 1
fi

if [[ -n "${APPLE_DEVELOPER_ID_APPLICATION:-}" ]]; then
  echo
  echo "[2/5] Code-signing app bundle..."
  codesign --deep --force --options runtime \
    --sign "${APPLE_DEVELOPER_ID_APPLICATION}" "${APP_BUNDLE}"
else
  echo
  echo "[2/5] Skipping code-signing (APPLE_DEVELOPER_ID_APPLICATION not set)."
fi

echo
echo "[3/5] Creating DMG staging layout..."
rm -rf "${STAGE_DIR}" "${DMG_PATH}"
mkdir -p "${STAGE_DIR}"
cp -R "${APP_BUNDLE}" "${STAGE_DIR}/AlarmViewer.app"
ln -s /Applications "${STAGE_DIR}/Applications"

echo
echo "[4/5] Building DMG image..."
hdiutil create \
  -volname "AlarmViewer" \
  -srcfolder "${STAGE_DIR}" \
  -ov -format UDZO \
  "${DMG_PATH}"

if [[ -n "${APPLE_DEVELOPER_ID_APPLICATION:-}" ]]; then
  codesign --force --sign "${APPLE_DEVELOPER_ID_APPLICATION}" "${DMG_PATH}" || true
fi

if [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]]; then
  echo
  echo "[5/5] Submitting DMG for notarization..."
  xcrun notarytool submit "${DMG_PATH}" \
    --apple-id "${APPLE_ID}" \
    --team-id "${APPLE_TEAM_ID}" \
    --password "${APPLE_APP_SPECIFIC_PASSWORD}" \
    --wait
  xcrun stapler staple "${APP_BUNDLE}" || true
  xcrun stapler staple "${DMG_PATH}" || true
else
  echo
  echo "[5/5] Skipping notarization (APPLE_ID/APPLE_TEAM_ID/APPLE_APP_SPECIFIC_PASSWORD not set)."
fi

echo
echo "Done."
echo "  App bundle: ${APP_BUNDLE}"
echo "  DMG:        ${DMG_PATH}"
