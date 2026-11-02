#!/usr/bin/env bash
# One-shot: create venv, install deps, build output_short.mp4, run QA.
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "FFmpeg is required (brew install ffmpeg / apt install ffmpeg)"; exit 1; }
PY=${PYTHON:-python3}
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python make_short.py "$@"
