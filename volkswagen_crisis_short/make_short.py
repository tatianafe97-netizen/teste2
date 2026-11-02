#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 - automated 50 s vertical Short: "Volkswagen in Crisis".

Pipeline
  1. edge-tts narration, one block per scene, with word-level timings -> voiceover.mp3 / voiceover.vtt
  2. scipy/numpy synthesized broadcast pulse bed at -22 dB, mixed under the narration
  3. Pillow + matplotlib frame renderer (multiprocess) -> raw frames piped into FFmpeg
  4. optional B-roll from assets/ (*.mp4, *.jpg, *.jpeg, *.png) composited behind the graphics
     with a dark broadcast vignette
  5. H.264 / AAC MP4, 1080x1920, 30 fps, 50 s

Usage
  python make_short.py               # English (en-US-ChristopherNeural)
  python make_short.py --lang pt     # Portuguese (pt-BR-AntonioNeural)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import signal
from scipy.io import wavfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from content import FACTS, SCENES, STRINGS, VOICES  # noqa: E402

ROOT = Path(__file__).resolve().parent
W, H, FPS, DUR = 1080, 1920, 30, 50.0
NFRAMES = int(DUR * FPS)
SR = 48_000

# ---------------------------------------------------------------- palette (financial desk)
SLATE_0 = (14, 17, 21)
SLATE_1 = (28, 33, 40)
SLATE_2 = (44, 51, 60)
SLATE_3 = (70, 80, 92)
RED = (230, 36, 43)
RED_DK = (140, 16, 22)
STEEL = (74, 127, 176)
STEEL_LT = (143, 184, 222)
WHITE = (245, 247, 250)
GREY = (168, 176, 185)
HEX = lambda c: "#%02x%02x%02x" % c  # noqa: E731

# ---------------------------------------------------------------- layout (px)
HEADER_Y0, HEADER_Y1 = 78, 250
PROGRESS_Y = 266
KICKER_Y = 296
CONTENT_Y0 = 420
CAPTION_CY = 1352
TICKER_Y0, TICKER_Y1 = 1484, 1544
SIDE = 48


# ======================================================================================
# helpers
# ======================================================================================
def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


# ---------------------------------------------------------------- fonts
FONT_DIRS = [ROOT / "fonts", Path("/usr/share/fonts/opentype/inter"), Path("/usr/share/fonts/truetype/dejavu")]
FONT_FILES = {
    "black": ["Inter-Black.otf", "InterDisplay-Black.otf", "DejaVuSans-Bold.ttf"],
    "xbold": ["Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf"],
    "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf"],
    "semi": ["Inter-SemiBold.otf", "DejaVuSans-Bold.ttf"],
    "reg": ["Inter-Medium.otf", "Inter-Regular.otf", "DejaVuSans.ttf"],
}


@lru_cache(None)
def font_path(weight: str) -> str:
    for name in FONT_FILES[weight]:
        for d in FONT_DIRS:
            p = d / name
            if p.exists():
                return str(p)
    found = shutil.which("fc-match")
    if found:
        return subprocess.run(["fc-match", "-f", "%{file}", "sans:bold"], capture_output=True, text=True).stdout
    raise FileNotFoundError("no usable font found; drop a .ttf/.otf into ./fonts")


@lru_cache(None)
def F(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path(weight), size)


def fit_font(text: str, weight: str, size: int, max_w: int, min_size: int = 18) -> ImageFont.FreeTypeFont:
    while size > min_size:
        f = F(weight, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return F(weight, min_size)


# ======================================================================================
# 1. narration (edge-tts) with word timings
# ======================================================================================
def _patch_edge_tts_ssl():
    """Trust a corporate / proxy CA bundle on top of certifi when one is configured."""
    import edge_tts.communicate as comm

    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        bundle = os.environ.get(var)
        if bundle and Path(bundle).is_file():
            try:
                comm._SSL_CTX.load_verify_locations(cafile=bundle)
            except Exception:  # pragma: no cover - best effort
                pass
            break


async def _tts_block(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    import edge_tts

    words: list[dict] = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with open(mp3, "wb") as fh:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    "text": chunk["text"],
                })
    return words


def decode_audio(path: Path, tempo: float = 1.0) -> np.ndarray:
    af = ["-af", f"atempo={tempo:.5f}"] if abs(tempo - 1.0) > 1e-3 else []
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), *af, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def fmt_ts(t: float) -> str:
    h, rem = divmod(max(t, 0.0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(words: list[dict], path: Path) -> None:
    lines = ["WEBVTT", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{fmt_ts(w['start'])} --> {fmt_ts(w['end'])}", w["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_voiceover(lang: str, voice: str, rate: str, build: Path, out_mp3: Path, out_vtt: Path) -> list[dict]:
    _patch_edge_tts_ssl()
    strings = STRINGS[lang]
    track = np.zeros(int(DUR * SR), dtype=np.float32)
    all_words: list[dict] = []
    for i, (text, (s0, s1)) in enumerate(zip(strings["narration"], SCENES)):
        mp3 = build / f"vo_{lang}_{i + 1}.mp3"
        for attempt in range(4):
            try:
                words = asyncio.run(_tts_block(text, voice, rate, mp3))
                if mp3.stat().st_size > 0 and words:
                    break
            except Exception as exc:  # network hiccups
                log(f"  edge-tts attempt {attempt + 1} failed: {exc}")
            time.sleep(2 ** (attempt + 1))
        else:
            raise RuntimeError(f"edge-tts failed for scene {i + 1}")

        lead, tail = 0.15, 0.30
        window = (s1 - s0) - lead - tail
        dur = ffprobe_duration(mp3)
        tempo = 1.0
        if dur > window:
            tempo = dur / window
            if tempo > 1.18:
                log(f"  WARNING scene {i + 1}: narration {dur:.2f}s needs {tempo:.2f}x to fit {window:.2f}s")
        audio = decode_audio(mp3, tempo)
        start = int((s0 + lead) * SR)
        end = min(len(track), start + len(audio))
        track[start:end] += audio[: end - start]
        for w in words:
            all_words.append({
                "start": round(s0 + lead + w["start"] / tempo, 3),
                "end": round(s0 + lead + w["end"] / tempo, 3),
                "text": w["text"],
                "scene": i,
            })
        log(f"  scene {i + 1}: {len(words)} words, {dur:.2f}s raw, tempo {tempo:.3f}, window {window:.2f}s")

    raw_wav = build / f"voice_raw_{lang}.wav"
    wavfile.write(raw_wav, SR, track)
    norm_wav = build / f"voice_{lang}.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw_wav),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "1", "-t", str(DUR), str(norm_wav)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(norm_wav), "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)])
    write_vtt(all_words, out_vtt)
    (build / f"words_{lang}.json").write_text(json.dumps(all_words, ensure_ascii=False, indent=1))
    return all_words


