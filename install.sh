#!/usr/bin/env bash
set -euo pipefail
project_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
if command -v pkg >/dev/null; then bash "$project_dir/scripts/install-termux.sh" "$@"
else bash "$project_dir/scripts/install-linux.sh" "$@"; fi
