#!/usr/bin/env bash
# Sets up a virtualenv, installs Python deps and checks for ffmpeg + fonts.
set -euo pipefail
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo "ffmpeg not found (apt install ffmpeg / brew install ffmpeg)"; exit 1; }
python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
mkdir -p fonts
base=https://raw.githubusercontent.com/google/fonts/main/ofl
[ -f fonts/Anton-Regular.ttf ]   || curl -sSfL -o fonts/Anton-Regular.ttf   "$base/anton/Anton-Regular.ttf"
[ -f fonts/Oswald-Variable.ttf ] || curl -sSfL -o fonts/Oswald-Variable.ttf "$base/oswald/Oswald%5Bwght%5D.ttf"
echo "Ready. Run:  . .venv/bin/activate && python make_short.py   (or --lang pt)"