# ======================================================================================
# 2. broadcast pulse bed (scipy) + mix
# ======================================================================================
def synth_bed(bed_db: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(DUR * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2), dtype=np.float64)

    # low industrial drone (A1 + E2) with slow breathing LFO
    lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.08 * t - np.pi / 2)
    drone = 0.55 * np.sin(2 * np.pi * 55.0 * t) + 0.25 * np.sin(2 * np.pi * 82.41 * t + 0.4)
    drone += 0.12 * signal.sawtooth(2 * np.pi * 110.0 * t)
    b, a = signal.butter(2, 300 / (SR / 2), "low")
    drone = signal.lfilter(b, a, drone) * lfo
    out += 0.45 * drone[:, None]

    # heartbeat-style pulse, 96 BPM, accented on the beat
    beat = 60.0 / 96.0
    klen = int(0.35 * SR)
    kt = np.arange(klen) / SR
    freq = 46 + 54 * np.exp(-kt / 0.04)
    kick = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-kt / 0.11)
    k = 0
    bt = 0.0
    while bt < DUR - 0.4:
        i0 = int(bt * SR)
        gain = 1.0 if k % 2 == 0 else 0.55
        out[i0:i0 + klen] += (0.9 * gain * kick)[:, None]
        bt += beat / 2 if k % 2 == 0 else beat * 1.5  # "lub-dub" pattern
        k += 1

    # clock-like hi ticks on 8ths, alternating pan
    tlen = int(0.03 * SR)
    hb, ha = signal.butter(2, 5000 / (SR / 2), "high")
    step = beat / 2
    j = 0
    tt = 0.0
    while tt < DUR - 0.1:
        i0 = int(tt * SR)
        noise = signal.lfilter(hb, ha, rng.standard_normal(tlen)) * np.exp(-np.arange(tlen) / (0.006 * SR))
        pan = 0.3 if j % 2 else 0.7
        amp = 0.16 if j % 4 == 0 else 0.08
        seg = out[i0:i0 + tlen]
        seg[:, 0] += amp * (1 - pan) * noise[: len(seg)]
        seg[:, 1] += amp * pan * noise[: len(seg)]
        tt += step
        j += 1

    # risers into each scene change + low impact on the cut
    for s0, _ in SCENES[1:]:
        rl = int(1.6 * SR)
        r0 = int(s0 * SR) - rl
        env = np.linspace(0, 1, rl) ** 2.5
        noise = rng.standard_normal(rl)
        sos = signal.butter(2, [800 / (SR / 2), 4000 / (SR / 2)], "band", output="sos")
        riser = signal.sosfilt(sos, noise) * env * 0.35
        out[r0:r0 + rl] += riser[:, None]
        il = int(1.2 * SR)
        it = np.arange(il) / SR
        boom = np.sin(2 * np.pi * (38 + 40 * np.exp(-it / 0.05)) * it) * np.exp(-it / 0.35)
        i0 = int(s0 * SR)
        out[i0:i0 + il] += (0.9 * boom)[:, None]

    # fades, normalise to 0 dBFS peak, then drop to bed level
    fade_in, fade_out = int(0.8 * SR), int(1.8 * SR)
    out[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    out[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    out /= np.max(np.abs(out)) + 1e-9
    out *= 10 ** (bed_db / 20)
    return out.astype(np.float32)


def build_mix(voice_wav: Path, bed: np.ndarray, out_wav: Path) -> None:
    _, voice = wavfile.read(voice_wav)
    voice = voice.astype(np.float32)
    if voice.dtype.kind == "i":
        voice /= 32768.0
    n = bed.shape[0]
    v = np.zeros(n, dtype=np.float32)
    v[: min(n, len(voice))] = voice[:n]
    mix = bed + v[:, None]
    peak = np.max(np.abs(mix))
    if peak > 0.89:  # ~ -1 dBFS ceiling
        mix *= 0.89 / peak
    wavfile.write(out_wav, SR, mix.astype(np.float32))


# ======================================================================================
# 3. captions: group word timings into short broadcast chunks
# ======================================================================================
def build_chunks(words: list[dict], max_words: int = 3, max_chars: int = 18) -> list[dict]:
    chunks: list[dict] = []
    cur: list[dict] = []
    for idx, w in enumerate(words):
        if cur:
            prev = cur[-1]
            gap = w["start"] - prev["end"]
            chars = sum(len(x["text"]) + 1 for x in cur) + len(w["text"])
            if len(cur) >= max_words or chars > max_chars or gap > 0.28 or w["scene"] != prev["scene"]:
                chunks.append({"words": cur})
                cur = []
        cur.append(w)
    if cur:
        chunks.append({"words": cur})
    for c in chunks:
        c["start"] = c["words"][0]["start"]
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1]["start"] if i + 1 < len(chunks) else DUR
        c["end"] = min(nxt, c["words"][-1]["end"] + 0.45)
    return chunks


# ======================================================================================
# 4. matplotlib charts (rendered at a quantized animation progress, cached per worker)
# ======================================================================================
_MPL_READY = False


def _mpl_setup():
    global _MPL_READY
    if _MPL_READY:
        return
    for w in ("bold", "semi", "black"):
        try:
            font_manager.fontManager.addfont(font_path(w))
        except Exception:
            pass
    fam = font_manager.FontProperties(fname=font_path("semi")).get_name()
    plt.rcParams.update({
        "font.family": fam,
        "font.weight": "semibold",
        "text.color": HEX(WHITE),
        "axes.labelcolor": HEX(GREY),
        "xtick.color": HEX(WHITE),
        "ytick.color": HEX(GREY),
        "axes.edgecolor": HEX(SLATE_3),
        "axes.facecolor": "none",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
    })
    _MPL_READY = True


def _fig_to_image(fig) -> Image.Image:
    fig.canvas.draw()
    arr = np.asarray(fig.canvas.buffer_rgba()).copy()
    plt.close(fig)
    return Image.fromarray(arr, "RGBA")


def _style_ax(ax, title):
    ax.set_title(title, loc="left", fontsize=17, color=HEX(STEEL_LT), pad=14, fontweight="bold")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(HEX(SLATE_3))
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", labelsize=14, length=0)
    ax.tick_params(axis="x", labelsize=15, length=0, pad=10)
    ax.grid(axis="y", color=HEX(SLATE_3), alpha=0.45, lw=1)
    ax.set_axisbelow(True)


@lru_cache(maxsize=256)
def chart_s1(q: int, lang: str) -> Image.Image:
    _mpl_setup()
    S = STRINGS[lang]
    p = ease_out(q / 60)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.84, 4.0), dpi=100, gridspec_kw={"wspace": 0.42})
    fig.subplots_adjust(left=0.08, right=0.98, top=0.86, bottom=0.2)

    vals = [FACTS["op_loss_q3_2025_bn"], FACTS["op_loss_q3_2026_bn"]]
    bars = a1.bar(S["s1_ax1_cats"], [v * p for v in vals], color=[HEX(STEEL), HEX(RED)], width=0.58, zorder=3)
    a1.axhline(0, color=HEX(WHITE), lw=2, zorder=4)
    a1.set_ylim(-7.2, 0.6)
    _style_ax(a1, S["s1_ax1_title"])
    if p > 0.55:
        alpha = clamp((p - 0.55) / 0.3)
        for b, v in zip(bars, vals):
            a1.text(b.get_x() + b.get_width() / 2, v * p - 0.25, f"{v:+.2f}".replace("+", "+").replace(".", "," if lang == "pt" else "."),
                    ha="center", va="top", fontsize=20, fontweight="bold", color=HEX(WHITE), alpha=alpha)

    vals2 = [FACTS["deliveries_chg_pct"], FACTS["revenue_chg_pct"]]
    bars2 = a2.bar(S["s1_ax2_cats"], [v * p for v in vals2], color=[HEX(RED), HEX(RED_DK)], width=0.58, zorder=3)
    a2.axhline(0, color=HEX(WHITE), lw=2, zorder=4)
    a2.set_ylim(-18.5, 0.8)
    _style_ax(a2, S["s1_ax2_title"])
    if p > 0.55:
        alpha = clamp((p - 0.55) / 0.3)
        for b, v in zip(bars2, vals2):
            txt = f"{v:.1f}%"
            if lang == "pt":
                txt = txt.replace(".", ",")
            a2.text(b.get_x() + b.get_width() / 2, v * p - 0.6, txt, ha="center", va="top",
                    fontsize=20, fontweight="bold", color=HEX(WHITE), alpha=alpha)
    return _fig_to_image(fig)


