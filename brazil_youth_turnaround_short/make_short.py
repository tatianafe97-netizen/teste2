#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 — 'Brazil's Youth Uprising' 50-second vertical Short.

    python make_short.py               # English (en-US-ChristopherNeural)
    python make_short.py --lang pt     # Portuguese (pt-BR-AntonioNeural)

Pipeline: edge-tts narration + word timings -> scipy documentary pulse -> optional
graded B-roll from assets/ -> Pillow/matplotlib frames piped into FFmpeg -> MP4.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from short import audio, broll, voice  # noqa: E402
from short.content import DURATION, NARRATION, SCENES, VOICES  # noqa: E402

W, H = 1080, 1920


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["en", "pt"], default="en")
    ap.add_argument("--rate", default="+8%", help="edge-tts speaking rate (default +8%%)")
    ap.add_argument("--voice", default=None, help="override edge-tts voice")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--assets", default=str(ROOT / "assets"))
    ap.add_argument("--pulse-db", type=float, default=-20.0, help="pulse bed level in dBFS RMS")
    ap.add_argument("--out", default=None, help="output MP4 path")
    ap.add_argument("--crf", type=int, default=21)
    ap.add_argument("--maxrate", default="8M", help="x264 VBV max bitrate (keeps grain from bloating the file)")
    ap.add_argument("--preview", type=float, default=None,
                    help="render only the first N seconds (quick look)")
    args = ap.parse_args()

    lang = args.lang
    suffix = "" if lang == "en" else f"_{lang}"
    out = Path(args.out) if args.out else ROOT / f"brazil_youth_short{suffix}.mp4"
    build = ROOT / "build" / lang
    build.mkdir(parents=True, exist_ok=True)
    voice_name = args.voice or VOICES[lang]
    t0 = time.time()

    # 1. narration ------------------------------------------------------------------
    print(f"[1/5] edge-tts narration ({voice_name}, rate {args.rate})")
    segments = []
    for i, text in enumerate(NARRATION[lang]):
        mp3 = build / f"vo_scene{i + 1}.mp3"
        words = voice.synthesize(text, voice_name, args.rate, mp3)
        segments.append((mp3, words))
    vo, words = audio.assemble_narration(segments, SCENES, DURATION)
    vo_wav = build / "voiceover.wav"
    audio.write_wav(vo_wav, vo)
    vo_mp3 = ROOT / f"voiceover{suffix}.mp3"
    vtt = ROOT / f"voiceover{suffix}.vtt"
    audio.encode_mp3(vo_wav, vo_mp3)
    audio.write_vtt(vtt, words)
    (build / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1))
    print(f"      -> {vo_mp3.name}, {vtt.name} ({len(words)} word cues)")

    # 2. pulse + mix ----------------------------------------------------------------
    print(f"[2/5] documentary pulse at {args.pulse_db:+.0f} dBFS + mix")
    pulse = audio.documentary_pulse(DURATION, SCENES, level_db=args.pulse_db)
    audio.write_wav(build / "pulse.wav", pulse)
    mix = audio.soft_limit(vo + pulse)
    mix_wav = build / "mix.wav"
    audio.write_wav(mix_wav, mix)

    # 3. b-roll ---------------------------------------------------------------------
    assets = broll.find_assets(args.assets)
    reader = None
    if assets:
        print(f"[3/5] B-roll: {len(assets)} file(s) from {args.assets} -> graded plate")
        plate = broll.build_broll(assets, build / "broll.mp4", DURATION, W, H, args.fps)
        reader = broll.FrameReader(plate, W, H)
    else:
        print("[3/5] B-roll: none found in assets/ -> charcoal documentary plate")

    # 4. frames -> ffmpeg -----------------------------------------------------------
    from short.visuals import Compositor
    dur = min(DURATION, args.preview) if args.preview else DURATION
    n_frames = int(round(dur * args.fps))
    print(f"[4/5] rendering {n_frames} frames @ {args.fps}fps {W}x{H}")
    comp = Compositor(lang, args.fps, words, DURATION, reader)
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(args.fps), "-i", "-",
           "-i", str(mix_wav),
           "-map", "0:v", "-map", "1:a", "-t", f"{dur:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf), "-maxrate", args.maxrate, "-bufsize", "16M", "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-r", str(args.fps), "-g", str(args.fps * 2),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    tr = time.time()
    try:
        for i in range(n_frames):
            proc.stdin.write(comp.frame(i).tobytes())
            if i % (args.fps * 5) == 0:
                el = time.time() - tr
                eta = el / (i + 1) * (n_frames - i - 1)
                print(f"      frame {i:5d}/{n_frames}  ({el:5.1f}s elapsed, ~{eta:4.0f}s left)", flush=True)
    finally:
        proc.stdin.close()
        rc = proc.wait()
        if reader:
            reader.close()
    if rc != 0:
        sys.exit(f"ffmpeg failed with exit code {rc}")

    # 5. verify ---------------------------------------------------------------------
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size",
                            "-of", "json", str(out)], capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    print(f"[5/5] {out.name}: {v['width']}x{v['height']} {v['codec_name']} {v['r_frame_rate']}fps, "
          f"{float(info['format']['duration']):.2f}s, {int(info['format']['size']) / 1e6:.1f} MB "
          f"(total {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
