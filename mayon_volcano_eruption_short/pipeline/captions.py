"""Burned-in broadcast captions driven by the edge-tts word-level VTT."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import config as C
from .tts import Word

MAX_WORDS = 3
MAX_CHARS = 18
GAP_BREAK = 0.32
FONT_SIZE = 76
STROKE = 6


@dataclass
class Chunk:
    words: list[Word]
    start: float
    end: float


def group(words: list[Word]) -> list[Chunk]:
    chunks, cur = [], []

    def flush():
        if cur:
            chunks.append(Chunk(list(cur), cur[0].start, cur[-1].end))
            cur.clear()

    for w in words:
        if cur and cur[-1].text[-1:] in ".,!?;:":
            flush()
        if cur:
            chars = sum(len(x.text) + 1 for x in cur) + len(w.text)
            if (len(cur) >= MAX_WORDS or chars > MAX_CHARS
                    or w.start - cur[-1].end > GAP_BREAK):
                flush()
        cur.append(w)
    flush()
    for a, b in zip(chunks, chunks[1:]):
        a.end = min(b.start, a.end + 0.6)
    if chunks:
        chunks[-1].end = chunks[-1].end + 0.6
    return chunks


class CaptionRenderer:
    def __init__(self, words: list[Word]):
        self.chunks = group(words)
        self.font = C.font("bold", FONT_SIZE)
        self._cache: dict = {}

    def _layout(self, texts):
        f = self.font
        space = f.getlength(" ")
        widths = [f.getlength(t) for t in texts]
        total = sum(widths) + space * (len(texts) - 1)
        if total <= C.CAPTION_MAX_W or len(texts) == 1:
            return [list(range(len(texts)))], widths, space
        # split in two balanced lines
        best, best_cost = 1, 1e9
        for k in range(1, len(texts)):
            l1 = sum(widths[:k]) + space * (k - 1)
            l2 = sum(widths[k:]) + space * (len(texts) - k - 1)
            cost = max(l1, l2)
            if cost < best_cost:
                best, best_cost = k, cost
        return [list(range(best)), list(range(best, len(texts)))], widths, space

    def _sprite(self, ci: int, active: int) -> Image.Image:
        key = (ci, active)
        if key in self._cache:
            return self._cache[key]
        chunk = self.chunks[ci]
        texts = [w.text.upper().rstrip(".,;:") for w in chunk.words]
        lines, widths, space = self._layout(texts)
        f = self.font
        asc, desc = f.getmetrics()
        line_h = asc + desc + 6
        line_ws = [sum(widths[i] for i in ln) + space * (len(ln) - 1) for ln in lines]
        pad_x, pad_y = 34, 18
        sw = int(min(C.W - 40, max(line_ws) + pad_x * 2 + STROKE * 2))
        sh = int(line_h * len(lines) + pad_y * 2)
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, sw - 1, sh - 1), radius=18, fill=C.ASH + (178,))
        d.rectangle((0, 14, 7, sh - 15), fill=C.ORANGE + (255,))
        y = pad_y
        for ln, lw in zip(lines, line_ws):
            x = (sw - lw) / 2
            for i in ln:
                col = C.SULFUR if i == active else C.WHITE
                d.text((x, y), texts[i], font=f, fill=col + (255,),
                       stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
                x += widths[i] + space
            y += line_h
        self._cache[key] = img
        return img

    def draw(self, canvas: Image.Image, t: float) -> None:
        for ci, ch in enumerate(self.chunks):
            if ch.start <= t < ch.end:
                break
        else:
            return
        active = 0
        for i, w in enumerate(ch.words):
            if t >= w.start:
                active = i
        spr = self._sprite(ci, active)
        age = t - ch.start
        if age < 0.12:                     # quick pop-in
            s = 0.88 + 0.12 * (age / 0.12)
            spr = spr.resize((max(1, int(spr.width * s)), max(1, int(spr.height * s))),
                             Image.BILINEAR)
        x = (C.W - spr.width) // 2
        y = C.CAPTION_CY - spr.height // 2
        canvas.paste(spr, (x, y), spr)
