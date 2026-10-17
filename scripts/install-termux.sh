#!/usr/bin/env bash
set -euo pipefail
command -v pkg >/dev/null || { echo 'Script ini untuk Termux. Linux: bash scripts/install-linux.sh'; exit 1; }
project_dir="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
pkg install -y python git
if [[ "${1:-}" != '--core-only' ]]; then
  pkg install -y clang make pkg-config libjpeg-turbo zlib freetype libpng
fi
# Termux owns its pip; do not upgrade system pip or ask for root.
python -c 'import sys; assert sys.version_info >= (3,11), "Update Python Termux ke 3.11+"'
export OSINTCLI_VENV="${OSINTCLI_VENV:-$HOME/.local/share/osintcli/venv}"
bash "$project_dir/scripts/install-linux.sh" "${1:-}"
ln -sfn "$OSINTCLI_VENV/bin/osintcli" "$PREFIX/bin/osintcli"
echo 'Jalankan: osintcli'
echo 'Izin storage hanya diperlukan saat export Android: termux-setup-storage'
