#!/usr/bin/env bash
# [SRS Section 7.5, NFR-07] Automated Build & Packaging Script for Ravlator macOS Bundle
set -euo pipefail

echo "============================================================"
echo " Building Ravlator — Windows Gaming Manager for macOS"
echo "============================================================"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_DIR}/dist"
BUILD_DIR="${PROJECT_DIR}/build"
APP_NAME="Ravlator.app"
DMG_NAME="Ravlator-0.1.0-arm64.dmg"

cd "${PROJECT_DIR}"

# 1. Clean previous builds
echo "[*] Cleaning build directories..."
rm -rf "${DIST_DIR}" "${BUILD_DIR}"

# 2. Package standalone macOS .app bundle using PyInstaller
echo "[*] Compiling standalone application bundle..."
.venv/bin/pip install -q pyinstaller

.venv/bin/pyinstaller \
    --name="Ravlator" \
    --windowed \
    --onedir \
    --noconfirm \
    --clean \
    --osx-bundle-identifier="com.ravlator.app" \
    --add-data="assets:assets" \
    --add-data="docs:docs" \
    --collect-all="pyside6" \
    ravlator/gui/app.py

echo "[+] Application bundle created at: ${DIST_DIR}/${APP_NAME}"

# 3. Code Signing (Ad-hoc if no Developer ID Certificate provided)
SIGN_IDENTITY="${APPLE_DEVELOPER_IDENTITY:-"-"}"
echo "[*] Applying macOS Code Signing (Identity: ${SIGN_IDENTITY})..."
codesign --force --deep --options runtime --sign "${SIGN_IDENTITY}" "${DIST_DIR}/${APP_NAME}"

# 4. Generate Disk Image (.dmg)
echo "[*] Creating macOS Disk Image (.dmg)..."
hdiutil create \
    -volname "Ravlator" \
    -srcfolder "${DIST_DIR}/${APP_NAME}" \
    -ov \
    -format UDZO \
    "${DIST_DIR}/${DMG_NAME}"

echo "============================================================"
echo "[+] SUCCESS: Built macOS DMG at:"
echo "    ${DIST_DIR}/${DMG_NAME}"
echo "============================================================"