@lru_cache(maxsize=256)
def chart_s2(q: int, lang: str) -> Image.Image:
    _mpl_setup()
    S = STRINGS[lang]
    p = ease_out(q / 60)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.84, 4.1), dpi=100, gridspec_kw={"wspace": 0.38, "width_ratios": [1, 1.25]})
    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.2)

    idx = 100 + FACTS["china_chg_pct"]  # 61.5
    vals = [100.0, idx]
    bars = a1.bar(S["s2_ax1_cats"], [100.0, 100 - (100 - idx) * p], color=[HEX(STEEL), HEX(RED)], width=0.6, zorder=3)
    a1.set_ylim(0, 112)
    _style_ax(a1, S["s2_ax1_title"])
    a1.title.set_fontsize(14)
    for b, v in zip(bars, vals):
        shown = b.get_height()
        a1.text(b.get_x() + b.get_width() / 2, shown + 2, f"{shown:.1f}".replace(".", "," if lang == "pt" else "."),
                ha="center", va="bottom", fontsize=19, fontweight="bold", color=HEX(WHITE))

    charges = [FACTS["porsche_impairment_bn"], FACTS["china_writedown_bn"], FACTS["other_restructuring_bn"]]
    cats = S["s2_ax2_cats"]
    y = np.arange(len(charges))[::-1]
    a2.barh(y, [c * p for c in charges], color=[HEX(RED), HEX(RED_DK), HEX(STEEL)], height=0.62, zorder=3)
    a2.set_yticks(y, cats)
    a2.set_xlim(0, 7.6)
    a2.set_title(S["s2_ax2_title"], loc="left", fontsize=14, color=HEX(STEEL_LT), pad=14, fontweight="bold")
    for side in ("top", "right", "bottom"):
        a2.spines[side].set_visible(False)
    a2.spines["left"].set_color(HEX(SLATE_3))
    a2.tick_params(axis="y", labelsize=14, length=0, colors=HEX(WHITE))
    a2.tick_params(axis="x", labelsize=0, length=0)
    a2.set_xticks([])
    if p > 0.5:
        alpha = clamp((p - 0.5) / 0.3)
        for yy, c in zip(y, charges):
            txt = f"€{c:.1f}B" if lang == "en" else f"€{c:.1f} bi".replace(".", ",")
            a2.text(c * p + 0.15, yy, txt, va="center", fontsize=18, fontweight="bold", color=HEX(WHITE), alpha=alpha)
    return _fig_to_image(fig)


@lru_cache(maxsize=256)
def chart_s3(q: int, lang: str) -> Image.Image:
    _mpl_setup()
    S = STRINGS[lang]
    p = ease_in_out(q / 60)
    y0, y1 = FACTS["freeze_from"], FACTS["freeze_to"]
    fig, ax = plt.subplots(figsize=(9.84, 4.2), dpi=100)
    fig.subplots_adjust(left=0.08, right=0.86, top=0.86, bottom=0.14)

    xs = np.linspace(y0, y1, 200)
    final = 1 + FACTS["real_wage_loss_pct"] / 100  # 0.90
    real = 100 * final ** ((xs - y0) / (y1 - y0))
    nominal = np.full_like(xs, 100.0)
    m = xs <= y0 + (y1 - y0) * max(p, 0.002)
    ax.plot(xs[m], nominal[m], color=HEX(STEEL_LT), lw=4, zorder=4, solid_capstyle="round")
    ax.plot(xs[m], real[m], color=HEX(RED), lw=5, zorder=5, solid_capstyle="round")
    ax.fill_between(xs[m], real[m], nominal[m], color=HEX(RED), alpha=0.22, lw=0, zorder=3)
    xe = xs[m][-1]
    ax.scatter([xe], [real[m][-1]], s=120, color=HEX(RED), zorder=6, edgecolor=HEX(WHITE), linewidth=2)
    ax.scatter([xe], [100], s=70, color=HEX(STEEL_LT), zorder=6)
    ax.text(y0 + 0.05, 101.0, S["s3_nominal"], va="bottom", fontsize=15, color=HEX(STEEL_LT))
    rv = real[m][-1]
    lab = f"{rv - 100:+.1f}%" if lang == "en" else f"{rv - 100:+.1f}%".replace(".", ",")
    ax.text(xe - 0.06, rv - 0.6, lab, va="top", ha="right", fontsize=24, fontweight="bold", color=HEX(RED), clip_on=False)
    ax.text(y0 + 0.05, 88.0, S["s3_real"], fontsize=15, color=HEX(RED), alpha=clamp(p * 3))
    ax.set_xlim(y0 - 0.1, y1 + 0.05)
    ax.set_ylim(86, 103.5)
    ax.set_xticks(range(y0, y1 + 1))
    _style_ax(ax, S["s3_ax_title"])
    return _fig_to_image(fig)


