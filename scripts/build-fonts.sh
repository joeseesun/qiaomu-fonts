#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 ]]; then
  printf 'Usage: %s /path/to/punchcutter/skills/punchcutter [family-slug ...]\n' "$0" >&2
  exit 2
fi
punchcutter="$1"
shift
python_bin="${PYTHON:-python3}"

export PYTHONDONTWRITEBYTECODE=1 PUNCHCUTTER_TELEMETRY=0
if [[ "$(uname -s)" == Darwin ]]; then
  export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:+$DYLD_FALLBACK_LIBRARY_PATH:}/opt/homebrew/lib:/usr/local/lib:/usr/lib"
fi

mkdir -p "$root/build"
if [[ $# -eq 0 ]]; then
  set -- trivulzio-quill chawton-script arles-letter monticello-draft amherst-pencil trinity-notes
fi
for family in "$@"; do
  case "$family" in
    trivulzio-quill|chawton-script|arles-letter|monticello-draft|amherst-pencil|trinity-notes) ;;
    *) printf 'Unknown font family slug: %s\n' "$family" >&2; exit 2 ;;
  esac
  "$python_bin" "$punchcutter/scripts/punchcutter.py" build \
    "$root/sources/$family/spec.json" --out "$root/build/$family"
done
