#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${OS:-}" != "Windows_NT" && "$(uname -s)" != MINGW* && "$(uname -s)" != CYGWIN* ]]; then
  echo "[ERROR] Windows EXE build must run on Windows runner."
  echo "Use GitHub Actions workflow '.github/workflows/release-installer-exe.yml'."
  exit 2
fi

python -m pip install --upgrade pip
python -m pip install pyinstaller

pyinstaller --noconfirm --clean openclaw_installer_gui.spec

mkdir -p release
cp -f dist/OpenClawInstaller.exe release/OpenClawInstaller.exe

echo "[OK] built release/OpenClawInstaller.exe"
