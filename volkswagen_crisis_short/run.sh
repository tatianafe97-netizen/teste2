#!/usr/bin/env bash
# Create the venv (first run), install deps, render the Short.
# Usage: ./run.sh            -> English
#        ./run.sh --lang pt  -> Portuguese (pt-BR-AntonioNeural)
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python make_short.py "$@"
