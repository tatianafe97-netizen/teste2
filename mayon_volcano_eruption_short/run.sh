#!/usr/bin/env bash
# One-shot bootstrap: create venv, install deps, render the Short.
#   ./run.sh              → output/mayon_eruption_short.mp4 (English)
#   ./run.sh --lang pt    → output/mayon_eruption_short_pt.mp4 (Portuguese)
set -euo pipefail
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null || { echo "ffmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

.venv/bin/python make_short.py "$@"
