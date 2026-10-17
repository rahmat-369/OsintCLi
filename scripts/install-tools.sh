#!/usr/bin/env bash
set -euo pipefail
project_dir="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
tool_name="${1:-}"
case "$tool_name" in
  sherlock) upstream_url='https://github.com/sherlock-project/sherlock'; pinned_commit='e40a45ec2a074b90703b3b4b842c8a3adbd6ada3';;
  maigret) upstream_url='https://github.com/soxoj/maigret'; pinned_commit='eaf820666d15bfd545129f3223e2261c27191e74';;
  exiftool)
    if command -v pkg >/dev/null; then pkg install -y exiftool
    elif command -v apt-get >/dev/null; then
      echo 'Pasang lewat package manager: sudo apt-get install libimage-exiftool-perl'
      exit 0
    else echo 'Pasang ExifTool dari https://exiftool.org sesuai OS Anda.'; exit 0; fi
    exiftool -ver; exit 0;;
  *) echo 'Usage: bash scripts/install-tools.sh sherlock|maigret|exiftool'; exit 2;;
esac
command -v git >/dev/null || { echo 'Git diperlukan.'; exit 1; }
tool_root="${OSINTCLI_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/osintcli}/tools/$tool_name"
python3 -m venv "$tool_root"
"$tool_root/bin/python" -m pip install -c "$project_dir/constraints/$tool_name.txt" "git+$upstream_url@$pinned_commit"
"$tool_root/bin/$tool_name" --help >/dev/null
"$tool_root/bin/python" -m pip freeze > "$tool_root/installed-lock.txt"
echo "$pinned_commit" > "$tool_root/audited-commit.txt"
echo "$tool_name terpasang terpisah. Pilih engine di menu Username."
echo 'Dependensi transitif tercatat di installed-lock.txt; uji live masih diperlukan.'
