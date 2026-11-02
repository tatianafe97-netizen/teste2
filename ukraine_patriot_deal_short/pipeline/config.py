"""Global constants: canvas, timing, palette, layout and font resolution."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
BUILD_DIR = ROOT / "build"

# ── Canvas ────────────────────────────────────────────────────────────────
W, H = 1080, 1920
FPS = 30
DURATION = 50.0
N_FRAMES = int(round(DURATION * FPS))


@dataclass(frozen=True)
class SceneSlot:
    key: str
    start: float
    end: float

    @property
    def dur(self) -> float:
        return self.end - self.start


SCENES = (
    SceneSlot("package", 0.0, 12.0),
    SceneSlot("money", 12.0, 25.0),
    SceneSlot("timeline", 25.0, 38.0),
    SceneSlot("impact", 38.0, 50.0),
)

# ── Palette: deep navy / radar cyan / NATO blue / alert amber ────────────
NAVY_DEEP = (4, 11, 26)
NAVY = (9, 22, 46)
PANEL = (12, 30, 60)
PANEL_HI = (20, 46, 86)
GRID = (0, 190, 230)
CYAN = (0, 229, 255)
CYAN_DIM = (0, 140, 170)
NATO_BLUE = (0, 73, 144)
NATO_LIGHT = (40, 120, 210)
AMBER = (255, 176, 0)
AMBER_DIM = (180, 115, 0)
ALERT_RED = (255, 64, 64)
WHITE = (242, 247, 252)
GREY = (138, 160, 188)
BLACK = (0, 0, 0)


def rgba(c: tuple[int, int, int], a: int | float = 255) -> tuple[int, int, int, int]:
    return (c[0], c[1], c[2], int(max(0, min(255, a))))


def hexc(c: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % c


# ── Layout (YouTube Shorts safe zones) ───────────────────────────────────
MARGIN_X = 50
HEADER_Y0, HEADER_Y1 = 60, 214
TAG_Y = 232                # scene tag strip
KICKER_Y = 292             # kicker chip
HEADLINE_Y = 340           # scene headline
CONTENT_BOTTOM = 1150      # graphics must stay above the caption zone
CAPTION_CENTER_Y = 1275    # central safe zone for burned-in subtitles
CAPTION_MAX_W = 960
LOWER_THIRD_Y = 1405
TICKER_Y = 1560

# ── Fonts (system Inter / JetBrains Mono with matplotlib DejaVu fallback) ─
_FONT_CANDIDATES = {
    "black": ["Inter-Black.otf", "InterDisplay-Black.otf", "DejaVuSans-Bold.ttf"],
    "xbold": ["Inter-ExtraBold.otf", "InterDisplay-ExtraBold.otf", "DejaVuSans-Bold.ttf"],
    "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf"],
    "semi": ["Inter-SemiBold.otf", "Inter-Medium.otf", "DejaVuSans.ttf"],
    "mono": ["JetBrainsMono-Bold.ttf", "DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf"],
    "mono_reg": ["JetBrainsMono-Regular.ttf", "JetBrainsMono-Medium.ttf", "DejaVuSansMono.ttf"],
}
_FONT_DIRS = [
    ROOT / "fonts",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path("C:/Windows/Fonts"),
]


@lru_cache(maxsize=None)
def _font_index() -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for d in _FONT_DIRS:
        if d.exists():
            for p in d.rglob("*"):
                if p.suffix.lower() in (".ttf", ".otf"):
                    idx.setdefault(p.name, p)
    try:  # matplotlib always ships DejaVu, so there is a guaranteed fallback
        import matplotlib
        mpl_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        for p in mpl_dir.glob("*.ttf"):
            idx.setdefault(p.name, p)
    except Exception:
        pass
    return idx


@lru_cache(maxsize=None)
def font_path(style: str) -> str:
    idx = _font_index()
    for name in _FONT_CANDIDATES[style]:
        if name in idx:
            return str(idx[name])
    raise FileNotFoundError(f"No font found for style {style!r}")


@lru_cache(maxsize=None)
def font(style: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(style), max(6, int(size)))
