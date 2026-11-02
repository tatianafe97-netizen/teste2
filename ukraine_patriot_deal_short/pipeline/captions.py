"""Burned-in broadcast subtitles driven by edge-tts word timings."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageDraw

from .config import W, CAPTION_CENTER_Y, CAPTION_MAX_W, AMBER, WHITE, BLACK, font, rgba
from .draw import ease_out, prog
from .tts import Word

MAX_WORDS = 3
MAX_CHARS = 20
BASE_SIZE = 74
STROKE = 7
LINE_GAP = 10


@dataclass
class Phrase:
    words: list[Word]
    start: float
    end: float


def build_phrases(words: list[Word]) -> list[Phrase]:
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        chars = sum(len(x.text) + 1 for x in cur) + len(w.text)
        gap = (w.start - cur[-1].end) if cur else 0
        if cur and (len(cur) >= MAX_WORDS or chars > MAX_CHARS or gap > 0.28 or w.scene != cur[-1].scene):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    phrases = []
    for i, g in enumerate(groups):
        nxt = groups[i + 1][0].start if i + 1 < len(groups) else g[-1].end + 0.6
        end = min(nxt - 0.02, g[-1].end + 0.45)
        phrases.append(Phrase(g, g[0].start - 0.04, end))
    return phrases


class CaptionRenderer:
    def __init__(self, words: list[Word]):
        self.phrases = build_phrases(words)
        self._i = 0

    def _current(self, t: float) -> Phrase | None:
        # frames are rendered in order, so walk forward from the last hit
        while self._i < len(self.phrases) - 1 and t >= self.phrases[self._i + 1].start:
            self._i += 1
        for j in (self._i, max(0, self._i - 1)):
            p = self.phrases[j] if self.phrases else None
            if p and p.start <= t < p.end:
                return p
        return None

    def draw(self, img, t: float) -> None:
        ph = self._current(t)
        if ph is None:
            return
        d = ImageDraw.Draw(img, "RGBA")
        pop = ease_out(prog(t, ph.start, 0.12))
        size = BASE_SIZE
        tokens = [w.text.upper() for w in ph.words]

        def layout(sz):
            f = font("black", sz)
            space = f.getlength(" ")
            lines, cur, cur_w = [], [], 0.0
            for k, tok in enumerate(tokens):
                tw = f.getlength(tok)
                if cur and cur_w + space + tw > CAPTION_MAX_W:
                    lines.append((cur, cur_w))
                    cur, cur_w = [], 0.0
                cur_w = cur_w + (space if cur else 0) + tw
                cur.append(k)
            lines.append((cur, cur_w))
            return f, space, lines

        f, space, lines = layout(size)
        while (len(lines) > 2 or max(w for _, w in lines) > CAPTION_MAX_W) and size > 40:
            size -= 4
            f, space, lines = layout(size)
        scale = 0.9 + 0.1 * pop
        if scale < 0.999:
            f, space, lines = layout(int(size * scale))
        lh = f.size + LINE_GAP
        total_h = lh * len(lines) - LINE_GAP
        y = CAPTION_CENTER_Y - total_h / 2

        # active word index (karaoke highlight)
        active = 0
        for k, w in enumerate(ph.words):
            if t >= w.start - 0.03:
                active = k
        widest = max(w for _, w in lines)
        pad = 26
        d.rounded_rectangle(((W - widest) / 2 - pad, y - 18, (W + widest) / 2 + pad, y + total_h + 22),
                            radius=14, fill=rgba(BLACK, 120 * pop))
        for idxs, lw in lines:
            x = (W - lw) / 2
            for k in idxs:
                tok = tokens[k]
                color = AMBER if k == active else WHITE
                d.text((x, y + f.size / 2), tok, font=f, anchor="lm", fill=rgba(color, 255 * pop),
                       stroke_width=STROKE, stroke_fill=rgba(BLACK, 255 * pop))
                x += f.getlength(tok) + space
            y += lh
