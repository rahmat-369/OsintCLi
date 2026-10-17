#!/usr/bin/env bash
set -euo pipefail
project_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
venv_dir="${OSINTCLI_VENV:-$HOME/.local/share/osintcli/venv}"
if [[ -x "$venv_dir/bin/osintcli" ]]; then exec "$venv_dir/bin/osintcli" "$@"; fi
cd "$project_dir"
exec python3 -m osintcli "$@"
