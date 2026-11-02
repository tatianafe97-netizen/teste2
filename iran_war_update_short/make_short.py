#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 — Iran War Briefing YouTube Short generator.

Pipeline: edge-tts narration (+ word-level VTT) -> scipy newsroom pulse bed (-22 dB)
-> Pillow/matplotlib situation-room frames (+ assets/ B-roll) -> FFmpeg H.264/AAC MP4
(1080x1920, 9:16, 30 fps, 50 s).

Usage:
    python make_short.py                 # English (en-US-ChristopherNeural)
    python make_short.py --lang pt       # Portuguese (pt-BR-AntonioNeural)
    python make_short.py --stills 5,18,30,45   # preview PNG frames only
"""
import argparse
import json
import os
import subprocess
import sys
import time

import audio_bed
import content
import graphics
import tts

HERE = os.path.dirname(os.path.abspath(__file__))


def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,"
                          "display_aspect_ratio,pix_fmt,sample_rate",
                          "-of", "json", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def load_words(vtt_path):
    """Fallback: re-read word cues from an existing voiceover.vtt (for --reuse-audio)."""
    words, scene_bounds = [], content.SCENES
    with open(vtt_path, encoding="utf-8") as f:
        blocks = f.read().strip().split("\n\n")[1:]
    to_s = lambda ts: sum(float(x) * m for x, m in zip(ts.split(":"), (3600, 60, 1)))  # noqa: E731
    for b in blocks:
        lines = b.strip().splitlines()
        a, _, z = lines[1].partition(" --> ")
        st = to_s(a)
        scene = next((i for i, (s0, s1) in enumerate(scene_bounds) if s0 <= st < s1), len(scene_bounds) - 1)
        words.append({"start": st, "end": to_s(z), "text": " ".join(lines[2:]), "scene": scene})
    return words


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["en", "pt"], default="en")
    ap.add_argument("--assets", default=os.path.join(HERE, "assets"), help="folder with .mp4/.jpg B-roll")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "output"))
    ap.add_argument("--bed", choices=["scipy", "lavfi"], default="scipy", help="newsroom pulse generator")
    ap.add_argument("--reuse-audio", action="store_true", help="reuse existing voiceover.mp3/.vtt (offline re-render)")
    ap.add_argument("--stills", default="", help="comma-separated timestamps: write preview PNGs and exit")
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()

    lang = args.lang
    L = content.LABELS[lang]
    suffix = "" if lang == "en" else "_pt"
    os.makedirs(args.out_dir, exist_ok=True)
    build = os.path.join(HERE, "build", lang)
    os.makedirs(build, exist_ok=True)
    out_mp3 = os.path.join(args.out_dir, f"voiceover{suffix}.mp3")
    out_vtt = os.path.join(args.out_dir, f"voiceover{suffix}.vtt")
    out_mp4 = os.path.join(args.out_dir, f"iran_war_short{suffix}.mp4")
    segments = content.NARRATION[lang]
    D = content.DURATION

    t0 = time.time()
    print(f"[1/4] Voiceover ({content.VOICES[lang]}, rate {content.RATE})")
    if args.reuse_audio and os.path.exists(out_mp3) and os.path.exists(out_vtt):
        vo_wav = os.path.join(build, "voiceover.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_mp3, "-ac", "1", "-ar", "48000", vo_wav], check=True)
        words = load_words(out_vtt)
        print(f"  reused {out_mp3}")
    else:
        vo_wav, words = tts.build_voiceover(segments, content.SCENES, D, content.VOICES[lang], content.RATE,
                                            build, out_mp3, out_vtt)
    with open(os.path.join(args.out_dir, f"script{suffix}.txt"), "w", encoding="utf-8") as f:
        for (a, b), seg in zip(content.SCENES, segments):
            f.write(f"[{a:04.1f}s-{b:04.1f}s] {seg}\n")
    print(f"  {len(words)} word cues -> {out_vtt}")

    print(f"[2/4] Newsroom pulse bed ({args.bed}, {audio_bed.BED_GAIN_DB:.0f} dB)")
    bed_wav = audio_bed.write_bed(os.path.join(build, "bed.wav"), D, args.bed)

    print("[3/4] Graphics")
    r = graphics.Renderer(L, lang, content.SCENES, D, words, segments, args.assets)

    if args.stills:
        for ts in [float(x) for x in args.stills.split(",") if x.strip()]:
            p = os.path.join(build, f"still_{ts:05.2f}.png")
            r.frame(ts).save(p)
            print(f"  wrote {p}")
        return

    n_frames = int(round(D * graphics.FPS))
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{graphics.W}x{graphics.H}", "-r", str(graphics.FPS),
           "-i", "-", "-i", vo_wav, "-i", bed_wav,
           "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest:normalize=0,"
                              "alimiter=limit=0.95,aresample=48000[a]",
           "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-r", str(graphics.FPS), "-aspect", "9:16",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{D:.3f}", "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n_frames):
        proc.stdin.write(r.frame(i / graphics.FPS).tobytes())
        if i % 150 == 0:
            el = time.time() - t0
            print(f"  frame {i:4d}/{n_frames}  ({el:5.1f}s elapsed)", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg encoding failed")

    print("[4/4] Verify")
    info = ffprobe(out_mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    dur = float(info["format"]["duration"])
    num, den = map(int, v["r_frame_rate"].split("/"))
    checks = {
        "resolution 1080x1920": (v["width"], v["height"]) == (1080, 1920),
        "30 fps": abs(num / den - 30) < 0.01,
        "duration ~50s": abs(dur - D) < 0.2,
        "h264/yuv420p": v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p",
        "aac audio": a["codec_name"] == "aac",
    }
    for k, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {k}")
    print(f"  {out_mp4}  {os.path.getsize(out_mp4) / 1e6:.1f} MB, {dur:.2f}s, built in {time.time() - t0:.0f}s")
    if not all(checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
