"""Single source of truth: verified facts, narration script, timing, layout, palette.

Every on-screen claim and every narrated sentence is derived from FACTS below.
Do not add details here that are not in the verified fact sheet.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ASSETS = ROOT / "assets"
FONTS = ROOT / "fonts"
DATA = ROOT / "data"

OUTPUT_VIDEO = ROOT / "output_short.mp4"
OUTPUT_VOICE = ROOT / "voiceover.mp3"
OUTPUT_VTT = ROOT / "voiceover.vtt"       # sentence-level timing (edge-tts)
OUTPUT_SRT = ROOT / "captions.srt"        # phrase-level burned-in captions
OUTPUT_WORDS = BUILD / "words.json"       # word-level timing (edge-tts WordBoundary)

# --------------------------------------------------------------------------- #
# Video format
# --------------------------------------------------------------------------- #
W, H = 1080, 1920
FPS = 30
DURATION = 45.0
N_FRAMES = int(DURATION * FPS)
AUDIO_SR = 48000

# --------------------------------------------------------------------------- #
# Channel branding
# --------------------------------------------------------------------------- #
CHANNEL = "GLOBAL NEWS 1.0"
CHANNEL_TAGLINE = "NEWS IN REAL TIME"
BREAKING_TAG = "BREAKING NEWS • PALM BEACH COUNTY, FL"
OUTRO_TEXT = "Follow Global News 1.0 for Real-Time Updates"

# --------------------------------------------------------------------------- #
# Verified facts (as supplied; nothing else is shown or narrated)
# --------------------------------------------------------------------------- #
FACTS = {
    "aircraft": "Learjet 60",
    "registration": "N722BD",
    "type": "Private jet",
    "city": "Greenacres",
    "county": "Palm Beach County",
    "state": "Florida",
    "date": "Sunday, November 1, 2026",
    "date_short": "SUN NOV 1, 2026",
    "time": "~12:50 PM EST",
    "origin": "Austin-Bergstrom International Airport (TX)",
    "origin_code": "AUS",
    "destination": "North Eleuthera Airport (Bahamas)",
    "destination_code": "ELH",
    "on_board": 9,
    "fatalities": 9,
    "fatalities_source": "U.S. Transportation Secretary Sean Duffy",
    "ground_injuries": 0,
    "ground_injuries_source": "Florida Gov. Ron DeSantis",
    "ground_injuries_note": "No immediate reports",
    "cruise_alt_ft": 35_000,
    "conditions": ["TURBULENCE", "ICING", "PRECIPITATION"],
    "dive_rate_fpm": (10_000, 30_000),
    "telemetry_start_ft": 35_250,
    "telemetry_end_ft": 8_750,
    "telemetry_window_s": 60,
    "location": "Military Trail & 10th Avenue North",
    "aftermath": "Fireball; crater left by the road",
    "evacuated": 600,
    "investigators": ["FAA", "NTSB"],
}

# Approximate coordinates (lon, lat) for the map. Airports are public reference
# points; the crash marker is the reported intersection, shown as approximate.
GEO = {
    "AUS": (-97.6699, 30.1945),
    "ELH": (-76.6835, 25.4749),
    "CRASH": (-80.1160, 26.6290),
}

# --------------------------------------------------------------------------- #
# Scenes (seconds). Narration for each scene is synthesized separately and
# placed at the scene start, so voice and graphics always line up.
# --------------------------------------------------------------------------- #
SCENES = [
    {"id": "map",       "start": 0.0,  "end": 10.0},
    {"id": "telemetry", "start": 10.0, "end": 25.0},
    {"id": "summary",   "start": 25.0, "end": 35.0},
    {"id": "investigation", "start": 35.0, "end": 45.0},
]
TRANSITION = 0.45  # seconds of cross-dissolve at each scene boundary

# Narration: tight, objective, strictly from FACTS. One block per scene.
# "lead_in" = seconds after scene start before the voice begins.
# "max_len" = hard ceiling for the spoken block; if edge-tts runs long the
# pipeline automatically re-synthesizes faster (up to MAX_RATE).
SCRIPT = [
    {
        "scene": "map", "lead_in": 0.35, "max_len": 9.4,
        "text": ("Breaking news: a private Learjet 60 has crashed in Greenacres, "
                 "Palm Beach County, Florida, on a flight from Austin, Texas, to the Bahamas."),
    },
    {
        "scene": "telemetry", "lead_in": 0.35, "max_len": 14.3,
        "text": ("At thirty-five thousand feet, pilots reported turbulence, icing, and precipitation. "
                 "The jet then entered a rapid dive, falling between ten thousand and thirty thousand feet per minute, "
                 "as the pilot declared a mayday emergency."),
    },
    {
        "scene": "summary", "lead_in": 0.3, "max_len": 9.5,
        "text": ("All nine people on board were killed, Transportation Secretary Sean Duffy confirmed. "
                 "Governor Ron DeSantis said there were no immediate reports of ground injuries."),
    },
    {
        "scene": "investigation", "lead_in": 0.25, "max_len": 9.1,
        "text": ("The jet erupted into a fireball by the road. "
                 "About six hundred residents were evacuated, and the FAA and NTSB are investigating."),
    },
]

VOICE = "en-US-ChristopherNeural"
FALLBACK_VOICE = "en-US-GuyNeural"
BASE_RATE = 8      # percent, as requested (+8%)
MAX_RATE = 20      # auto-speed ceiling if a block overflows its scene

DRONE_DB_BELOW_VOICE = 22.0   # drone RMS sits 22 dB under the voiceover RMS

# --------------------------------------------------------------------------- #
# Layout (YouTube Shorts safe zones: keep text out of the bottom ~380 px of
# channel/title UI and the right-edge action rail).
# --------------------------------------------------------------------------- #
MARGIN = 48
HEADER_Y = 96
HEADER_H = 150
BREAKING_H = 62
CONTENT_TOP = 360
CONTENT_BOTTOM = 1190
CAPTION_CENTER_Y = 1300
TICKER_Y = 1440
TICKER_H = 60
LOWER_THIRD_Y = 1180

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
NAVY_DEEP = (6, 12, 28)
NAVY = (12, 26, 58)
NAVY_MID = (22, 44, 92)
NAVY_LINE = (48, 78, 140)
RED = (206, 22, 36)
RED_DARK = (140, 10, 22)
WHITE = (255, 255, 255)
OFFWHITE = (226, 232, 242)
MUTED = (150, 166, 196)
AMBER = (255, 182, 39)
CYAN = (64, 196, 255)
LAND = (30, 48, 86)
LAND_EDGE = (78, 108, 168)
OCEAN = (8, 18, 40)

# Spoken numbers -> broadcast numerals in the burned-in captions.
CAPTION_SUBS = [
    ("thirty-five thousand", "35,000"),
    ("ten thousand", "10,000"),
    ("thirty thousand", "30,000"),
    ("six hundred", "600"),
    ("nine", "9"),
]

TICKER_ITEMS = [
    "All 9 people on board killed in Learjet 60 crash in Greenacres, FL",
    "Jet departed Austin-Bergstrom International Airport bound for North Eleuthera, Bahamas",
    "No immediate reports of injuries on the ground",
    "About 600 nearby residents evacuated",
    "FAA and NTSB investigating",
]
