#!/usr/bin/env python3
"""
GLOBAL NEWS 1.0 - NEWS IN REAL TIME
Weather Desk Short: Cyclone Arnab slams India's eastern coast.

Fully automated pipeline:
  1. edge-tts voiceover (+ word-level WebVTT timings)
  2. scipy-synthesised low-frequency weather drone (-22 dBFS RMS)
  3. optional B-roll from assets/ (graded, vignetted, looped)
  4. Pillow + matplotlib telemetry graphics rendered frame-by-frame
  5. FFmpeg composite -> 1080x1920 / 30 fps / H.264 + AAC MP4

Usage:
    python generate_short.py              # English (en-US-ChristopherNeural)
    python generate_short.py --lang pt    # Portuguese (pt-BR-AntonioNeural)
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import shutil
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon, Rectangle  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

# --------------------------------------------------------------------------------------
# Global format
# --------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30
DURATION = 50.0
N_FRAMES = int(DURATION * FPS)
VOICE_OFFSET = 0.35          # seconds of silence before narration starts
VOICE_TAIL = 1.0             # minimum breathing room after narration ends
SCENES = [(0.0, 12.0), (12.0, 25.0), (25.0, 38.0), (38.0, 50.0)]

# Panel (main visual) geometry
PX, PY, PW, PH = 40, 405, 1000, 800
CAPTION_CY = 1338            # caption centre line (central safe zone)

# Palette: cyclone satellite navy, warning amber, storm teal, stark white
NAVY_DEEP = (4, 10, 26)
NAVY = (9, 22, 48)
NAVY_PANEL = (12, 30, 62)
NAVY_LINE = (34, 62, 104)
AMBER = (255, 176, 0)
AMBER_HOT = (255, 122, 20)
ALERT_RED = (232, 44, 44)
TEAL = (0, 201, 183)
TEAL_DIM = (0, 120, 112)
WHITE = (246, 249, 252)
GREY = (168, 184, 204)

CAT_COLORS = {
    "D": (0, 201, 183),
    "DD": (96, 222, 160),
    "CS": (255, 214, 0),
    "SCS": (255, 176, 0),
    "VSCS": (255, 92, 30),
}

# --------------------------------------------------------------------------------------
# Editorial content (facts cross-checked against AP / IMD / NDRF reporting, see SOURCES.md)
# --------------------------------------------------------------------------------------
CONTENT = {
    "en": {
        "voice": "en-US-ChristopherNeural",
        "script": (
            "Breaking from the Global News weather desk. Cyclone Arnab has slammed into "
            "India's eastern coast. The storm strengthened over the Bay of Bengal and made "
            "landfall near Narsapur, close to Bhimavaram in Andhra Pradesh, with sustained "
            "winds of up to 135 kilometers per hour and gusts near 150. More than 100,000 "
            "coastal residents were moved into cyclone shelters across Andhra Pradesh and "
            "southern Odisha. National Disaster Response Force teams are deployed, nearly "
            "1,100 medical teams are in the field, and more than 30,000 fishing boats are "
            "secured ashore. At least three people have been killed. Flash floods have "
            "swamped paddy fields, power and phone lines are down, and the weakening storm "
            "is pushing inland toward Chhattisgarh. Follow Global News 1.0 for real-time updates."
        ),
        "header_top": "GLOBAL NEWS 1.0  \u2022  WEATHER DESK:",
        "header_main": "CYCLONE ARNAB SLAMS INDIA",
        "alert": "SEVERE WEATHER ALERT",
        "live": "LIVE",
        "region": "BAY OF BENGAL",
        "scene_kickers": ["01 \u00b7 RADAR TRACK", "02 \u00b7 EVACUATION", "03 \u00b7 MOBILIZATION",
                          "04 \u00b7 AFTERMATH"],
        "scene_titles": ["BAY OF BENGAL RADAR TRACK", "100,000+ EVACUATED",
                         "EMERGENCY MOBILIZATION", "AFTERMATH & RESTORATION"],
        "chips": ["WINDS 125\u2013135 KM/H", "GUSTS ~150 KM/H", "LANDFALL 28 OCT"],
        "ticker": ("CYCLONE ARNAB MAKES LANDFALL NEAR NARSAPUR, ANDHRA PRADESH   \u2022   "
                   "SUSTAINED WINDS 125\u2013135 KM/H, GUSTS NEAR 150 KM/H   \u2022   "
                   "100,000+ COASTAL RESIDENTS IN CYCLONE SHELTERS   \u2022   "
                   "NDRF TEAMS DEPLOYED ACROSS ANDHRA PRADESH & ODISHA   \u2022   "
                   "30,000+ FISHING BOATS SECURED   \u2022   "),
        "radar": {
            "station": "DWR VISAKHAPATNAM",
            "track": "ILLUSTRATIVE TRACK",
            "imd": "IMD CLASS",
            "range": "CLASS RANGE",
            "landfall": "LANDFALL",
            "landfall_sub": "NEAR NARSAPUR / BHIMAVARAM",
            "weakening": "WEAKENING INLAND",
            "observed": "LANDFALL WINDS",
            "observed_val": "125\u2013135 KM/H \u00b7 GUSTS ~150",
            "names": {"D": "DEPRESSION", "DD": "DEEP DEPRESSION", "CS": "CYCLONIC STORM",
                      "SCS": "SEVERE CYCLONIC STORM", "VSCS": "VERY SEVERE CYCLONIC STORM"},
        },
        "evac": {
            "counter": "RESIDENTS EVACUATED",
            "zone": "COASTAL EVACUATION ZONE",
            "shelters": "CYCLONE SHELTERS",
            "landfall": "LANDFALL ZONE",
            "states": {"AP": "ANDHRA\nPRADESH", "OD": "ODISHA", "TG": "TELANGANA",
                       "CG": "CHHATTISGARH", "BOB": "BAY OF BENGAL"},
            "note": "SCHEMATIC MAP \u00b7 BOUNDARIES APPROXIMATE",
        },
        "metrics_title": "LIVE RESPONSE STATUS",
        "metrics": [
            ("people", 100000, "{:,}+", "RESIDENTS\nEVACUATED"),
            ("medic", 1100, "~{:,}", "MEDICAL\nTEAMS"),
            ("boat", 30000, "{:,}+", "FISHING BOATS\nSECURED"),
            ("shield", None, "NDRF", "RESCUE TEAMS\nDEPLOYED"),
        ],
        "active": "ACTIVE",
        "after_title": "IMPACT & RESTORATION TRACKER",
        "after_rows": [
            ("CASUALTIES", "At least 3 killed in Andhra Pradesh", "CONFIRMED", ALERT_RED, False),
            ("FLASH FLOODS", "Coastal towns & low-lying districts", "ACTIVE", AMBER_HOT, False),
            ("PADDY FIELDS", "Farmland inundated across the delta", "SUBMERGED", AMBER, False),
            ("POWER & TELECOM", "Lines down, networks damaged", "RESTORING", TEAL, True),
            ("STORM TRACK", "Weakening, moving inland to Chhattisgarh", "INLAND", TEAL, True),
        ],
        "cta_1": "FOLLOW GLOBAL NEWS 1.0",
        "cta_2": "FOR REAL-TIME UPDATES",
        "watermark": "GLOBAL NEWS 1.0 \u2022 NEWS IN REAL TIME",
    },
    "pt": {
        "voice": "pt-BR-AntonioNeural",
        "script": (
            "Urgente, da central do clima da Global News. O ciclone Arnab atingiu a costa "
            "leste da Índia. A tempestade ganhou força na Baía de Bengala e tocou o continente "
            "perto de Narsapur, próximo a Bhimavaram, em Andhra Pradesh, com ventos de até "
            "135 quilômetros por hora e rajadas perto de 150. Mais de 100 mil moradores do "
            "litoral foram levados para abrigos em Andhra Pradesh e no sul de Odisha. Equipes "
            "da Força Nacional de Resposta a Desastres estão em campo, com cerca de 1.100 "
            "equipes médicas, e mais de 30 mil barcos de pesca foram recolhidos. Pelo menos "
            "três pessoas morreram. Enchentes alagaram arrozais, a energia e a telefonia "
            "caíram, e a tempestade avança para o interior, rumo a Chhattisgarh. Siga a "
            "Global News 1.0 para atualizações em tempo real."
        ),
        "header_top": "GLOBAL NEWS 1.0  \u2022  CENTRAL DO CLIMA:",
        "header_main": "CICLONE ARNAB ATINGE A ÍNDIA",
        "alert": "ALERTA DE TEMPO SEVERO",
        "live": "AO VIVO",
        "region": "BAÍA DE BENGALA",
        "scene_kickers": ["01 \u00b7 RADAR", "02 \u00b7 EVACUAÇÃO", "03 \u00b7 MOBILIZAÇÃO",
                          "04 \u00b7 CONSEQUÊNCIAS"],
        "scene_titles": ["TRAJETÓRIA NA BAÍA DE BENGALA", "100 MIL+ EVACUADOS",
                         "MOBILIZAÇÃO DE EMERGÊNCIA", "DANOS E RECUPERAÇÃO"],
        "chips": ["VENTOS 125\u2013135 KM/H", "RAJADAS ~150 KM/H", "IMPACTO 28 OUT"],
        "ticker": ("CICLONE ARNAB TOCA A COSTA PERTO DE NARSAPUR, ANDHRA PRADESH   \u2022   "
                   "VENTOS DE 125\u2013135 KM/H, RAJADAS PERTO DE 150 KM/H   \u2022   "
                   "MAIS DE 100 MIL MORADORES EM ABRIGOS   \u2022   "
                   "EQUIPES DA NDRF EM ANDHRA PRADESH E ODISHA   \u2022   "
                   "MAIS DE 30 MIL BARCOS RECOLHIDOS   \u2022   "),
        "radar": {
            "station": "RADAR VISAKHAPATNAM",
            "track": "TRAJETÓRIA ILUSTRATIVA",
            "imd": "CLASSE IMD",
            "range": "FAIXA DA CLASSE",
            "landfall": "IMPACTO NA COSTA",
            "landfall_sub": "PERTO DE NARSAPUR / BHIMAVARAM",
            "weakening": "ENFRAQUECENDO NO INTERIOR",
            "observed": "VENTOS NO IMPACTO",
            "observed_val": "125\u2013135 KM/H \u00b7 RAJADAS ~150",
            "names": {"D": "DEPRESSÃO", "DD": "DEPRESSÃO PROFUNDA", "CS": "TEMPESTADE CICLÔNICA",
                      "SCS": "TEMPESTADE CICLÔNICA SEVERA",
                      "VSCS": "TEMPESTADE CICLÔNICA MUITO SEVERA"},
        },
        "evac": {
            "counter": "MORADORES EVACUADOS",
            "zone": "ZONA COSTEIRA DE EVACUAÇÃO",
            "shelters": "ABRIGOS CONTRA CICLONES",
            "landfall": "ZONA DE IMPACTO",
            "states": {"AP": "ANDHRA\nPRADESH", "OD": "ODISHA", "TG": "TELANGANA",
                       "CG": "CHHATTISGARH", "BOB": "BAÍA DE BENGALA"},
            "note": "MAPA ESQUEMÁTICO \u00b7 LIMITES APROXIMADOS",
        },
        "metrics_title": "STATUS DA RESPOSTA",
        "metrics": [
            ("people", 100000, "{:,}+", "MORADORES\nEVACUADOS"),
            ("medic", 1100, "~{:,}", "EQUIPES\nMÉDICAS"),
            ("boat", 30000, "{:,}+", "BARCOS DE PESCA\nRECOLHIDOS"),
            ("shield", None, "NDRF", "EQUIPES DE RESGATE\nMOBILIZADAS"),
        ],
        "active": "ATIVO",
        "after_title": "PAINEL DE DANOS E RECUPERAÇÃO",
        "after_rows": [
            ("VÍTIMAS", "Ao menos 3 mortos em Andhra Pradesh", "CONFIRMADO", ALERT_RED, False),
            ("ENCHENTES", "Cidades costeiras e áreas baixas", "ATIVO", AMBER_HOT, False),
            ("ARROZAIS", "Lavouras alagadas no delta", "SUBMERSOS", AMBER, False),
            ("ENERGIA E TELECOM", "Linhas caídas, redes danificadas", "RESTAURANDO", TEAL, True),
            ("TRAJETÓRIA", "Enfraquece rumo a Chhattisgarh", "INTERIOR", TEAL, True),
        ],
        "cta_1": "SIGA A GLOBAL NEWS 1.0",
        "cta_2": "ATUALIZAÇÕES EM TEMPO REAL",
        "watermark": "GLOBAL NEWS 1.0 \u2022 NEWS IN REAL TIME",
    },
}


def thousands(n: int, lang: str) -> str:
    s = f"{n:,}"
    return s.replace(",", ".") if lang == "pt" else s


# --------------------------------------------------------------------------------------
# Geography (schematic, lon/lat). Approximate - for broadcast illustration only.
# --------------------------------------------------------------------------------------
COAST = [
    (79.85, 11.5), (79.86, 12.0), (80.15, 12.5), (80.29, 13.08), (80.33, 13.55), (80.2, 14.0),
    (80.12, 14.3), (80.18, 14.8), (80.08, 15.3), (80.2, 15.55), (80.35, 15.82), (80.65, 15.85),
    (80.95, 15.73), (81.12, 15.88), (81.15, 16.17), (81.35, 16.3), (81.55, 16.35),
    (81.72, 16.31), (81.95, 16.45), (82.25, 16.62), (82.36, 16.88), (82.3, 16.98),
    (82.5, 17.15), (82.8, 17.4), (83.1, 17.55), (83.3, 17.66), (83.55, 17.85), (83.85, 18.1),
    (84.13, 18.3), (84.4, 18.55), (84.7, 18.95), (84.95, 19.25), (85.2, 19.45), (85.5, 19.7),
    (85.85, 19.8), (86.2, 19.92), (86.5, 20.1), (86.75, 20.35), (86.95, 20.7), (87.0, 21.05),
    (87.15, 21.4), (87.5, 21.6), (87.9, 21.75), (88.1, 21.6), (88.4, 21.6), (88.8, 21.55),
    (89.3, 21.7), (89.8, 21.85), (90.3, 21.9), (90.7, 22.1), (91.0, 22.4), (91.5, 22.5),
    (91.85, 22.25), (91.95, 21.5), (92.2, 21.0), (92.6, 20.5), (93.2, 19.9), (93.7, 19.3),
    (94.2, 18.5), (94.5, 17.5), (94.4, 16.0),
]
LAND = COAST + [(96.0, 15.0), (96.0, 26.0), (75.0, 26.0), (75.0, 11.5)]
AP_COAST = [p for p in COAST if 13.4 <= p[1] <= 19.0 and p[0] < 84.8]
OD_COAST = [p for p in COAST if 84.7 <= p[0] <= 87.5 and 18.9 <= p[1] <= 21.65]
AP_OD_BORDER = [(84.6, 19.1), (84.1, 18.95), (83.6, 18.75), (83.1, 18.45), (82.5, 18.05),
                (82.0, 17.85), (81.5, 17.75)]
AP_POLY = AP_COAST + AP_OD_BORDER + [
    (80.9, 17.25), (80.3, 16.85), (79.6, 16.6), (78.6, 16.1), (77.3, 15.9), (77.0, 15.4),
    (77.1, 14.5), (77.6, 13.9), (78.4, 13.3), (78.6, 12.7), (79.2, 13.0), (79.9, 13.4)]
OD_POLY = OD_COAST + [
    (87.25, 21.95), (86.8, 22.2), (86.0, 22.55), (85.0, 22.45), (84.3, 22.45), (83.6, 22.4),
    (83.3, 22.0), (82.5, 21.5), (82.4, 20.8), (82.0, 20.3), (82.4, 19.6), (81.85, 18.6)
] + AP_OD_BORDER[::-1]

CITIES = {
    "VISAKHAPATNAM": (83.30, 17.69),
    "BHIMAVARAM": (81.52, 16.54),
    "NARSAPUR": (81.70, 16.43),
    "KAKINADA": (82.24, 16.95),
    "MACHILIPATNAM": (81.14, 16.17),
    "CHENNAI": (80.27, 13.08),
    "BHUBANESWAR": (85.82, 20.30),
    "GOPALPUR": (84.92, 19.26),
    "PURI": (85.83, 19.81),
    "SRIKAKULAM": (83.90, 18.30),
}

# Illustrative storm track with IMD intensity classes (D -> VSCS -> weakening inland)
TRACK = [
    (87.6, 13.2, "D"), (86.4, 13.9, "DD"), (85.2, 14.6, "CS"), (84.0, 15.3, "SCS"),
    (82.9, 15.9, "VSCS"), (81.72, 16.36, "VSCS"), (81.2, 17.2, "SCS"), (80.8, 18.2, "CS"),
]
TRACK_T = [0.6, 2.0, 3.4, 4.8, 6.4, 8.0, 9.8, 11.3]   # local scene seconds at each node
LANDFALL_IDX = 5
IMD_RANGES = {"D": "31\u201349 KM/H", "DD": "50\u201361 KM/H", "CS": "62\u201388 KM/H",
              "SCS": "89\u2013117 KM/H", "VSCS": "118\u2013165 KM/H"}


def make_extent(lat0: float, lat1: float, lon_c: float, w: int = PW, h: int = PH):
    """Equirectangular extent whose lon span matches the panel aspect at mid-latitude."""
    coslat = math.cos(math.radians((lat0 + lat1) / 2))
    lon_span = (w / h) * (lat1 - lat0) / coslat
    return (lon_c - lon_span / 2, lon_c + lon_span / 2, lat0, lat1)


EXT_RADAR = make_extent(12.5, 22.5, 84.0)
EXT_EVAC = make_extent(13.6, 21.4, 83.0)


def geo2px(lon, lat, ext, w=PW, h=PH):
    lon0, lon1, lat0, lat1 = ext
    return ((lon - lon0) / (lon1 - lon0) * w, (lat1 - lat) / (lat1 - lat0) * h)


# --------------------------------------------------------------------------------------
# Fonts & drawing helpers
# --------------------------------------------------------------------------------------
FONT_CANDIDATES = {
    "black": ["Inter-Black.otf", "Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf"],
    "xbold": ["Inter-ExtraBold.otf", "InterDisplay-ExtraBold.otf", "DejaVuSans-Bold.ttf"],
    "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    "semi": ["Inter-SemiBold.otf", "DejaVuSans-Bold.ttf"],
    "reg": ["Inter-Medium.otf", "Inter-Regular.otf", "DejaVuSans.ttf"],
    "mono": ["JetBrainsMono-Bold.ttf", "DejaVuSansMono-Bold.ttf"],
}


@lru_cache(maxsize=1)
def _font_index() -> dict:
    idx = {}
    dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts",
            Path.home() / ".local/share/fonts", Path("/Library/Fonts"),
            Path("C:/Windows/Fonts"), Path(matplotlib.get_data_path()) / "fonts" / "ttf"]
    for d in dirs:
        if d.is_dir():
            for p in d.rglob("*"):
                if p.suffix.lower() in (".ttf", ".otf"):
                    idx.setdefault(p.name, p)
    return idx


@lru_cache(maxsize=256)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    idx = _font_index()
    for name in FONT_CANDIDATES[kind] + ["DejaVuSans-Bold.ttf"]:
        if name in idx:
            return ImageFont.truetype(str(idx[name]), size)
    return ImageFont.load_default(size)


def fit_font(text: str, kind: str, size: int, max_w: int, min_size: int = 18):
    while size > min_size:
        f = font(kind, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return font(kind, min_size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def rgba(c, a=255):
    return (c[0], c[1], c[2], int(clamp(a, 0, 255)))


def fade_alpha(img: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return img
    r, g, b, al = img.split()
    al = al.point(lambda v: int(v * a))
    return Image.merge("RGBA", (r, g, b, al))


def draw_text(d: ImageDraw.ImageDraw, xy, s, f, fill, anchor="la", stroke=0, stroke_fill=(0, 0, 0)):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke,
           stroke_fill=stroke_fill if stroke else None)


def glow_layer(size, draw_fn, radius=8):
    """Draw shapes on a transparent layer and return (blurred glow + sharp) composite."""
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(lay))
    g = lay.filter(ImageFilter.GaussianBlur(radius))
    g.alpha_composite(lay)
    return g


class BlendDraw:
    """ImageDraw that alpha-blends onto an RGBA image (plain ImageDraw *replaces* pixels,
    so translucent shapes would punch holes in the frame). Call commit() to apply."""

    def __init__(self, base: Image.Image):
        self.base = base
        self.ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.ov)

    def __getattr__(self, name):
        return getattr(self.d, name)

    def commit(self):
        self.base.alpha_composite(self.ov)
        self.ov = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.ov)


# --------------------------------------------------------------------------------------
# 1. Voiceover (edge-tts) + word-level VTT
# --------------------------------------------------------------------------------------
@dataclass
class Word:
    start: float
    end: float
    text: str


def _ssl_connector():
    """edge-tts uses aiohttp + certifi; honour corporate/proxy CA bundles when present."""
    import aiohttp
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        p = os.environ.get(var)
        if p and Path(p).is_file():
            return aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=p))
    return None


async def _tts(text: str, voice: str, rate: str, mp3: Path) -> list[Word]:
    import edge_tts
    kwargs = {"rate": rate, "boundary": "WordBoundary"}
    conn = _ssl_connector()
    if conn is not None:
        kwargs["connector"] = conn
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        kwargs["proxy"] = proxy
    comm = edge_tts.Communicate(text, voice, **kwargs)
    words: list[Word] = []
    with open(mp3, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7
                words.append(Word(s, s + chunk["duration"] / 1e7, chunk["text"]))
    return words


def align_punctuation(words: list[Word], script: str) -> list[Word]:
    """Recover punctuation/casing from the script tokens for nicer captions."""
    tokens = script.split()
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())  # noqa: E731
    j, out = 0, []
    for w in words:
        nw = norm(w.text)
        n_parts = max(1, len(w.text.split()))   # edge-tts may merge "135 km per hour"
        span = " ".join(tokens[j:j + n_parts])
        if n_parts > 1 and norm(span) == nw:
            out.append(Word(w.start, w.end, span))
            j += n_parts
            continue
        hit = next((k for k in range(j, min(j + 6, len(tokens))) if nw and norm(tokens[k]) == nw),
                   None)
        if hit is not None:
            out.append(Word(w.start, w.end, tokens[hit]))
            j = hit + 1
        else:
            out.append(Word(w.start, w.end, w.text))
            j += n_parts
    return out


def vtt_ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(words: list[Word], path: Path):
    lines = ["WEBVTT", "Kind: captions", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{vtt_ts(w.start)} --> {vtt_ts(w.end)}", w.text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def build_voiceover(lang: str, rate: str, out_mp3: Path, out_vtt: Path, build: Path,
                    reuse: bool) -> list[Word]:
    cfg = CONTENT[lang]
    words_json = build / f"words_{lang}.json"
    if reuse and out_mp3.exists() and words_json.exists():
        print(f"[tts] reusing {out_mp3.name}")
        words = align_punctuation([Word(**w) for w in json.loads(words_json.read_text())],
                                  cfg["script"])
        write_vtt(words, out_vtt)
        return words

    raw = build / f"voice_raw_{lang}.mp3"
    print(f"[tts] edge-tts {cfg['voice']} rate {rate} ...")
    for attempt in range(4):
        try:
            words = asyncio.run(_tts(cfg["script"], cfg["voice"], rate, raw))
            break
        except Exception as exc:  # network hiccups
            if attempt == 3:
                raise SystemExit(f"edge-tts failed: {exc}")
            wait = 2 ** (attempt + 1)
            print(f"[tts] retry in {wait}s ({exc})")
            time.sleep(wait)
    words = align_punctuation(words, cfg["script"])

    dur = ffprobe_duration(raw)
    max_len = DURATION - VOICE_OFFSET - VOICE_TAIL
    if dur > max_len:
        factor = dur / max_len
        print(f"[tts] narration {dur:.2f}s > {max_len:.2f}s -> atempo {factor:.3f}")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-filter:a",
                        f"atempo={factor:.5f}", "-c:a", "libmp3lame", "-b:a", "192k",
                        str(out_mp3)], check=True)
        words = [Word(w.start / factor, w.end / factor, w.text) for w in words]
    else:
        shutil.copyfile(raw, out_mp3)
    print(f"[tts] voiceover {ffprobe_duration(out_mp3):.2f}s, {len(words)} words")
    write_vtt(words, out_vtt)
    words_json.write_text(json.dumps([w.__dict__ for w in words], ensure_ascii=False, indent=1))
    return words


# --------------------------------------------------------------------------------------
# 2. Atmospheric weather drone (scipy) + mix
# --------------------------------------------------------------------------------------
def synth_drone(path: Path, dur: float, target_db: float, sr: int = 48000):
    try:
        from scipy import signal
        from scipy.io import wavfile
    except ImportError:  # ffmpeg lavfi fallback
        print("[drone] scipy unavailable -> ffmpeg lavfi drone")
        expr = ("aevalsrc='0.5*sin(2*PI*41.2*t)+0.35*sin(2*PI*55*t)+0.2*sin(2*PI*61.74*t)'"
                f":s={sr}:d={dur}")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", expr,
                        "-f", "lavfi", "-i", f"anoisesrc=c=brown:a=0.3:d={dur}:r={sr}",
                        "-filter_complex",
                        "[1]lowpass=f=180[n];[0][n]amix=2:normalize=0,"
                        f"afade=t=in:d=2,afade=t=out:st={dur - 2.5}:d=2.5,"
                        f"loudnorm=I={target_db}:TP=-6,aresample={sr}", "-ac", "2", str(path)],
                       check=True)
        return

    n = int(dur * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(1977)

    def norm(x):
        return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)

    swell = 0.62 + 0.38 * np.sin(2 * np.pi * 0.07 * t - 1.2)
    tones = (np.sin(2 * np.pi * 41.2 * t + 0.35 * np.sin(2 * np.pi * 0.11 * t))
             + 0.70 * np.sin(2 * np.pi * 55.0 * t + 0.2 * np.sin(2 * np.pi * 0.05 * t))
             + 0.42 * np.sin(2 * np.pi * 61.74 * t)          # minor-ish cluster = ominous
             + 0.22 * np.sin(2 * np.pi * 82.4 * t + 1.0))
    sos_low = signal.butter(4, 150, "low", fs=sr, output="sos")
    sos_wind = signal.butter(2, [260, 900], "band", fs=sr, output="sos")
    chans = []
    for ch in range(2):
        rumble = signal.sosfilt(sos_low, rng.standard_normal(n))
        wind = signal.sosfilt(sos_wind, rng.standard_normal(n))
        gust = (0.25 + 0.75 * np.sin(2 * np.pi * (0.043 + 0.006 * ch) * t + 1.3 + ch) ** 4)
        x = 1.0 * norm(tones) * swell + 0.85 * norm(rumble) + 0.22 * norm(wind) * gust
        chans.append(x)
    y = np.stack(chans, axis=1)
    fade_in, fade_out = int(2.0 * sr), int(2.5 * sr)
    env = np.ones(n)
    env[:fade_in] = np.linspace(0, 1, fade_in) ** 2
    env[-fade_out:] = np.linspace(1, 0, fade_out) ** 2
    y *= env[:, None]
    body = y[fade_in:-fade_out]
    rms = np.sqrt(np.mean(body ** 2))
    y *= (10 ** (target_db / 20)) / rms
    peak = np.max(np.abs(y))
    if peak > 0.89:
        y *= 0.89 / peak
    wavfile.write(str(path), sr, (y * 32767).astype(np.int16))
    print(f"[drone] {dur:.0f}s drone @ {target_db:.0f} dBFS RMS -> {path.name}")


def mix_audio(voice: Path, drone: Path, out: Path):
    delay = int(VOICE_OFFSET * 1000)
    fc = (f"[0:a]loudnorm=I=-15:TP=-2:LRA=11,aresample=48000,adelay={delay}:all=1,apad[v];"
          f"[1:a]aresample=48000[d];"
          f"[v][d]amix=inputs=2:normalize=0:duration=shortest,"
          f"alimiter=limit=0.94,atrim=0:{DURATION}[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(drone),
                    "-filter_complex", fc, "-map", "[a]", "-ac", "2", "-ar", "48000",
                    str(out)], check=True)
    print(f"[audio] mixed -> {out.name}")


# --------------------------------------------------------------------------------------
# 3. Optional B-roll from assets/
# --------------------------------------------------------------------------------------
GRADE = ("eq=contrast=1.45:brightness=-0.10:saturation=0.55,"
         "colorbalance=rs=-0.06:gs=0.01:bs=0.12:rm=-0.04:bm=0.07,"
         "vignette=angle=PI/3.3,vignette=angle=PI/4.5")


def build_broll(assets: Path, build: Path) -> Path | None:
    if not assets.is_dir():
        return None
    files = sorted(p for p in assets.iterdir()
                   if p.suffix.lower() in (".mp4", ".mov", ".jpg", ".jpeg", ".png"))
    if not files:
        return None
    seg = DURATION / len(files)
    parts = []
    for i, f in enumerate(files):
        out = build / f"broll_{i:02d}.mp4"
        if f.suffix.lower() in (".mp4", ".mov"):
            inp = ["-stream_loop", "-1", "-t", f"{seg:.3f}", "-i", str(f)]
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"fps={FPS},{GRADE},format=yuv420p")
        else:  # slow Ken Burns push on stills
            inp = ["-loop", "1", "-framerate", str(FPS), "-t", f"{seg:.3f}", "-i", str(f)]
            vf = (f"scale={int(W * 1.15)}:{int(H * 1.15)}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H}:x='(iw-ow)*t/{seg:.3f}':y='(ih-oh)*(0.5+0.4*sin(t/3))',"
                  f"{GRADE},format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-vf", vf, "-an",
                        "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        str(out)], check=True)
        parts.append(out)
    lst = build / "broll_list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    out = build / "broll.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out)], check=True)
    print(f"[broll] {len(files)} asset(s) graded -> {out.name}")
    return out


# --------------------------------------------------------------------------------------
# 4. Static layers (matplotlib basemaps, Pillow chrome)
# --------------------------------------------------------------------------------------
def cloud_noise(h, w, seed, scales=(6, 14, 30)):
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w))
    for i, s in enumerate(scales):
        acc += gaussian_filter(rng.standard_normal((h, w)), s) * (1.6 ** i)
    acc = (acc - acc.min()) / (np.ptp(acc) + 1e-9)
    return acc


def render_basemap(ext, style: str, ocean_alpha: float) -> Image.Image:
    lon0, lon1, lat0, lat1 = ext
    fig = plt.figure(figsize=(PW / 100, PH / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.axis("off")
    hexc = lambda c: "#%02x%02x%02x" % c  # noqa: E731
    ax.add_patch(Rectangle((lon0, lat0), lon1 - lon0, lat1 - lat0, color=hexc((3, 9, 24)),
                           alpha=ocean_alpha, zorder=0))
    if style == "radar":
        # synthetic IR satellite texture over the ocean
        cm = LinearSegmentedColormap.from_list("ir", [(0, 0, 0, 0), (0.55, 0.75, 0.85, 0.0),
                                                      (0.75, 0.88, 0.95, 0.18),
                                                      (0.95, 0.98, 1.0, 0.32)])
        tex = cloud_noise(200, 250, 11)
        ax.imshow(tex, extent=(lon0, lon1, lat0, lat1), cmap=cm, zorder=1, aspect="auto",
                  interpolation="bicubic")
        land_fc, land_alpha, coast = (22, 48, 70), 0.96, TEAL
    else:
        land_fc, land_alpha, coast = (30, 58, 92), 0.97, (150, 200, 235)
    ax.add_patch(MplPolygon(LAND, closed=True, fc=hexc(land_fc), alpha=land_alpha,
                            ec=hexc(coast), lw=2.2, zorder=2))
    if style == "evac":
        ax.add_patch(MplPolygon(AP_POLY, closed=True, fc=hexc((0, 150, 138)), alpha=0.5,
                                ec=hexc(TEAL), lw=2.0, zorder=3))
        ax.add_patch(MplPolygon(OD_POLY, closed=True, fc=hexc((40, 120, 170)), alpha=0.55,
                                ec=hexc((110, 200, 230)), lw=2.0, zorder=3))
        ax.add_patch(MplPolygon(AP_POLY, closed=True, fill=False, hatch="//",
                                ec=hexc((0, 160, 150)), lw=0, alpha=0.35, zorder=3))
    else:
        ax.add_patch(MplPolygon(AP_POLY, closed=True, fill=False, ec=hexc((0, 150, 140)),
                                lw=1.2, ls=(0, (3, 3)), zorder=3))
        ax.add_patch(MplPolygon(OD_POLY, closed=True, fill=False, ec=hexc((0, 150, 140)),
                                lw=1.2, ls=(0, (3, 3)), zorder=3))
    for lon in range(int(lon0) + 1, int(lon1) + 1):
        if lon % 2 == 0:
            ax.axvline(lon, color=hexc(TEAL), alpha=0.16, lw=1, ls=(0, (4, 6)), zorder=4)
    for lat in range(int(lat0) + 1, int(lat1) + 1):
        if lat % 2 == 0:
            ax.axhline(lat, color=hexc(TEAL), alpha=0.16, lw=1, ls=(0, (4, 6)), zorder=4)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, transparent=True)
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf).convert("RGBA")
    if img.size != (PW, PH):
        img = img.resize((PW, PH), Image.Resampling.LANCZOS)
    return img


def grid_labels(img: Image.Image, ext):
    d = BlendDraw(img)
    f = font("mono", 18)
    lon0, lon1, lat0, lat1 = ext
    for lon in range(int(lon0) + 1, int(lon1) + 1):
        if lon % 2 == 0:
            x, _ = geo2px(lon, lat0, ext)
            draw_text(d, (x + 4, PH - 26), f"{lon}\u00b0E", f, rgba(TEAL, 150))
    for lat in range(int(lat0) + 1, int(lat1) + 1):
        if lat % 2 == 0:
            _, y = geo2px(lon0, lat, ext)
            draw_text(d, (8, y - 22), f"{lat}\u00b0N", f, rgba(TEAL, 150))
    d.commit()


def cyclone_sprite(size=420, seed=5) -> Image.Image:
    """Satellite/radar-like spiral cloud mass with an eye, coloured as reflectivity."""
    from scipy.ndimage import gaussian_filter
    yy, xx = np.mgrid[0:size, 0:size]
    c = (size - 1) / 2
    x, y = (xx - c) / c, (yy - c) / c
    r = np.sqrt(x * x + y * y) + 1e-6
    th = np.arctan2(y, x)
    arms = (0.5 + 0.5 * np.cos(2 * (th + 2.6 * np.log(r)))) ** 2.2
    rng = np.random.default_rng(seed)
    noise = gaussian_filter(rng.standard_normal((size, size)), 5)
    noise = (noise - noise.min()) / np.ptp(noise)
    radial = np.exp(-((r / 0.62) ** 2))
    eyewall = np.exp(-((r - 0.12) / 0.06) ** 2)
    v = radial * (0.25 + 0.75 * arms) * (0.55 + 0.6 * noise) + 0.9 * eyewall
    v[r < 0.06] *= 0.1   # clear eye
    v *= np.clip((0.98 - r) / 0.35, 0, 1) ** 1.5   # soft circular falloff
    v = np.clip(v, 0, 1)
    cmap = LinearSegmentedColormap.from_list("refl", [
        (0.00, (0.0, 0.79, 0.72, 0.0)), (0.25, (0.0, 0.79, 0.72, 0.45)),
        (0.50, (0.85, 0.95, 1.00, 0.70)), (0.72, (1.0, 0.69, 0.0, 0.85)),
        (1.00, (1.0, 0.30, 0.10, 0.95))])
    arr = (cmap(v) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA").filter(ImageFilter.GaussianBlur(1.2))


def build_base(broll: bool) -> Image.Image:
    yy = np.linspace(0, 1, H)[:, None]
    mid = np.exp(-((yy - 0.42) / 0.38) ** 2)
    col = np.array(NAVY_DEEP)[None, None, :] * (1 - mid[..., None]) + \
        np.array((12, 30, 64))[None, None, :] * mid[..., None]
    col = np.repeat(col, W, axis=1)
    xx = np.linspace(-1, 1, W)[None, :]
    yv = np.linspace(-1, 1, H)[:, None]
    vig = 1 - 0.55 * np.clip((xx ** 2 + (yv * 0.8) ** 2) - 0.25, 0, 1)
    col = col * vig[..., None]
    a = np.full((H, W, 1), 150 if broll else 255, dtype=np.float64)
    if broll:  # darker edges = broadcast vignette on top of footage
        a = np.clip(a + 105 * (1 - vig[..., None]) * 2.2, 0, 255)
    img = Image.fromarray(np.concatenate([col, a], axis=2).astype(np.uint8), "RGBA")
    d = BlendDraw(img)
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=rgba(TEAL, 12))
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=rgba(TEAL, 12))
    d.commit()
    return img


def build_chrome(cfg) -> Image.Image:
    """Header, scene frame, telemetry chips, ticker bed, watermark (all static)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Alert stripe
    d.rectangle([0, 70, W, 122], fill=rgba(AMBER))
    for i in range(-2, 6):
        x = i * 34
        d.polygon([(x, 122), (x + 17, 70), (x + 34, 70), (x + 17, 122)], fill=rgba(NAVY_DEEP))
    tri_x = 200
    d.polygon([(tri_x, 112), (tri_x + 18, 80), (tri_x + 36, 112)], fill=rgba(NAVY_DEEP))
    draw_text(d, (tri_x + 18, 106), "!", font("black", 24), rgba(AMBER), anchor="ms")
    draw_text(d, (tri_x + 50, 96), cfg["alert"], font("black", 34), rgba(NAVY_DEEP), anchor="lm")
    # Header panel
    d.rectangle([0, 122, W, 256], fill=rgba(NAVY_PANEL, 238))
    d.rectangle([0, 252, W, 258], fill=rgba(TEAL))
    f1 = fit_font(cfg["header_top"], "bold", 40, W - 80)
    draw_text(d, (40, 134), cfg["header_top"], f1, rgba(AMBER))
    f2 = fit_font(cfg["header_main"], "black", 72, W - 80)
    draw_text(d, (40, 180), cfg["header_main"], f2, rgba(WHITE))
    # Panel frame + corner brackets
    d.rectangle([PX - 2, PY - 2, PX + PW + 1, PY + PH + 1], outline=rgba(NAVY_LINE, 255), width=2)
    L = 46
    for (cx, cy, sx, sy) in [(PX - 6, PY - 6, 1, 1), (PX + PW + 5, PY - 6, -1, 1),
                             (PX - 6, PY + PH + 5, 1, -1), (PX + PW + 5, PY + PH + 5, -1, -1)]:
        d.line([(cx, cy), (cx + sx * L, cy)], fill=rgba(AMBER), width=6)
        d.line([(cx, cy), (cx, cy + sy * L)], fill=rgba(AMBER), width=6)
    # Telemetry chips
    fchip = fit_font(max(cfg["chips"], key=len), "mono", 28, 300)
    x = 40
    gap = 18
    widths = [fchip.getlength(c) + 40 for c in cfg["chips"]]
    scale = min(1.0, (W - 80 - gap * 2) / sum(widths))
    for c, wdt in zip(cfg["chips"], widths):
        wdt *= scale
        d.rounded_rectangle([x, 1478, x + wdt, 1540], 10, fill=rgba(NAVY_PANEL, 235),
                            outline=rgba(TEAL, 200), width=2)
        draw_text(d, (x + wdt / 2, 1509), c, fchip, rgba(WHITE), anchor="mm")
        x += wdt + gap
    # Ticker bed
    d.rectangle([0, 1564, W, 1630], fill=rgba(NAVY_DEEP, 240))
    d.rectangle([0, 1564, W, 1567], fill=rgba(AMBER))
    d.rectangle([0, 1627, W, 1630], fill=rgba(TEAL, 180))
    # Watermark below ticker (lives under the Shorts UI, purely decorative)
    draw_text(d, (W / 2, 1700), cfg["watermark"], font("bold", 26), rgba(WHITE, 70), anchor="mm")
    return img


