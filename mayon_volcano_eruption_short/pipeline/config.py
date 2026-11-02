"""Global constants: canvas, timing, layout, palette and fonts."""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# ---------------------------------------------------------------- canvas ---
W, H = 1080, 1920
FPS = 30
DURATION = 50.0
N_FRAMES = int(round(DURATION * FPS))

# Scene windows (seconds) – fixed by the editorial brief.
SCENES = [(0.0, 12.0), (12.0, 25.0), (25.0, 38.0), (38.0, 50.0)]

# Narration slot for each scene: [scene_start + LEAD, scene_end - TAIL].
VOICE_LEAD = 0.25
VOICE_TAIL = 0.30
MAX_ATEMPO = 1.30  # never speed a segment up by more than this

# ---------------------------------------------------------------- layout ---
# Vertical bands (px). YouTube Shorts overlays its own UI on the bottom
# ~380 px and right ~120 px, so everything important sits above y=1540.
HEADER_TOP = 64
HEADER_BOTTOM = 252
INFO_Y = 266
PROGRESS_Y = 312
CHIP_Y = 332
PANEL_TOP = 392
PANEL_BOTTOM = 1150
PANEL_X0, PANEL_X1 = 40, 1040
CAPTION_CY = 1290          # caption block vertical centre (central safe zone)
CAPTION_MAX_W = 940
TICKER_Y0, TICKER_Y1 = 1436, 1498
FOOTER_Y = 1518

# --------------------------------------------------------------- palette ---
ASH = (20, 20, 23)           # volcanic ash charcoal
ASH_2 = (34, 34, 38)
ASH_3 = (52, 52, 58)
ORANGE = (255, 106, 0)       # alert orange
ORANGE_HOT = (255, 140, 30)
SULFUR = (255, 214, 10)      # sulfur yellow
WHITE = (246, 246, 240)      # stark telemetry white
GRAY = (150, 150, 158)
GRAY_DIM = (96, 96, 104)
RED = (232, 32, 44)
LAVA = (255, 70, 20)


def hexc(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb[:3])


# ----------------------------------------------------------------- fonts ---
_FONT_CANDIDATES = {
    "display": [
        "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
        "/usr/share/fonts/opentype/inter/Inter-Black.otf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ("fc", "sans:black"),
    ],
    "bold": [
        "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ("fc", "sans:bold"),
    ],
    "semi": [
        "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ("fc", "sans:semibold"),
    ],
    "mono": [
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        ("fc", "monospace:bold"),
    ],
}


@lru_cache(maxsize=None)
def font_path(kind: str) -> str | None:
    for cand in _FONT_CANDIDATES[kind]:
        if isinstance(cand, tuple):
            if shutil.which("fc-match"):
                try:
                    p = subprocess.run(["fc-match", "-f", "%{file}", cand[1]],
                                       capture_output=True, text=True, timeout=10).stdout.strip()
                    if p and os.path.exists(p):
                        return p
                except Exception:
                    pass
        elif os.path.exists(cand):
            return cand
    return None


@lru_cache(maxsize=None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    p = font_path(kind)
    if p is None:
        return ImageFont.load_default(size)
    return ImageFont.truetype(p, size)


def fit_font(kind: str, text: str, max_w: int, start: int, minimum: int = 12):
    """Largest font size (<= start) whose rendering of *text* fits max_w."""
    size = start
    while size > minimum:
        f = font(kind, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return font(kind, minimum)


ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
BUILD_DIR = ROOT / "build"
OUTPUT_DIR = ROOT / "output"
