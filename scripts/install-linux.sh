#!/usr/bin/env bash
set -euo pipefail
project_dir="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo 'Python 3.11+ diperlukan.'; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ diperlukan"'
venv_dir="${OSINTCLI_VENV:-$HOME/.local/share/osintcli/venv}"
python3 -m venv "$venv_dir" || { echo 'Pasang python3-venv melalui package manager, lalu ulangi.'; exit 1; }
if [[ "${1:-}" != '--core-only' ]]; then
  "$venv_dir/bin/python" -m pip install -r "$project_dir/requirements-reports.txt" || { echo 'Dependensi laporan gagal. Ulangi setelah jaringan/build dependencies siap; --core-only tersedia.'; exit 1; }
fi
"$venv_dir/bin/python" -m pip install --no-deps "$project_dir"
mkdir -p "$HOME/.local/bin"
ln -sfn "$venv_dir/bin/osintcli" "$HOME/.local/bin/osintcli"
"$venv_dir/bin/osintcli" doctor
echo 'Terpasang. Jalankan: ~/.local/bin/osintcli'
echo 'Untuk perintah singkat: export PATH="$HOME/.local/bin:$PATH"'
