"""matplotlib timeline: Ukraine's immediate need vs. 2030s new-build deliveries."""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image

from .config import AMBER, CYAN, CYAN_DIM, NATO_LIGHT, NAVY_DEEP, GREY, WHITE, font_path, hexc

CHART_W, CHART_H = 980, 400
YEAR0, YEAR1 = 2026.0, 2033.0
NOW = 2026 + 10 / 12          # November 2026
DECADE = 2030.0
_AX = (0.04, 0.11, 0.93, 0.87)  # left, bottom, width, height (figure fraction)
_YLIM = (-0.62, 2.78)
LANES = {"need": 2, "prod": 1, "plan": 0}
BAR_H = 0.40


def chart_x(year: float) -> float:
    l, _, w, _ = _AX
    return CHART_W * (l + w * (year - YEAR0) / (YEAR1 - YEAR0))


def chart_y(lane_value: float) -> float:
    _, b, _, h = _AX
    frac = (lane_value - _YLIM[0]) / (_YLIM[1] - _YLIM[0])
    return CHART_H * (1 - (b + h * frac))


def _fp(style: str, size: float) -> FontProperties:
    return FontProperties(fname=font_path(style), size=size)


def _bar(ax, x0, x1, lane, color, alpha=1.0, hatch=None, label=None, tcolor=None, edge=None):
    y = LANES[lane] - BAR_H / 2
    ax.add_patch(plt.Rectangle((x0, y), x1 - x0, BAR_H, fc=color if not hatch else "none",
                               ec=edge or color, lw=1.6, alpha=alpha, hatch=hatch, zorder=3))
    if label:
        box = dict(boxstyle="square,pad=0.25", fc=hexc(NAVY_DEEP), ec="none", alpha=0.9) if hatch else None
        ax.text(x0 + 0.08, LANES[lane], label, va="center", ha="left", bbox=box,
                color=tcolor or hexc(NAVY_DEEP), fontproperties=_fp("xbold", 12.5), zorder=5)


def render_timeline(T: dict) -> tuple[Image.Image, Image.Image]:
    """Returns (base layer, proposal-lane layer), both RGBA CHART_W x CHART_H."""
    layers = []
    for part in ("base", "plan"):
        fig = plt.figure(figsize=(CHART_W / 100, CHART_H / 100), dpi=100)
        fig.patch.set_alpha(0)
        ax = fig.add_axes(_AX)
        ax.set_xlim(YEAR0, YEAR1)
        ax.set_ylim(*_YLIM)
        ax.patch.set_alpha(0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_yticks([])
        if part == "base":
            ax.axvspan(DECADE, YEAR1, color=hexc(CYAN), alpha=0.07, zorder=0)
            ax.text((DECADE + YEAR1) / 2, 2.62, T["s3_2030s"], ha="center", va="center",
                    color=hexc(CYAN), fontproperties=_fp("mono", 14), alpha=0.9)
            for yr in range(2026, 2033):
                ax.axvline(yr, color=hexc(CYAN), lw=0.6, alpha=0.12, zorder=0)
            ax.set_xticks(range(2026, 2034))
            ax.set_xticklabels([str(y) for y in range(2026, 2033)] + ["→"])
            for lbl in ax.get_xticklabels():
                lbl.set_fontproperties(_fp("mono", 12.5))
                lbl.set_color(hexc(GREY))
            ax.tick_params(axis="x", length=6, color=hexc(CYAN_DIM), pad=4)
            ax.spines["bottom"].set_visible(True)
            ax.spines["bottom"].set_color(hexc(CYAN_DIM))
            for key, lane in (("need", 0), ("prod", 1)):
                ax.text(YEAR0 + 0.03, LANES[key] + BAR_H / 2 + 0.17, T["s3_lanes"][lane],
                        color=hexc(WHITE), fontproperties=_fp("mono", 12), va="center")
            _bar(ax, YEAR0, YEAR1, "need", hexc(AMBER), label=T["s3_need"])
            _bar(ax, NOW, DECADE, "prod", hexc(GREY), hatch="////", alpha=0.8,
                 label=T["s3_leadtime"], tcolor=hexc(WHITE))
            # soft gradient onset: the exact first-delivery year is not public
            steps = 48
            for i in range(steps):
                x0 = DECADE + i * 0.016
                ax.add_patch(plt.Rectangle((x0, LANES["prod"] - BAR_H / 2), 0.017, BAR_H,
                                           fc=hexc(CYAN), ec="none", alpha=(i + 1) / steps, zorder=3))
            x_full = DECADE + steps * 0.016
            ax.add_patch(plt.Rectangle((x_full, LANES["prod"] - BAR_H / 2), YEAR1 - x_full, BAR_H,
                                       fc=hexc(CYAN), ec="none", zorder=3))
            ax.text(DECADE + 0.35, LANES["prod"], T["s3_delivery"], va="center", ha="left",
                    color=hexc(NAVY_DEEP), fontproperties=_fp("xbold", 12.5), zorder=5)
        else:
            ax.set_xticks([])
            ax.text(YEAR0 + 0.03, LANES["plan"] + BAR_H / 2 + 0.17, T["s3_lanes"][2],
                    color=hexc(WHITE), fontproperties=_fp("mono", 12), va="center")
            _bar(ax, NOW, 2028.45, "plan", hexc(NATO_LIGHT), label=T["s3_swap"], tcolor=hexc(WHITE))
            ax.annotate("", xy=(2028.9, LANES["plan"]), xytext=(2028.4, LANES["plan"]),
                        arrowprops=dict(arrowstyle="-|>", color=hexc(NATO_LIGHT), lw=2.4, mutation_scale=22))
            _bar(ax, DECADE, YEAR1, "plan", hexc(CYAN), hatch="\\\\\\\\", alpha=0.9,
                 label=T["s3_backfill"], tcolor=hexc(CYAN))
        fig.canvas.draw()
        arr = np.asarray(fig.canvas.buffer_rgba()).copy()
        plt.close(fig)
        layers.append(Image.fromarray(arr, "RGBA"))
    return layers[0], layers[1]