# --------------------------------------------------------------------------------------
# 5. Animated scene renderers
# --------------------------------------------------------------------------------------
def draw_icon(d: ImageDraw.ImageDraw, kind: str, cx, cy, s, col):
    c = rgba(col)
    if kind == "people":
        for dx, k in ((-0.55, 0.8), (0.55, 0.8), (0, 1.0)):
            x = cx + dx * s
            r = 0.22 * s * k
            d.ellipse([x - r, cy - 0.55 * s * k - r, x + r, cy - 0.55 * s * k + r], fill=c)
            d.rounded_rectangle([x - 0.36 * s * k, cy - 0.25 * s * k, x + 0.36 * s * k,
                                 cy + 0.55 * s], radius=int(0.2 * s), fill=c)
    elif kind == "medic":
        a, b = 0.22 * s, 0.7 * s
        d.rounded_rectangle([cx - b, cy - b, cx + b, cy + b], radius=int(0.25 * s),
                            outline=c, width=max(3, int(s * 0.1)))
        d.rectangle([cx - a, cy - b * 0.7, cx + a, cy + b * 0.7], fill=c)
        d.rectangle([cx - b * 0.7, cy - a, cx + b * 0.7, cy + a], fill=c)
    elif kind == "boat":
        d.polygon([(cx - 0.8 * s, cy + 0.2 * s), (cx + 0.8 * s, cy + 0.2 * s),
                   (cx + 0.55 * s, cy + 0.6 * s), (cx - 0.55 * s, cy + 0.6 * s)], fill=c)
        d.line([(cx, cy + 0.2 * s), (cx, cy - 0.75 * s)], fill=c, width=max(3, int(s * 0.08)))
        d.polygon([(cx + 0.06 * s, cy - 0.7 * s), (cx + 0.6 * s, cy + 0.1 * s),
                   (cx + 0.06 * s, cy + 0.1 * s)], fill=c)
        for k in range(3):
            y = cy + 0.78 * s + k * 0.0
            d.arc([cx - 0.9 * s + k * 0.6 * s, y - 0.12 * s, cx - 0.3 * s + k * 0.6 * s,
                   y + 0.12 * s], 0, 180, fill=c, width=3)
    elif kind == "shield":
        d.polygon([(cx, cy - 0.8 * s), (cx + 0.7 * s, cy - 0.5 * s), (cx + 0.6 * s, cy + 0.2 * s),
                   (cx, cy + 0.8 * s), (cx - 0.6 * s, cy + 0.2 * s), (cx - 0.7 * s, cy - 0.5 * s)],
                  outline=c, width=max(3, int(s * 0.1)))
        d.line([(cx - 0.3 * s, cy), (cx - 0.05 * s, cy + 0.28 * s), (cx + 0.35 * s, cy - 0.25 * s)],
               fill=c, width=max(4, int(s * 0.12)), joint="curve")
    elif kind == "house":
        d.polygon([(cx - s, cy), (cx, cy - s), (cx + s, cy)], fill=c)
        d.rectangle([cx - 0.7 * s, cy, cx + 0.7 * s, cy + 0.9 * s], fill=c)


