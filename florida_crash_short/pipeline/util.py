import json
import subprocess
import sys


def log(msg):
    print(msg, flush=True)


def run(cmd, **kw):
    """Run a command; on failure show the tail of stderr so FFmpeg errors are readable."""
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if res.returncode != 0:
        tail = "\n".join((res.stderr or res.stdout).strip().splitlines()[-25:])
        raise RuntimeError(f"command failed ({res.returncode}): {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    return res


def ffprobe_json(path):
    res = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", str(path)])
    return json.loads(res.stdout)


def ffprobe_duration(path):
    return float(ffprobe_json(path)["format"]["duration"])
