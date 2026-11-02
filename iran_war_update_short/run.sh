#!/usr/bin/env bash
# One-shot: create venv, install deps, render the Short. Extra args go to make_short.py (e.g. --lang pt).
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python make_short.py "$@"