def draw_pin(d, x, y, label, f, col, a=255, side="left", drop=1.0):
    y_off = (1 - ease_out(drop)) * -60
    y2 = y + y_off
    d.ellipse([x - 20, y2 - 52, x + 20, y2 - 12], fill=rgba(col, a))
    d.polygon([(x - 15, y2 - 24), (x + 15, y2 - 24), (x, y2)], fill=rgba(col, a))
    d.ellipse([x - 8, y2 - 40, x + 8, y2 - 24], fill=rgba(NAVY_DEEP, a))
    tw = f.getlength(label)
    if side == "left":
        bx0, bx1 = x - 30 - tw - 24, x - 30
    else:
        bx0, bx1 = x + 30, x + 30 + tw + 24
    d.rounded_rectangle([bx0, y2 - 60, bx1, y2 - 16], 8, fill=rgba(NAVY_DEEP, int(a * 0.92)),
                        outline=rgba(col, a), width=2)
    draw_text(d, ((bx0 + bx1) / 2, y2 - 38), label, f, rgba(WHITE, a), anchor="mm")


class Renderer:
    def __init__(self, lang: str, words: list[Word], broll: bool):
        self.lang = lang
        self.cfg = CONTENT[lang]
        self.words = words
        self.chunks = self._chunk_words(words)
        print("[gfx] building static layers ...")
        base = build_base(broll)
        base.alpha_composite(build_chrome(self.cfg))
        self.static = base
        oa = 0.72 if broll else 1.0
        self.map_radar = render_basemap(EXT_RADAR, "radar", oa)
        grid_labels(self.map_radar, EXT_RADAR)
        self._labels_radar(self.map_radar)
        self.map_evac = render_basemap(EXT_EVAC, "evac", oa)
        grid_labels(self.map_evac, EXT_EVAC)
        self._labels_evac(self.map_evac)
        self.sprite = cyclone_sprite()
        self.track_px = [geo2px(lo, la, EXT_RADAR) for lo, la, _ in TRACK]
        tf = font("bold", 34)
        tick = "   " + self.cfg["ticker"]
        tw = int(tf.getlength(tick)) + 2
        self.ticker = Image.new("RGBA", (tw, 60), (0, 0, 0, 0))
        draw_text(ImageDraw.Draw(self.ticker), (0, 30), tick, tf, rgba(WHITE), anchor="lm")
        self.ticker_w = tw

    # ---------------- static label passes ----------------
    def _labels_radar(self, img):
        d = BlendDraw(img)
        r = self.cfg["radar"]
        fs = font("semi", 22)
        for name in ("VISAKHAPATNAM", "BHUBANESWAR"):
            lo, la = CITIES[name]
            x, y = geo2px(lo, la, EXT_RADAR)
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=rgba(WHITE))
            draw_text(d, (x - 12, y), name.title(), fs, rgba(WHITE, 220), anchor="rm",
                      stroke=3, stroke_fill=rgba(NAVY_DEEP))
        x, y = geo2px(87.6, 17.6, EXT_RADAR)
        draw_text(d, (x, y), self.cfg["region"], font("bold", 34), rgba(TEAL, 150), anchor="mm")
        draw_text(d, (PW - 16, 18), r["station"], font("mono", 20), rgba(TEAL, 200), anchor="ra")
        draw_text(d, (PW - 16, 44), r["track"], font("mono", 18), rgba(GREY, 230), anchor="ra",
                  stroke=3, stroke_fill=rgba(NAVY_DEEP))
        d.commit()

    def _labels_evac(self, img):
        d = BlendDraw(img)
        e = self.cfg["evac"]["states"]
        fb = font("black", 34)
        for key, (lo, la), col in (("AP", (79.3, 15.0), WHITE), ("OD", (84.6, 20.9), WHITE),
                                   ("TG", (79.0, 17.45), GREY), ("CG", (81.0, 20.4), GREY),
                                   ("BOB", (86.1, 16.3), TEAL)):
            x, y = geo2px(lo, la, EXT_EVAC)
            big = key in ("AP", "OD")
            f = fb if big else font("bold", 36 if key == "BOB" else 24)
            fill = rgba(col, 230 if big else 160)
            d.multiline_text((x, y), e[key], font=f, fill=fill, anchor="mm", align="center",
                             spacing=2)
        fs = font("semi", 21)
        for name in ("KAKINADA", "SRIKAKULAM", "GOPALPUR", "PURI", "BHUBANESWAR"):
            lo, la = CITIES[name]
            x, y = geo2px(lo, la, EXT_EVAC)
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=rgba(WHITE, 220))
            anchor, dx = ("lm", 10) if name in ("SRIKAKULAM", "GOPALPUR", "PURI", "KAKINADA") \
                else ("rm", -10)
            draw_text(d, (x + dx, y), name.title(), fs, rgba(WHITE, 200), anchor=anchor,
                      stroke=3, stroke_fill=rgba(NAVY_DEEP))
        draw_text(d, (PW - 14, 14), self.cfg["evac"]["note"], font("mono", 16),
                  rgba(GREY, 190), anchor="ra")
        d.commit()

    # ---------------- captions ----------------
    @staticmethod
    def _chunk_words(words: list[Word]):
        chunks, cur = [], []
        for i, w in enumerate(words):
            cur.append(w)
            txt = " ".join(x.text for x in cur)
            nxt = words[i + 1] if i + 1 < len(words) else None
            gap = (nxt.start - w.end) if nxt else 9
            if (len(cur) >= 4 or len(txt) >= 18 or w.text[-1:] in ".,;:!?" or gap > 0.32
                    or nxt is None):
                chunks.append(cur)
                cur = []
        out = []
        for k, c in enumerate(chunks):
            start = c[0].start
            nxt_start = chunks[k + 1][0].start if k + 1 < len(chunks) else None
            end = c[-1].end + 0.35
            if nxt_start is not None:
                end = min(nxt_start, end) if nxt_start - c[-1].end > 0.6 else nxt_start
            out.append((start, end, c))
        return out

    def draw_caption(self, frame: Image.Image, t: float):
        tv = t - VOICE_OFFSET
        active = None
        for s, e, c in self.chunks:
            if s - 0.02 <= tv < e:
                active = (s, e, c)
                break
        if not active:
            return
        s, e, c = active
        tokens = [w.text.upper() for w in c]
        f = font("black", 80)
        space = f.getlength(" ")
        total = sum(f.getlength(tk) for tk in tokens) + space * (len(tokens) - 1)
        max_w = 940
        lines = [list(range(len(tokens)))]
        if total > max_w:  # balance into two lines
            best = None
            for split in range(1, len(tokens)):
                a = sum(f.getlength(tk) for tk in tokens[:split]) + space * (split - 1)
                b = sum(f.getlength(tk) for tk in tokens[split:]) + space * (len(tokens) - split - 1)
                if best is None or max(a, b) < best[0]:
                    best = (max(a, b), split)
            if best:
                lines = [list(range(best[1])), list(range(best[1], len(tokens)))]
                if best[0] > max_w:
                    f = font("black", int(80 * max_w / best[0]))
                    space = f.getlength(" ")
            else:
                f = font("black", int(80 * max_w / total))
                space = f.getlength(" ")
        lh = int(f.size * 1.12)
        block_h = lh * len(lines)
        widths = [sum(f.getlength(tokens[i]) for i in ln) + space * (len(ln) - 1) for ln in lines]
        bw = max(widths) + 64
        bh = block_h + 40
        pop = ease_out((tv - s) / 0.14)
        lay = Image.new("RGBA", (int(bw) + 20, int(bh) + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.rounded_rectangle([10, 10, 10 + bw, 10 + bh], 18, fill=(2, 6, 16, 205))
        d.rectangle([10, 10 + 8, 18, 10 + bh - 8], fill=rgba(AMBER))
        y = 10 + 20 + lh / 2
        for ln, lw in zip(lines, widths):
            x = 10 + (bw - lw) / 2
            for i in ln:
                w = c[i]
                spoken = w.start - 0.02 <= tv
                current = w.start - 0.02 <= tv < max(w.end, w.start + 0.12)
                col = AMBER if current else (WHITE if spoken else (200, 210, 225))
                draw_text(d, (x, y), tokens[i], f, rgba(col), anchor="lm", stroke=4,
                          stroke_fill=(0, 0, 0))
                x += f.getlength(tokens[i]) + space
            y += lh
        sc = 0.88 + 0.12 * pop
        if sc < 0.999:
            lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))),
                             Image.Resampling.BILINEAR)
        lay = fade_alpha(lay, clamp((tv - s) / 0.08 + 0.3))
        frame.alpha_composite(lay, (int(W / 2 - lay.width / 2), int(CAPTION_CY - lay.height / 2)))

    # ---------------- per-frame chrome ----------------
    def draw_dynamic_chrome(self, frame: Image.Image, t: float, scene: int, a_scene: float):
        d = BlendDraw(frame)
        # LIVE badge
        live_f = font("black", 28)
        lw = live_f.getlength(self.cfg["live"]) + 58
        x1 = W - 28
        x0 = x1 - lw
        d.rounded_rectangle([x0, 78, x1, 114], 8, fill=rgba(ALERT_RED))
        blink = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(t * 2 * math.pi * 0.9))
        d.ellipse([x0 + 14, 88, x0 + 30, 104], fill=rgba(WHITE, 255 * blink))
        draw_text(d, (x0 + 40, 96), self.cfg["live"], live_f, rgba(WHITE), anchor="lm")
        # Scene kicker + title
        lay = Image.new("RGBA", (W, 140), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        kf = font("mono", 26)
        k = self.cfg["scene_kickers"][scene]
        kw = kf.getlength(k) + 32
        ld.rounded_rectangle([40, 12, 40 + kw, 52], 8, fill=rgba(TEAL))
        draw_text(ld, (56, 32), k, kf, rgba(NAVY_DEEP), anchor="lm")
        prog_w = (W - 80 - kw - 24)
        ld.rounded_rectangle([40 + kw + 24, 28, W - 40, 36], 4, fill=rgba(NAVY_LINE))
        s0, s1 = SCENES[scene]
        p = clamp((t - s0) / (s1 - s0))
        ld.rounded_rectangle([40 + kw + 24, 28, 40 + kw + 24 + max(8, prog_w * p), 36], 4,
                             fill=rgba(AMBER))
        title = self.cfg["scene_titles"][scene]
        tf = fit_font(title, "black", 60, W - 80)
        draw_text(ld, (40, 98), title, tf, rgba(WHITE), anchor="lm")
        slide = int((1 - a_scene) * 24)
        frame.alpha_composite(fade_alpha(lay, a_scene), (0, 262 + slide))
        # Ticker
        label_w = 170
        off = int((t * 150) % self.ticker_w)
        crop = self.ticker.crop((off, 0, off + W - label_w, 60))
        if off + W - label_w > self.ticker_w:  # wrap
            seam = Image.new("RGBA", (W - label_w, 60), (0, 0, 0, 0))
            seam.paste(self.ticker.crop((off, 0, self.ticker_w, 60)), (0, 0))
            seam.paste(self.ticker.crop((0, 0, W - label_w - (self.ticker_w - off), 60)),
                       (self.ticker_w - off, 0))
            crop = seam
        frame.alpha_composite(crop, (label_w, 1567))
        d.rectangle([0, 1568, label_w - 10, 1626], fill=rgba(AMBER))
        d.polygon([(label_w - 10, 1568), (label_w + 8, 1597), (label_w - 10, 1626)],
                  fill=rgba(AMBER))
        draw_text(d, ((label_w - 10) / 2, 1597), "ALERT" if self.lang == "en" else "ALERTA",
                  font("black", 30), rgba(NAVY_DEEP), anchor="mm")
        d.commit()

    # ---------------- Scene 1: radar track ----------------
    def scene_radar(self, lt: float) -> Image.Image:
        img = self.map_radar.copy()
        r = self.cfg["radar"]
        # Doppler radar sweep at Visakhapatnam
        rx, ry = geo2px(*CITIES["VISAKHAPATNAM"], EXT_RADAR)
        km = PH / (EXT_RADAR[3] - EXT_RADAR[2]) / 111.0
        sweep = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sweep)
        R = 300 * km
        for rr in (100, 200, 300):
            q = rr * km
            sd.ellipse([rx - q, ry - q, rx + q, ry + q], outline=rgba(TEAL, 70), width=1)
        ang = (lt * 110) % 360
        for k in range(28):
            sd.pieslice([rx - R, ry - R, rx + R, ry + R], ang - k * 2.2 - 2.2, ang - k * 2.2,
                        fill=rgba(TEAL, 70 * (1 - k / 28) ** 1.6))
        ex, ey = rx + R * math.cos(math.radians(ang)), ry + R * math.sin(math.radians(ang))
        sd.line([(rx, ry), (ex, ey)], fill=rgba(TEAL, 200), width=2)
        img.alpha_composite(sweep)

        # Track progress
        nodes = self.track_px
        tt = TRACK_T
        if lt <= tt[0]:
            seg, u = 0, 0.0
        elif lt >= tt[-1]:
            seg, u = len(nodes) - 2, 1.0
        else:
            seg = max(i for i in range(len(tt) - 1) if tt[i] <= lt)
            u = ease_in_out((lt - tt[seg]) / (tt[seg + 1] - tt[seg]))
        cx = nodes[seg][0] + (nodes[seg + 1][0] - nodes[seg][0]) * u
        cy = nodes[seg][1] + (nodes[seg + 1][1] - nodes[seg][1]) * u
        cur_cat = TRACK[seg + (1 if u >= 0.5 else 0)][2]
        passed = [p for p, ti in zip(nodes, tt) if ti <= lt]

        # dashed full (illustrative) path
        d = BlendDraw(img)
        for i in range(len(nodes) - 1):
            (x0, y0), (x1, y1) = nodes[i], nodes[i + 1]
            n = 10
            for k in range(0, n, 2):
                a0, a1 = k / n, (k + 1) / n
                d.line([(x0 + (x1 - x0) * a0, y0 + (y1 - y0) * a0),
                        (x0 + (x1 - x0) * a1, y0 + (y1 - y0) * a1)], fill=rgba(WHITE, 90), width=3)
        d.commit()
        path = passed + [(cx, cy)]
        if len(path) >= 2:
            img.alpha_composite(glow_layer(img.size, lambda g: g.line(
                path, fill=rgba(AMBER, 255), width=6, joint="curve"), radius=6))
        # intensity markers
        d = BlendDraw(img)
        mf = font("black", 18)
        for (x, y), (lo, la, cat), ti in zip(nodes, TRACK, tt):
            on = lt >= ti
            col = CAT_COLORS[cat]
            rad = 22 if cat == "VSCS" else 19
            d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=rgba(NAVY_DEEP, 230 if on else 120),
                      outline=rgba(col, 255 if on else 110), width=4)
            draw_text(d, (x, y + 1), cat, mf if len(cat) < 4 else font("black", 14),
                      rgba(col, 255 if on else 120), anchor="mm")

        d.commit()
        # cyclone sprite (grows with intensity, decays inland)
        inten = {"D": 0.45, "DD": 0.55, "CS": 0.7, "SCS": 0.85, "VSCS": 1.0}[cur_cat]
        if lt > tt[LANDFALL_IDX]:
            inten *= 1 - 0.35 * clamp((lt - tt[LANDFALL_IDX]) / 3.0)
        appear = ease_out(lt / 0.8)
        size = int(self.sprite.width * (0.5 + 0.55 * inten) * (0.6 + 0.4 * appear))
        spr = self.sprite.rotate(lt * 38, resample=Image.Resampling.BILINEAR)  # anticlockwise (NH)
        spr = spr.resize((size, size), Image.Resampling.BILINEAR)
        spr = fade_alpha(spr, 0.88 * appear)
        img.alpha_composite(spr, (int(cx - size / 2), int(cy - size / 2)))
        d = BlendDraw(img)
        # storm symbol at centre
        for k in range(2):
            a0 = lt * 220 + k * 180
            d.arc([cx - 18, cy - 18, cx + 18, cy + 18], a0, a0 + 110, fill=rgba(WHITE), width=5)
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=rgba(WHITE))

        # landfall flash
        lf = tt[LANDFALL_IDX]
        if lt >= lf - 0.1:
            lx, ly = nodes[LANDFALL_IDX]
            for k in range(3):
                ph = ((lt - lf) * 0.9 + k / 3) % 1.0
                q = 20 + ph * 90
                d.ellipse([lx - q, ly - q, lx + q, ly + q], outline=rgba(ALERT_RED, 220 * (1 - ph)),
                          width=4)
            d.commit()
            a = ease_out((lt - lf) / 0.4)
            bx0, by0 = lx - 330, ly + 64
            box = Image.new("RGBA", img.size, (0, 0, 0, 0))
            bd = ImageDraw.Draw(box)
            bd.rounded_rectangle([bx0, by0, bx0 + 410, by0 + 92], 10, fill=rgba(ALERT_RED, 235))
            draw_text(bd, (bx0 + 18, by0 + 28), r["landfall"] + " \u00b7 28 OCT 2026",
                      fit_font(r["landfall"] + " \u00b7 28 OCT 2026", "black", 28, 380), rgba(WHITE),
                      anchor="lm")
            draw_text(bd, (bx0 + 18, by0 + 66), r["landfall_sub"],
                      fit_font(r["landfall_sub"], "bold", 23, 380), rgba(WHITE), anchor="lm")
            bd.line([(lx - 6, ly + 22), (bx0 + 300, by0)], fill=rgba(ALERT_RED), width=3)
            img.alpha_composite(fade_alpha(box, a))

        # telemetry box (top-left)
        d.commit()
        d = BlendDraw(img)
        col = CAT_COLORS[cur_cat]
        d.rounded_rectangle([16, 16, 470, 196], 12, fill=rgba(NAVY_DEEP, 225),
                            outline=rgba(col, 255), width=3)
        draw_text(d, (34, 34), r["imd"], font("mono", 20), rgba(GREY))
        name = r["names"][cur_cat]
        draw_text(d, (34, 62), name, fit_font(name, "black", 32, 420), rgba(col))
        if lt >= lf:
            draw_text(d, (34, 112), r["observed"], font("mono", 20), rgba(GREY))
            draw_text(d, (34, 140), r["observed_val"], fit_font(r["observed_val"], "black", 30, 420),
                      rgba(WHITE))
        else:
            draw_text(d, (34, 112), r["range"], font("mono", 20), rgba(GREY))
            draw_text(d, (34, 140), IMD_RANGES[cur_cat], font("black", 32), rgba(WHITE))
        if lt > tt[LANDFALL_IDX] + 1.5:
            draw_text(d, (34, 214), "\u25bc " + r["weakening"], font("bold", 24), rgba(TEAL),
                      stroke=3, stroke_fill=rgba(NAVY_DEEP))
        # category legend
        lx = 16
        ly = PH - 78
        cats = list(CAT_COLORS)
        d.rounded_rectangle([lx, ly, lx + 128 * len(cats) - 8 + 0, ly + 36], 8,
                            fill=rgba(NAVY_DEEP, 200))
        for i, cat in enumerate(cats):
            x = lx + 10 + i * 128
            on = cat == cur_cat
            d.rounded_rectangle([x, ly + 6, x + 112, ly + 30], 6,
                                fill=rgba(CAT_COLORS[cat], 255 if on else 70))
            draw_text(d, (x + 56, ly + 18), cat, font("black", 18),
                      rgba(NAVY_DEEP if on else WHITE), anchor="mm")
        d.commit()
        return img

    # ---------------- Scene 2: evacuation map ----------------
    def scene_evac(self, lt: float) -> Image.Image:
        img = self.map_evac.copy()
        e = self.cfg["evac"]
        zone_ap = [geo2px(lo, la, EXT_EVAC) for lo, la in AP_COAST if la >= 15.6]
        zone_od = [geo2px(lo, la, EXT_EVAC) for lo, la in OD_COAST if lo <= 85.9]
        grow = ease_out((lt - 0.3) / 2.5)
        pulse = 0.5 + 0.5 * math.sin(lt * 2 * math.pi * 0.8)

        def partial(pts, frac):
            if frac <= 0:
                return []
            n = max(2, int(len(pts) * frac + 0.999))
            return pts[:n]

        def zones(g):
            for pts, delay in ((zone_ap, 0.0), (zone_od, 0.25)):
                seg = partial(pts, clamp(grow * 1.2 - delay))
                if len(seg) >= 2:
                    g.line(seg, fill=rgba(AMBER, 70 + 60 * pulse), width=46, joint="curve")
                    g.line(seg, fill=rgba(AMBER_HOT, 230), width=7, joint="curve")
        img.alpha_composite(glow_layer(img.size, zones, radius=10))
        d = BlendDraw(img)
        # shelter icons popping along the coast
        allpts = zone_ap[::2] + zone_od[::2]
        for i, (x, y) in enumerate(allpts):
            a = ease_out((lt - 1.4 - i * 0.18) / 0.3)
            if a <= 0:
                continue
            ix, iy = x - 30, y - 30   # inland (NW) of the coastline
            draw_icon(d, "house", ix, iy, 11 * (0.6 + 0.4 * a), WHITE)
        # landfall marker near Narsapur
        nx, ny = geo2px(*CITIES["NARSAPUR"], EXT_EVAC)
        for k in range(2):
            ph = (lt * 0.8 + k / 2) % 1.0
            q = 14 + ph * 60
            d.ellipse([nx - q, ny - q, nx + q, ny + q], outline=rgba(ALERT_RED, 230 * (1 - ph)), width=4)
        d.line([(nx - 12, ny - 12), (nx + 12, ny + 12)], fill=rgba(ALERT_RED), width=5)
        d.line([(nx - 12, ny + 12), (nx + 12, ny - 12)], fill=rgba(ALERT_RED), width=5)
        # pins
        pf = font("black", 24)
        vx, vy = geo2px(*CITIES["VISAKHAPATNAM"], EXT_EVAC)
        bx, by = geo2px(*CITIES["BHIMAVARAM"], EXT_EVAC)
        pa = ease_out((lt - 0.9) / 0.5)
        if pa > 0:
            draw_pin(d, vx, vy, "VISAKHAPATNAM", pf, AMBER, int(255 * clamp(pa * 2)), "left", pa)
        pb = ease_out((lt - 1.5) / 0.5)
        if pb > 0:
            draw_pin(d, bx, by, "BHIMAVARAM", pf, ALERT_RED, int(255 * clamp(pb * 2)), "left", pb)
            tag = e["landfall"]
            tf_ = font("black", 20)
            tw_ = tf_.getlength(tag) + 24
            d.rounded_rectangle([nx + 26, ny + 22, nx + 26 + tw_, ny + 54], 8,
                                fill=rgba(ALERT_RED, int(235 * clamp(pb * 2))))
            draw_text(d, (nx + 26 + tw_ / 2, ny + 38), tag, tf_, rgba(WHITE, int(255 * clamp(pb * 2))),
                      anchor="mm")
        # counter box
        cnt_p = ease_out((lt - 0.4) / 4.5)
        val = int(round(100000 * cnt_p / 500.0) * 500)
        d.rounded_rectangle([16, 16, 520, 176], 12, fill=rgba(NAVY_DEEP, 230),
                            outline=rgba(AMBER), width=3)
        num = thousands(val, self.lang) + ("+" if cnt_p > 0.999 else "")
        draw_text(d, (36, 26), num, font("black", 82), rgba(AMBER))
        draw_text(d, (38, 128), e["counter"], fit_font(e["counter"], "bold", 30, 460), rgba(WHITE))
        # legend
        ly = 196
        d.rounded_rectangle([16, ly, 520, ly + 96], 10, fill=rgba(NAVY_DEEP, 200))
        d.rounded_rectangle([32, ly + 18, 76, ly + 36], 4, fill=rgba(AMBER_HOT))
        draw_text(d, (90, ly + 27), e["zone"], fit_font(e["zone"], "semi", 22, 410), rgba(WHITE),
                  anchor="lm")
        draw_icon(d, "house", 54, ly + 64, 12, WHITE)
        draw_text(d, (90, ly + 70), e["shelters"], fit_font(e["shelters"], "semi", 22, 410),
                  rgba(WHITE), anchor="lm")
        d.commit()
        return img

    # ---------------- Scene 3: mobilization metrics ----------------
    def scene_metrics(self, lt: float) -> Image.Image:
        img = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
        d = BlendDraw(img)
        d.rectangle([0, 0, PW, PH], fill=rgba(NAVY_DEEP, 120))
        draw_text(d, (24, 40), self.cfg["metrics_title"], font("mono", 28), rgba(TEAL), anchor="lm")
        blink = 0.5 + 0.5 * math.cos(lt * 2 * math.pi * 1.1)
        d.ellipse([PW - 44, 30, PW - 24, 50], fill=rgba(ALERT_RED, 255 * (0.4 + 0.6 * blink)))
        d.commit()
        cw, ch = 470, 340
        pos = [(20, 80), (510, 80), (20, 440), (510, 440)]
        accents = [AMBER, TEAL, AMBER, TEAL]
        for i, ((icon, target, fmt, label), (x, y), acc) in enumerate(
                zip(self.cfg["metrics"], pos, accents)):
            st = 0.3 + i * 0.85
            a = ease_out((lt - st) / 0.5)
            if a <= 0:
                continue
            card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle([0, 0, cw - 1, ch - 1], 18, fill=rgba(NAVY_PANEL, 238),
                                 outline=rgba(NAVY_LINE), width=2)
            cd.rounded_rectangle([0, 0, cw - 1, 12], 6, fill=rgba(acc))
            draw_icon(cd, icon, 70, 90, 42, acc)
            if target is None:
                txt = fmt
                pill = self.cfg["active"]
                pw_ = font("black", 24).getlength(pill) + 50
                cd.rounded_rectangle([cw - pw_ - 24, 56, cw - 24, 96], 20,
                                     fill=rgba(TEAL, 80 + 175 * blink))
                draw_text(cd, (cw - 24 - pw_ / 2, 76), pill, font("black", 24), rgba(NAVY_DEEP),
                          anchor="mm")
            else:
                p = ease_out((lt - st - 0.2) / 1.6)
                v = int(target * p)
                step = 100 if target >= 10000 else 10
                v = int(round(v / step) * step)
                txt = fmt.format(v).replace(",", ".") if self.lang == "pt" else fmt.format(v)
                if p < 0.999:
                    txt = txt.replace("+", "")
            draw_text(cd, (28, 210), txt, fit_font(txt, "black", 104, cw - 56), rgba(WHITE),
                      anchor="ls")
            lf_ = fit_font(max(label.split("\n"), key=len), "bold", 34, cw - 60)
            cd.multiline_text((30, 236), label, font=lf_, fill=rgba(acc), spacing=4)
            card = fade_alpha(card, a)
            img.alpha_composite(card, (x, int(y + (1 - a) * 50)))
        return img

    # ---------------- Scene 4: aftermath & outro ----------------
    def scene_after(self, lt: float, total: float) -> Image.Image:
        img = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, PW, PH], fill=rgba(NAVY_DEEP, 120))
        draw_text(d, (24, 40), self.cfg["after_title"], font("mono", 28), rgba(TEAL), anchor="lm")
        row_h, y0 = 100, 76
        for i, (title, sub, status, col, progress) in enumerate(self.cfg["after_rows"]):
            st = 0.2 + i * 0.55
            a = ease_out((lt - st) / 0.45)
            if a <= 0:
                continue
            row = Image.new("RGBA", (PW - 32, row_h - 10), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            rw, rh = row.size
            rd.rounded_rectangle([0, 0, rw - 1, rh - 1], 12, fill=rgba(NAVY_PANEL, 236))
            rd.rounded_rectangle([0, 0, 10, rh - 1], 5, fill=rgba(col))
            draw_text(rd, (30, 28), title, fit_font(title, "black", 32, 560), rgba(WHITE), anchor="lm")
            draw_text(rd, (30, 64), sub, fit_font(sub, "reg", 25, 600), rgba(GREY), anchor="lm")
            pf = fit_font(status, "black", 22, 200)
            pw_ = pf.getlength(status) + 36
            rd.rounded_rectangle([rw - pw_ - 20, 14, rw - 20, 46], 16, fill=rgba(col))
            draw_text(rd, (rw - 20 - pw_ / 2, 30), status, pf, rgba(NAVY_DEEP), anchor="mm")
            if progress:  # indeterminate "in progress" stripes - no invented percentages
                bx0, bx1, by0, by1 = rw - 240, rw - 20, 58, 72
                rd.rounded_rectangle([bx0, by0, bx1, by1], 7, fill=rgba(NAVY_LINE))
                bar = Image.new("RGBA", (bx1 - bx0, by1 - by0), (0, 0, 0, 0))
                bd = ImageDraw.Draw(bar)
                off = (lt * 60) % 28
                for k in range(-2, 12):
                    xx = k * 28 + off
                    bd.polygon([(xx, by1 - by0), (xx + 14, 0), (xx + 28, 0), (xx + 14, by1 - by0)],
                               fill=rgba(col, 230))
                mask = Image.new("L", bar.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, bar.width - 1, bar.height - 1], 7,
                                                       fill=255)
                row.paste(bar, (bx0, by0), mask)
            row = fade_alpha(row, a)
            img.alpha_composite(row, (16 + int((1 - a) * 60), y0 + i * row_h))
        # CTA card
        cta_t = 5.4
        a = ease_out((lt - cta_t) / 0.6)
        if a > 0:
            pulse = 0.5 + 0.5 * math.sin((lt - cta_t) * 2 * math.pi * 0.9)
            cy0 = 590
            card = Image.new("RGBA", (PW - 32, 190), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cw_, ch_ = card.size
            cd.rounded_rectangle([0, 0, cw_ - 1, ch_ - 1], 20, fill=rgba(AMBER, 245))
            cd.rounded_rectangle([6, 6, cw_ - 7, ch_ - 7], 16, outline=rgba(NAVY_DEEP, 120 + 120 * pulse),
                                 width=4)
            # bell icon
            bx, by = 92, 95
            cd.pieslice([bx - 42, by - 52, bx + 42, by + 32], 180, 360, fill=rgba(NAVY_DEEP))
            cd.rectangle([bx - 42, by - 10, bx + 42, by + 22], fill=rgba(NAVY_DEEP))
            cd.polygon([(bx - 54, by + 32), (bx + 54, by + 32), (bx + 42, by + 14), (bx - 42, by + 14)],
                       fill=rgba(NAVY_DEEP))
            cd.ellipse([bx - 12, by + 30, bx + 12, by + 52], fill=rgba(NAVY_DEEP))
            ring = int(10 * math.sin(lt * 14) * pulse)
            cd.arc([bx - 70 + ring, by - 70, bx + 70 + ring, by + 70], 300, 340, fill=rgba(NAVY_DEEP),
                   width=6)
            draw_text(cd, (180, 72), self.cfg["cta_1"], fit_font(self.cfg["cta_1"], "black", 58, cw_ - 210),
                      rgba(NAVY_DEEP), anchor="lm")
            draw_text(cd, (182, 134), self.cfg["cta_2"], fit_font(self.cfg["cta_2"], "bold", 40, cw_ - 210),
                      rgba(NAVY_DEEP), anchor="lm")
            sc = 0.92 + 0.08 * a
            card = card.resize((int(cw_ * sc), int(ch_ * sc)), Image.Resampling.BILINEAR)
            card = fade_alpha(card, a)
            img.alpha_composite(card, (int(PW / 2 - card.width / 2), int(cy0 + 95 - card.height / 2)))
        return img

    # ---------------- frame ----------------
    def frame(self, i: int) -> Image.Image:
        t = i / FPS
        scene = next(k for k, (s0, s1) in enumerate(SCENES) if s0 <= t < s1 or k == len(SCENES) - 1)
        s0, s1 = SCENES[scene]
        lt = t - s0
        a_in = ease_out(lt / 0.45)
        a_out = 1.0 if scene == len(SCENES) - 1 else ease_out((s1 - t) / 0.3)
        a_scene = min(a_in, a_out)
        frame = self.static.copy()
        if scene == 0:
            panel = self.scene_radar(lt)
        elif scene == 1:
            panel = self.scene_evac(lt)
        elif scene == 2:
            panel = self.scene_metrics(lt)
        else:
            panel = self.scene_after(lt, s1 - s0)
        frame.alpha_composite(fade_alpha(panel, a_scene), (PX, PY))
        # amber wipe bar on scene change
        if lt < 0.45 and scene > 0:
            d = BlendDraw(frame)
            y = PY + int(ease_in_out(lt / 0.45) * PH)
            d.rectangle([PX, y - 4, PX + PW, y + 4], fill=rgba(AMBER, 230))
            d.commit()
        self.draw_dynamic_chrome(frame, t, scene, a_scene)
        self.draw_caption(frame, t)
        return frame


# --------------------------------------------------------------------------------------
# 6. Encode
# --------------------------------------------------------------------------------------
def render_video(renderer: Renderer, audio: Path, broll: Path | None, out: Path,
                 frames: int = N_FRAMES):
    if broll:
        bg = ["-stream_loop", "-1", "-i", str(broll)]
    else:
        bg = ["-f", "lavfi", "-i", f"color=c=0x040A1A:s={W}x{H}:r={FPS}:d={DURATION}"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *bg,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio),
           "-filter_complex",
           f"[0:v]fps={FPS},scale={W}:{H},setsar=1[bg];"
           f"[bg][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[v]",
           "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-profile:v", "high", "-r", str(FPS), "-g", str(FPS * 2),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{frames / FPS:.3f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    try:
        for i in range(frames):
            proc.stdin.write(renderer.frame(i).tobytes())
            if i % 150 == 0 or i == frames - 1:
                el = time.time() - t0
                print(f"[render] frame {i + 1}/{frames}  {el:5.1f}s  "
                      f"({(i + 1) / max(el, 1e-6):.1f} fps)", flush=True)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"ffmpeg exited with {rc}")


def verify(out: Path, expect_duration: float = DURATION) -> dict:
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,"
                          "sample_rate,channels:format=duration,size", "-of", "json", str(out)],
                         capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    dur = float(info["format"]["duration"])
    checks = {
        "resolution 1080x1920": (v["width"], v["height"]) == (W, H),
        "30 fps": v["r_frame_rate"] in ("30/1", "30000/1000"),
        "h264 yuv420p": v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p",
        "aac audio": a["codec_name"] == "aac",
        f"duration ~{expect_duration:.0f}s": abs(dur - expect_duration) < 0.25,
    }
    print(f"[verify] {out.name}: {v['width']}x{v['height']} @ {v['r_frame_rate']} "
          f"{v['codec_name']}/{v['pix_fmt']}, audio {a['codec_name']} {a['sample_rate']}Hz "
          f"{a['channels']}ch, {dur:.2f}s, {int(info['format']['size']) / 1e6:.1f} MB")
    for k, ok in checks.items():
        print(f"   [{'OK' if ok else 'FAIL'}] {k}")
    if not all(checks.values()):
        raise SystemExit("verification failed")
    return info


# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Cyclone Arnab India - YouTube Short generator")
    ap.add_argument("--lang", choices=sorted(CONTENT), default="en")
    ap.add_argument("--rate", default="+8%", help="edge-tts speaking rate (default +8%%)")
    ap.add_argument("--assets", type=Path, default=ROOT / "assets",
                    help="folder with optional .mp4/.jpg B-roll")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--drone-db", type=float, default=-22.0, help="drone level, dBFS RMS")
    ap.add_argument("--reuse-tts", action="store_true", help="reuse existing voiceover/words")
    ap.add_argument("--preview", type=float, default=None,
                    help="render only the first N seconds (quick test)")
    args = ap.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("ffmpeg/ffprobe not found on PATH")
    sfx = "" if args.lang == "en" else f"_{args.lang}"
    out = args.output or ROOT / f"cyclone_arnab_short{sfx}.mp4"
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    voice_mp3 = ROOT / f"voiceover{sfx}.mp3"
    voice_vtt = ROOT / f"voiceover{sfx}.vtt"

    t0 = time.time()
    words = build_voiceover(args.lang, args.rate, voice_mp3, voice_vtt, build, args.reuse_tts)
    drone = build / "drone.wav"
    synth_drone(drone, DURATION, args.drone_db)
    mix = build / f"mix{sfx}.wav"
    mix_audio(voice_mp3, drone, mix)
    broll = build_broll(args.assets, build)
    renderer = Renderer(args.lang, words, broll is not None)
    frames = N_FRAMES if args.preview is None else int(min(args.preview, DURATION) * FPS)
    render_video(renderer, mix, broll, out, frames)
    verify(out, frames / FPS)
    print(f"[done] {out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
