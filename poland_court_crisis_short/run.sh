#!/usr/bin/env bash
# One-shot runner: creates the venv, installs deps, renders the Short.
# Usage: ./run.sh            (English)
#        ./run.sh --lang pt  (Portuguese narration + captions)
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "FFmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python make_short.py "$@"