# ======================================================================================
# 5. frame renderer
# ======================================================================================
class Renderer:
    def __init__(self, lang: str, chunks: list[dict], broll: bool):
        self.lang = lang
        self.S = STRINGS[lang]
        self.chunks = chunks
        self.broll = broll
        self.base = self._make_base()
        self.header = self._make_header()
        self.ticker_strip = self._make_ticker()

    # ---------------------------------------------------------------- static layers
    def _make_base(self) -> Image.Image:
        if self.broll:
            # translucent slate wash so B-roll reads as texture, not content
            img = Image.new("RGBA", (W, H), SLATE_0 + (110,))
        else:
            y = np.linspace(0, 1, H)[:, None]
            x = np.linspace(-1, 1, W)[None, :]
            top = np.array(SLATE_2, dtype=np.float32)
            bot = np.array(SLATE_0, dtype=np.float32)
            g = top * (1 - y[..., None]) * 0.9 + bot * (y[..., None])
            g = g + np.zeros((H, W, 3), dtype=np.float32)
            # steel-blue glow behind the chart area
            glow = np.exp(-((x * 1.1) ** 2 + ((y - 0.38) * 2.4) ** 2))[..., None]
            g = g + glow * np.array([10, 22, 38], dtype=np.float32)
            rng = np.random.default_rng(3)
            g += rng.normal(0, 2.0, g.shape)  # film grain against banding
            img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
        d = ImageDraw.Draw(img)
        # faint financial-terminal grid
        for gx in range(0, W, 60):
            d.line([(gx, 0), (gx, H)], fill=STEEL + (14,), width=1)
        for gy in range(0, H, 60):
            d.line([(0, gy), (W, gy)], fill=STEEL + (14,), width=1)
        # broadcast vignette
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.45) / (H * 0.62)) ** 2)
        a = np.clip((r - 0.55) / 0.6, 0, 1) ** 1.6 * 235
        vig = Image.new("RGBA", (W, H), SLATE_0 + (0,))
        vig.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
        img.alpha_composite(vig)
        return img

    def _make_header(self) -> Image.Image:
        S = self.S
        img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, HEADER_Y0 - 8, W, HEADER_Y1], fill=SLATE_0 + (215,))
        d.rectangle([0, HEADER_Y1 - 6, W, HEADER_Y1], fill=RED)
        # live tag drawn per-frame (blink); leave room for it
        live_w = int(F("black", 26).getlength(S["live"])) + 62
        self.live_box = (SIDE, HEADER_Y0 + 10, SIDE + live_w, HEADER_Y0 + 56)
        fx = SIDE + live_w + 18
        f_top = fit_font(S["header_top"], "bold", 30, W - fx - SIDE)
        d.text((fx, HEADER_Y0 + 33), S["header_top"], font=f_top, fill=STEEL_LT, anchor="lm")
        f_main = fit_font(S["header_main"], "black", 92, W - 2 * SIDE)
        d.text((SIDE - 4, HEADER_Y0 + 118), S["header_main"], font=f_main, fill=WHITE, anchor="lm")
        return img

    def _make_ticker(self) -> Image.Image:
        f = F("bold", 30)
        sep = "   •   "
        text = sep.join(self.S["ticker"]) + sep
        tw = int(f.getlength(text))
        strip = Image.new("RGBA", (tw * 2, TICKER_Y1 - TICKER_Y0), (0, 0, 0, 0))
        d = ImageDraw.Draw(strip)
        for k in range(2):
            d.text((k * tw, (TICKER_Y1 - TICKER_Y0) // 2), text, font=f, fill=WHITE, anchor="lm")
        self.ticker_w = tw
        return strip

    # ---------------------------------------------------------------- dynamic pieces
    def draw_header(self, img: Image.Image, t: float):
        img.alpha_composite(self.header, (0, 0))
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = self.live_box
        d.rounded_rectangle(self.live_box, radius=8, fill=RED)
        on = (t % 1.0) < 0.6
        d.ellipse([x0 + 16, (y0 + y1) // 2 - 8, x0 + 32, (y0 + y1) // 2 + 8], fill=WHITE if on else RED_DK)
        d.text((x0 + 44, (y0 + y1) // 2), self.S["live"], font=F("black", 26), fill=WHITE, anchor="lm")
        # scene progress segments
        gap = 10
        segw = (W - 2 * SIDE - 3 * gap) / 4
        for k, (s0, s1) in enumerate(SCENES):
            xa = SIDE + k * (segw + gap)
            d.rounded_rectangle([xa, PROGRESS_Y, xa + segw, PROGRESS_Y + 8], radius=4, fill=SLATE_3 + (200,))
            fr = clamp((t - s0) / (s1 - s0))
            if fr > 0:
                d.rounded_rectangle([xa, PROGRESS_Y, xa + max(8, segw * fr), PROGRESS_Y + 8], radius=4,
                                    fill=RED if fr < 1 else WHITE)

    def draw_ticker(self, img: Image.Image, t: float):
        d = ImageDraw.Draw(img)
        d.rectangle([0, TICKER_Y0, W, TICKER_Y1], fill=SLATE_0 + (230,))
        offset = int((t * 150) % self.ticker_w)
        crop = self.ticker_strip.crop((offset, 0, offset + W, TICKER_Y1 - TICKER_Y0))
        img.alpha_composite(crop, (0, TICKER_Y0))
        label = self.S["channel"]
        f = F("black", 26)
        lw = int(f.getlength(label)) + 36
        d.rectangle([0, TICKER_Y0, lw, TICKER_Y1], fill=RED)
        d.polygon([(lw, TICKER_Y0), (lw + 22, TICKER_Y0), (lw, TICKER_Y1)], fill=RED)
        d.text((18, (TICKER_Y0 + TICKER_Y1) // 2), label, font=f, fill=WHITE, anchor="lm")
        d.line([(0, TICKER_Y0), (W, TICKER_Y0)], fill=STEEL, width=2)
        d.text((W // 2, TICKER_Y1 + 26), self.S["channel_full"], font=F("semi", 22), fill=GREY + (200,), anchor="mm")

    def draw_kicker(self, layer: Image.Image, k: int, lt: float):
        d = ImageDraw.Draw(layer)
        tag = f"{k + 1:02d}  {self.S['kickers'][k]}"
        f = F("black", 26)
        tw = int(f.getlength(tag)) + 36
        grow = ease_out(lt / 0.35)
        d.rectangle([SIDE, KICKER_Y, SIDE + int(tw * grow), KICKER_Y + 44], fill=RED)
        if grow > 0.8:
            d.text((SIDE + 18, KICKER_Y + 22), tag, font=f, fill=WHITE, anchor="lm")
        title = self.S["titles"][k]
        ft = fit_font(title, "black", 64, W - 2 * SIDE)
        a = int(255 * ease_out((lt - 0.1) / 0.35))
        d.text((SIDE - 2, KICKER_Y + 92), title, font=ft, fill=WHITE + (a,), anchor="lm")

    @staticmethod
    def panel(d: ImageDraw.ImageDraw, box, accent=STEEL, fill_alpha=210):
        d.rounded_rectangle(box, radius=18, fill=SLATE_1 + (fill_alpha,), outline=SLATE_3 + (255,), width=2)
        x0, y0, x1, y1 = box
        d.rounded_rectangle([x0, y0, x0 + 8, y1], radius=4, fill=accent)

    def tiles(self, layer, items, y0, y1, lt, start, accents):
        d = ImageDraw.Draw(layer)
        n = len(items)
        gap = 18
        tw = (W - 2 * SIDE - gap * (n - 1)) / n
        for i, ((big, small), acc) in enumerate(zip(items, accents)):
            a = ease_out((lt - start - i * 0.25) / 0.4)
            if a <= 0:
                continue
            x0 = SIDE + i * (tw + gap)
            dy = int((1 - a) * 30)
            box = [x0, y0 + dy, x0 + tw, y1 + dy]
            self.panel(d, box, accent=acc, fill_alpha=int(225 * a))
            fb = fit_font(big, "black", 58, int(tw - 40))
            d.text((x0 + tw / 2 + 4, y0 + dy + 64), big, font=fb, fill=acc[:3] + (int(255 * a),) if acc != STEEL else WHITE + (int(255 * a),), anchor="mm")
            fs = fit_font(small, "bold", 21, int(tw - 30), 14)
            d.text((x0 + tw / 2 + 4, y0 + dy + 128), small, font=fs, fill=GREY + (int(255 * a),), anchor="mm")

    def source(self, layer, text, y, lt):
        d = ImageDraw.Draw(layer)
        a = int(200 * ease_out((lt - 1.0) / 0.6))
        d.text((SIDE, y), text, font=fit_font(text, "reg", 20, W - 2 * SIDE, 14), fill=GREY + (a,), anchor="lm")

    # ---------------------------------------------------------------- scenes
    def scene1(self, layer, lt):
        S, d = self.S, ImageDraw.Draw(layer)
        # big counter
        p = ease_out((lt - 0.3) / 1.6)
        val = FACTS["op_loss_q3_2026_bn"] * p
        num = f"-€{abs(val):.2f}B" if self.lang == "en" else f"-€{abs(val):.2f} bi".replace(".", ",")
        self.panel(d, [SIDE, CONTENT_Y0, W - SIDE, CONTENT_Y0 + 190], accent=RED)
        shake = int(6 * math.sin(lt * 60) * max(0, 1 - abs(lt - 1.9) / 0.25)) if 1.65 < lt < 2.15 else 0
        d.text((SIDE + 40 + shake, CONTENT_Y0 + 82), num, font=F("black", 110), fill=RED, anchor="lm")
        d.text((SIDE + 44, CONTENT_Y0 + 158), S["s1_counter_label"], font=F("black", 28), fill=WHITE, anchor="lm")
        sub_f = F("semi", 22)
        d.text((W - SIDE - 30, CONTENT_Y0 + 158), S["s1_counter_sub"], font=sub_f, fill=GREY, anchor="rm") \
            if sub_f.getlength(S["s1_counter_sub"]) + F("black", 28).getlength(S["s1_counter_label"]) < W - 2 * SIDE - 100 else None
        # chart
        q = int(round(clamp((lt - 0.8) / 2.2) * 60))
        self.panel(d, [SIDE, CONTENT_Y0 + 206, W - SIDE, CONTENT_Y0 + 626], accent=STEEL)
        layer.alpha_composite(chart_s1(q, self.lang), (SIDE + 6, CONTENT_Y0 + 216))
        # KPI tiles (margin cap pulses)
        self.tiles(layer, S["s1_tiles"], CONTENT_Y0 + 642, CONTENT_Y0 + 802, lt, 2.6, [WHITE, WHITE, RED])
        self.source(layer, S["s1_source"], CONTENT_Y0 + 826, lt)

    def scene2(self, layer, lt):
        S, d = self.S, ImageDraw.Draw(layer)
        half = (W - 2 * SIDE - 18) // 2
        boxes = [[SIDE, CONTENT_Y0, SIDE + half, CONTENT_Y0 + 200],
                 [SIDE + half + 18, CONTENT_Y0, W - SIDE, CONTENT_Y0 + 200]]
        p = ease_out((lt - 0.3) / 1.4)
        china = FACTS["china_chg_pct"] * p
        big_l = f"{china:.1f}%" if self.lang == "en" else f"{china:.1f}%".replace(".", ",")
        charges = FACTS["one_off_total_bn"]
        big_r = f"€{charges * p:.1f}B" if self.lang == "en" else f"€{charges * p:.1f} bi".replace(".", ",")
        for box, head, big, sub, acc in [
            (boxes[0], S["s2_left_head"], big_l, S["s2_left_sub"], RED),
            (boxes[1], S["s2_right_head"], big_r, S["s2_right_sub"], RED),
        ]:
            self.panel(d, box, accent=acc)
            cx = (box[0] + box[2]) // 2 + 4
            d.text((cx, box[1] + 40), head, font=fit_font(head, "black", 28, half - 40), fill=STEEL_LT, anchor="mm")
            d.text((cx, box[1] + 108), big, font=fit_font(big, "black", 88, half - 40), fill=acc, anchor="mm")
            d.text((cx, box[1] + 170), sub, font=fit_font(sub, "bold", 24, half - 40), fill=WHITE, anchor="mm")
        q = int(round(clamp((lt - 1.0) / 2.2) * 60))
        self.panel(d, [SIDE, CONTENT_Y0 + 216, W - SIDE, CONTENT_Y0 + 646], accent=STEEL)
        layer.alpha_composite(chart_s2(q, self.lang), (SIDE + 6, CONTENT_Y0 + 226))
        # tariff banner with hazard stripes
        a = ease_out((lt - 5.5) / 0.5)
        if a > 0:
            y0, y1 = CONTENT_Y0 + 662, CONTENT_Y0 + 802
            dx = int((1 - a) * 80)
            self.panel(d, [SIDE + dx, y0, W - SIDE + dx, y1], accent=RED, fill_alpha=int(230 * a))
            stripe = Image.new("RGBA", (150, y1 - y0 - 24), (0, 0, 0, 0))
            sd = ImageDraw.Draw(stripe)
            off = int(lt * 40) % 40
            for sx in range(-200, 200, 40):
                sd.polygon([(sx + off, 0), (sx + off + 20, 0), (sx + off + 20 - 60, stripe.height), (sx + off - 60, stripe.height)],
                           fill=RED + (int(255 * a),))
            layer.alpha_composite(stripe, (SIDE + 22 + dx, y0 + 12))
            hx = SIDE + 196 + dx
            d.text((hx, y0 + 46), S["s2_banner_head"], font=F("black", 44), fill=WHITE + (int(255 * a),), anchor="lm")
            d.text((hx, y0 + 102), S["s2_banner_text"], font=fit_font(S["s2_banner_text"], "semi", 26, W - SIDE - hx - 24),
                   fill=GREY + (int(255 * a),), anchor="lm")
        self.source(layer, S["s2_source"], CONTENT_Y0 + 826, lt)

    def scene3(self, layer, lt):
        S, d = self.S, ImageDraw.Draw(layer)
        p = ease_out((lt - 0.3) / 1.8)
        n = int(round(FACTS["workers"] * p))
        num = f"{n:,}" if self.lang == "en" else f"{n:,}".replace(",", ".")
        self.panel(d, [SIDE, CONTENT_Y0, W - SIDE, CONTENT_Y0 + 190], accent=STEEL)
        d.text((SIDE + 40, CONTENT_Y0 + 80), num, font=F("black", 110), fill=WHITE, anchor="lm")
        # freeze badge
        bx = W - SIDE - 30
        fa = ease_out((lt - 1.8) / 0.4)
        if fa > 0:
            badge = "2026 → 2030"
            fb = F("black", 30)
            bw = fb.getlength(badge) + 40
            d.rounded_rectangle([bx - bw, CONTENT_Y0 + 52, bx, CONTENT_Y0 + 108], radius=10,
                                fill=STEEL + (int(255 * fa),))
            d.text((bx - bw / 2, CONTENT_Y0 + 80), badge, font=fb, fill=WHITE + (int(255 * fa),), anchor="mm")
        d.text((SIDE + 44, CONTENT_Y0 + 158), S["s3_counter_label"], font=F("black", 28), fill=STEEL_LT, anchor="lm")
        lab_w = F("black", 28).getlength(S["s3_counter_label"])
        f_sub = fit_font(S["s3_counter_sub"], "semi", 22, int(W - 2 * SIDE - lab_w - 110), 14)
        d.text((W - SIDE - 30, CONTENT_Y0 + 158), S["s3_counter_sub"], font=f_sub, fill=GREY, anchor="rm")
        q = int(round(clamp((lt - 1.2) / 4.0) * 60))
        self.panel(d, [SIDE, CONTENT_Y0 + 206, W - SIDE, CONTENT_Y0 + 646], accent=RED)
        layer.alpha_composite(chart_s3(q, self.lang), (SIDE + 6, CONTENT_Y0 + 214))
        self.tiles(layer, S["s3_tiles"], CONTENT_Y0 + 662, CONTENT_Y0 + 812, lt, 5.6, [WHITE, RED, RED])
        self.source(layer, S["s3_source"], CONTENT_Y0 + 836, lt)

    def scene4(self, layer, lt):
        S, d = self.S, ImageDraw.Draw(layer)
        colw = (W - 2 * SIDE - 80) // 2
        y0, y1 = CONTENT_Y0, CONTENT_Y0 + 470
        for side_i, (head, items, acc) in enumerate([
            (S["s4_left_head"], S["s4_left_items"], STEEL),
            (S["s4_right_head"], S["s4_right_items"], RED),
        ]):
            a = ease_out((lt - 0.2 - side_i * 0.35) / 0.45)
            if a <= 0:
                continue
            dx = int((1 - a) * (-90 if side_i == 0 else 90))
            x0 = SIDE + side_i * (colw + 80) + dx
            box = [x0, y0, x0 + colw, y1]
            self.panel(d, box, accent=acc, fill_alpha=int(225 * a))
            d.rectangle([x0 + 8, y0, x0 + colw, y0 + 74], fill=acc + (int(255 * a),))
            d.text((x0 + colw / 2 + 4, y0 + 38), head, font=fit_font(head, "black", 36, colw - 30),
                   fill=WHITE + (int(255 * a),), anchor="mm")
            for j, item in enumerate(items):
                ia = ease_out((lt - 0.9 - side_i * 0.35 - j * 0.45) / 0.35)
                if ia <= 0:
                    continue
                iy = y0 + 120 + j * 88
                d.rectangle([x0 + 30, iy - 7, x0 + 44, iy + 7], fill=acc + (int(255 * ia),))
                f = fit_font(item, "bold", 30, colw - 80, 16)
                d.text((x0 + 60, iy), item, font=f, fill=WHITE + (int(255 * ia),), anchor="lm")
        # VS badge
        va = ease_out((lt - 0.9) / 0.3)
        if va > 0:
            cx, cy = W // 2, (y0 + y1) // 2
            r = int(52 * (0.6 + 0.4 * va))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SLATE_0 + (int(255 * va),), outline=WHITE + (int(255 * va),), width=4)
            d.text((cx, cy), "VS", font=F("black", int(40 * (0.6 + 0.4 * va))), fill=WHITE + (int(255 * va),), anchor="mm")
        # question
        qa = ease_out((lt - 3.6) / 0.5)
        if qa > 0:
            qy = y1 + 30
            self.panel(d, [SIDE, qy, W - SIDE, qy + 110], accent=RED, fill_alpha=int(230 * qa))
            d.text((W // 2, qy + 55), S["s4_question"], font=fit_font(S["s4_question"], "black", 52, W - 2 * SIDE - 60),
                   fill=WHITE + (int(255 * qa),), anchor="mm")
        # CTA
        ca = ease_out((lt - 6.2) / 0.5)
        if ca > 0:
            cy0 = y1 + 160
            pulse = 0.5 + 0.5 * math.sin(lt * 6)
            glow = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.rounded_rectangle([SIDE + 10, 20, W - SIDE - 10, 180], radius=30, fill=RED + (int(150 * ca * pulse),))
            glow = glow.filter(ImageFilter.GaussianBlur(18))
            layer.alpha_composite(glow, (0, cy0 - 20))
            d.rounded_rectangle([SIDE, cy0, W - SIDE, cy0 + 160], radius=26, fill=RED + (int(255 * ca),))
            d.text((W // 2, cy0 + 60), S["s4_cta"], font=fit_font(S["s4_cta"], "black", 54, W - 2 * SIDE - 60),
                   fill=WHITE + (int(255 * ca),), anchor="mm")
            d.text((W // 2, cy0 + 118), S["s4_cta_sub"], font=F("bold", 30), fill=WHITE + (int(230 * ca),), anchor="mm")

    # ---------------------------------------------------------------- captions
    def draw_captions(self, img: Image.Image, t: float):
        chunk = None
        for c in self.chunks:
            if c["start"] - 0.02 <= t < c["end"]:
                chunk = c
                break
        if chunk is None:
            return
        words = [w["text"].upper() for w in chunk["words"]]
        active = 0
        for i, w in enumerate(chunk["words"]):
            if t >= w["start"] - 0.02:
                active = i
        f = F("black", 76)
        space = f.getlength(" ")
        widths = [f.getlength(w) for w in words]
        total = sum(widths) + space * (len(words) - 1)
        scale = min(1.0, (W - 2 * SIDE - 60) / max(total, 1))
        if scale < 1.0:
            f = F("black", int(76 * scale))
            space = f.getlength(" ")
            widths = [f.getlength(w) for w in words]
            total = sum(widths) + space * (len(words) - 1)
        cap = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(cap)
        x = (W - total) / 2
        cy = 100
        for i, (w, ww) in enumerate(zip(words, widths)):
            if i == active:
                d.rounded_rectangle([x - 14, cy - 52, x + ww + 14, cy + 50], radius=12, fill=RED)
            d.text((x, cy), w, font=f, fill=WHITE, anchor="lm", stroke_width=6 if i != active else 0, stroke_fill=(0, 0, 0))
            x += ww + space
        # pop-in on chunk start
        age = t - chunk["start"]
        s = 0.86 + 0.14 * ease_out(age / 0.12)
        if s < 0.999:
            nw, nh = int(W * s), int(200 * s)
            cap = cap.resize((nw, nh), Image.BILINEAR)
            img.alpha_composite(cap, ((W - nw) // 2, CAPTION_CY - nh // 2))
        else:
            img.alpha_composite(cap, (0, CAPTION_CY - 100))

    # ---------------------------------------------------------------- frame
    def frame(self, i: int) -> bytes:
        t = i / FPS
        img = self.base.copy()
        k = next(j for j, (s0, s1) in enumerate(SCENES) if s0 <= t < s1 or j == len(SCENES) - 1)
        s0, s1 = SCENES[k]
        lt = t - s0
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.draw_kicker(layer, k, lt)
        getattr(self, f"scene{k + 1}")(layer, lt)
        # scene transitions: slide/fade in, fade out
        a_in = ease_out(lt / 0.45)
        a_out = 1.0 if k == len(SCENES) - 1 else ease_out((s1 - t) / 0.25)
        a = min(a_in, a_out)
        dx = int((1 - a_in) * 120)
        if a < 0.999:
            alpha = layer.getchannel("A").point(lambda v, a=a: int(v * a))
            layer.putalpha(alpha)
        img.alpha_composite(layer, (dx, 0)) if dx == 0 else img.alpha_composite(layer.crop((0, 0, W - dx, H)), (dx, 0))
        # red flash wipe on the cut
        if k > 0 and lt < 0.22:
            wipe = Image.new("RGBA", (W, H), RED + (int(90 * (1 - lt / 0.22)),))
            img.alpha_composite(wipe)
        self.draw_header(img, t)
        self.draw_ticker(img, t)
        self.draw_captions(img, t)
        if self.broll:
            return img.tobytes()
        return img.convert("RGB").tobytes()


_R: Renderer | None = None


def _init_worker(lang, chunks, broll):
    global _R
    _R = Renderer(lang, chunks, broll)


def _render(i: int) -> bytes:
    return _R.frame(i)


# ======================================================================================
# 6. B-roll + final encode
# ======================================================================================
def find_broll(assets: Path) -> list[Path]:
    if not assets.is_dir():
        return []
    exts = {".mp4", ".mov", ".m4v", ".jpg", ".jpeg", ".png"}
    return sorted(p for p in assets.iterdir() if p.suffix.lower() in exts and not p.name.startswith("."))


def broll_inputs_and_filter(files: list[Path]) -> tuple[list[str], str]:
    args: list[str] = []
    parts: list[str] = []
    seg = DUR / len(files)
    nfr = int(math.ceil(seg * FPS))
    for i, f in enumerate(files):
        if f.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seg:.3f}", "-i", str(f)]
            parts.append(
                f"[{i}:v]scale=1296:2304:force_original_aspect_ratio=increase,crop=1296:2304,"
                f"zoompan=z='1+0.10*on/{nfr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
                f"trim=duration={seg:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[b{i}]"
            )
        else:
            args += ["-stream_loop", "-1", "-t", f"{seg:.3f}", "-i", str(f)]
            parts.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                f"trim=duration={seg:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[b{i}]"
            )
    concat = "".join(f"[b{i}]" for i in range(len(files)))
    parts.append(
        f"{concat}concat=n={len(files)}:v=1:a=0,"
        f"eq=brightness=-0.10:contrast=1.08:saturation=0.45,"
        f"colorbalance=bs=0.10:bm=0.05:rs=-0.04,"
        f"vignette=angle=PI/3.2,gblur=sigma=1.2,"
        f"tpad=stop_mode=clone:stop_duration={DUR},trim=duration={DUR},setpts=PTS-STARTPTS[bg]"
    )
    return args, ";".join(parts)


def encode(lang: str, words: list[dict], mix_wav: Path, out_mp4: Path, assets: Path, workers: int, preview: bool):
    files = find_broll(assets)
    broll = bool(files)
    chunks = build_chunks(words)
    pix = "rgba" if broll else "rgb24"
    frames = range(0, NFRAMES, 15) if preview else range(NFRAMES)

    cmd = ["ffmpeg", "-y", "-v", "error", "-stats"]
    filt = None
    if broll:
        b_args, b_filter = broll_inputs_and_filter(files)
        cmd += b_args
        vid_idx = len(files)
        filt = f"{b_filter};[bg][{vid_idx}:v]overlay=0:0:format=auto,format=yuv420p[v]"
        log(f"B-roll: {len(files)} asset(s) -> {', '.join(p.name for p in files)}")
    else:
        vid_idx = 0
    in_fps = 2 if preview else FPS
    cmd += ["-f", "rawvideo", "-pix_fmt", pix, "-s", f"{W}x{H}", "-r", str(in_fps), "-i", "-"]
    cmd += ["-i", str(mix_wav)]
    aud_idx = vid_idx + 1
    if filt:
        cmd += ["-filter_complex", filt, "-map", "[v]"]
    else:
        cmd += ["-map", f"{vid_idx}:v"]
    cmd += ["-map", f"{aud_idx}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-g", str(FPS * 2),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
            "-t", str(DUR), "-movflags", "+faststart", str(out_mp4)]

    log(f"rendering {len(frames)} frames with {workers} worker(s) -> {out_mp4.name}")
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ctx = mp.get_context("fork")
    with ctx.Pool(workers, initializer=_init_worker, initargs=(lang, chunks, broll)) as pool:
        for n, buf in enumerate(pool.imap(_render, frames, chunksize=6)):
            proc.stdin.write(buf)
            if n % 150 == 0:
                log(f"  frame {n}/{len(frames)}  ({time.time() - t0:.0f}s)")
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg encode failed")
    log(f"encode done in {time.time() - t0:.0f}s")


def verify(out_mp4: Path) -> dict:
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out_mp4)],
        check=True, capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    num, den = map(int, v["r_frame_rate"].split("/"))
    report = {
        "file": out_mp4.name,
        "size_mb": round(int(info["format"]["size"]) / 1e6, 2),
        "duration_s": round(float(info["format"]["duration"]), 3),
        "video": f"{v['codec_name']} {v['width']}x{v['height']} @ {num / den:g} fps, {v['pix_fmt']}",
        "audio": f"{a['codec_name']} {a['sample_rate']} Hz, {a['channels']} ch",
    }
    ok = (v["width"], v["height"]) == (W, H) and abs(num / den - FPS) < 0.01 and abs(report["duration_s"] - DUR) < 0.2
    report["ok"] = ok
    return report


# ======================================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=sorted(STRINGS), default="en", help="narration + on-screen language")
    ap.add_argument("--voice", help="override edge-tts voice")
    ap.add_argument("--rate", default="+8%", help="edge-tts speaking rate (default +8%%)")
    ap.add_argument("--bed-db", type=float, default=-22.0, help="pulse bed level in dB (default -22)")
    ap.add_argument("--assets", type=Path, default=ROOT / "assets", help="B-roll folder (*.mp4/*.jpg/*.png)")
    ap.add_argument("--out", type=Path, help="output mp4 path")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--reuse-tts", action="store_true", help="reuse cached narration if present")
    ap.add_argument("--preview", action="store_true", help="fast low-fps preview render")
    ap.add_argument("--stills", action="store_true", help="only dump a few PNG stills to build/")
    args = ap.parse_args()

    lang = args.lang
    voice = args.voice or VOICES[lang]
    suffix = "" if lang == "en" else f"_{lang}"
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    out_mp4 = args.out or ROOT / f"volkswagen_crisis_short{suffix}.mp4"
    vo_mp3 = ROOT / f"voiceover{suffix}.mp3"
    vo_vtt = ROOT / f"voiceover{suffix}.vtt"
    words_json = build / f"words_{lang}.json"

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH")

    log(f"lang={lang} voice={voice} rate={args.rate}")
    if args.reuse_tts and words_json.exists() and (build / f"voice_{lang}.wav").exists():
        words = json.loads(words_json.read_text())
        log("reusing cached narration")
    else:
        log("1/4 narration via edge-tts")
        words = build_voiceover(lang, voice, args.rate, build, vo_mp3, vo_vtt)

    if args.stills:
        r = Renderer(lang, build_chunks(words), bool(find_broll(args.assets)))
        for ts in (1.0, 4.0, 10.0, 12.2, 19.0, 31.0, 37.0, 41.0, 46.5):
            Image.frombytes("RGBA" if r.broll else "RGB", (W, H), r.frame(int(ts * FPS))).save(build / f"still_{lang}_{ts:05.1f}.png")
        log("stills written to build/")
        return

    log(f"2/4 pulse bed at {args.bed_db:g} dB + mix")
    bed = synth_bed(args.bed_db)
    wavfile.write(build / "bed.wav", SR, bed)
    mix_wav = build / f"mix_{lang}.wav"
    build_mix(build / f"voice_{lang}.wav", bed, mix_wav)

    log("3/4 render + encode")
    encode(lang, words, mix_wav, out_mp4, args.assets, args.workers, args.preview)

    log("4/4 verify")
    rep = verify(out_mp4)
    for k_, v_ in rep.items():
        log(f"  {k_}: {v_}")
    if not rep["ok"]:
        sys.exit("verification FAILED")
    log("done ✔")


if __name__ == "__main__":
    main()
