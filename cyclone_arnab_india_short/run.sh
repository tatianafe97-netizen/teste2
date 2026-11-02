#!/usr/bin/env bash
# One-shot: create venv, install deps, render the Short.
#   ./run.sh              -> English  (cyclone_arnab_short.mp4)
#   ./run.sh --lang pt    -> Portuguese (cyclone_arnab_short_pt.mp4)
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python generate_short.py "$@"
