"""Post-render QA: container/stream specs, full decode for errors, A/V sync,
audio loudness, and a contact sheet of sample frames for eyeballing."""
import re

from . import config as C
from .util import ffprobe_json, run, log


def verify(path=C.OUTPUT_VIDEO):
    problems = []
    info = ffprobe_json(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])

    def check(ok, msg):
        log(f"  [{'OK' if ok else 'FAIL'}] {msg}")
        if not ok:
            problems.append(msg)

    check(v is not None, "video stream present")
    check(a is not None, "audio stream present")
    if v:
        fps = eval(v["r_frame_rate"])  # e.g. "30/1"
        check((v["width"], v["height"]) == (C.W, C.H), f"resolution {v['width']}x{v['height']} (9:16)")
        check(abs(fps - C.FPS) < 0.01, f"frame rate {fps:g} fps")
        check(v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p",
              f"codec {v['codec_name']} / {v['pix_fmt']} (YouTube-safe)")
        nb = int(v.get("nb_frames", 0))
        check(abs(nb - C.N_FRAMES) <= 1, f"{nb} video frames (expected {C.N_FRAMES})")
    if a:
        check(a["codec_name"] == "aac", f"audio {a['codec_name']} {a.get('sample_rate')} Hz {a.get('channels')} ch")
        ad = float(a.get("duration", dur))
        check(abs(ad - C.DURATION) < 0.1, f"audio duration {ad:.2f}s")
    check(abs(dur - C.DURATION) < 0.1, f"container duration {dur:.2f}s")

    dec = run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])
    errs = dec.stderr.strip()
    check(not errs, "full decode with zero errors" + (f": {errs[:300]}" if errs else ""))

    lo = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a",
              "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    m_i = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)
    m_tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)
    if m_i:
        lufs, tp = float(m_i[-1]), float(m_tp[-1]) if m_tp else 0.0
        check(-16 <= lufs <= -12 and tp <= -1.0, f"loudness {lufs:.1f} LUFS, true peak {tp:.1f} dBTP")
    size = path.stat().st_size / 1e6
    log(f"  file size {size:.1f} MB, {info['format'].get('bit_rate', '?')} b/s")
    return problems


def contact_sheet(path=C.OUTPUT_VIDEO, out=C.BUILD / "contact_sheet.jpg"):
    """12 frames sampled across the video, tiled 6x2 at 1/4 scale."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
         "-vf", f"fps=12/{C.DURATION},scale=270:-1,tile=6x2:padding=6:color=0x0b1530",
         "-frames:v", "1", "-q:v", "3", str(out)])
    return out
