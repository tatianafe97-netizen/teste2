"""Editorial content: facts, script, and the timed segment plan.

Every number shown on screen or spoken aloud must come from FACTS below.
The analysis lines are framing and questions, not new factual claims.
To add a fact, add it to FACTS (with a source) and reference it by key.
"""

from dataclasses import dataclass, field

CHANNEL_NAME = "GLOBAL NEWS 1.0"
CHANNEL_TAGLINE = "NEWS IN REAL TIME"
REPORT_TITLE = "EUROPE'S AUTUMN OF REVOLT"
DATELINE = "OCT–NOV 2026"

# --------------------------------------------------------------------------
# Facts (from the editorial brief). Fill in `source` with the outlet / URL
# before publishing; validate_facts() prints a warning for any blank source.
# --------------------------------------------------------------------------
FACTS = {
    "countries": {"value": "15+", "label": "European countries mobilized", "source": ""},
    "france_oct17": {"value": 800_000, "label": "France · Oct 17 (up to)", "source": ""},
    "france_oct24": {"value": 410_000, "label": "France · Oct 24 · 289 cities & towns", "source": ""},
    "france_oct24_places": {"value": 289, "label": "cities & towns · Oct 24", "source": ""},
    "rome": {"value": 100_000, "label": "Rome (100,000+)", "source": ""},
    "madrid": {"value": 25_000, "label": "Madrid", "source": ""},
}


def validate_facts() -> list[str]:
    """Return warnings for facts that lack a source citation."""
    return [f"fact '{k}' has no source citation" for k, v in FACTS.items() if not v["source"]]


@dataclass
class Segment:
    key: str
    start: float          # seconds
    end: float            # seconds
    kind: str             # visual template: hook | counter | bars | causes | genz | question | cta
    narration: str        # spoken text (TTS)
    caption: str          # on-screen caption (may differ slightly from narration)
    data: dict = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.end - self.start


TOTAL_DURATION = 50.0
FPS = 30
WIDTH, HEIGHT = 1080, 1920

SEGMENTS: list[Segment] = [
    Segment(
        "hook", 0.0, 4.5, "hook",
        narration="Europe's workers are done waiting. From Paris to Rome, the streets are full.",
        caption="Europe's workers are done waiting.",
        data={"headline": ["EUROPE", "IS ON", "STRIKE"], "kicker": "15+ COUNTRIES · ONE WAVE"},
    ),
    Segment(
        "france", 4.5, 12.5, "counter",
        narration=("In France, up to eight hundred thousand marched on October seventeenth. "
                   "A week later, four hundred and ten thousand rallied across two hundred eighty-nine cities and towns."),
        caption="France: up to 800,000 on Oct 17 — then 410,000 across 289 towns on Oct 24.",
        data={"fact": "france_oct17", "second": "france_oct24", "title": "FRANCE"},
    ),
    Segment(
        "scale", 12.5, 20.0, "bars",
        narration=("Over one hundred thousand filled Rome. Twenty-five thousand marched in Madrid. "
                   "More than fifteen countries, one wave."),
        caption="Rome 100,000+ · Madrid 25,000 · 15+ countries.",
        data={"facts": ["france_oct17", "france_oct24", "rome", "madrid"],
              "title": "PEOPLE IN THE STREETS"},
    ),
    Segment(
        "causes", 20.0, 29.0, "causes",
        narration=("The root is material. Real wages are falling. Housing is a speculator's asset. "
                   "And austerity is choosing bombs over books."),
        caption="Falling real wages. Speculative rents. Bombs over books.",
        data={"items": [("REAL WAGES", "▼", "falling"),
                        ("RENTS", "▲", "speculation"),
                        ("BUDGETS", "⚖", "bombs over books")],
              "title": "WHY NOW"},
    ),
    Segment(
        "genz", 29.0, 36.5, "genz",
        narration=("A generation priced out of its own future is blockading campuses "
                   "and joining the picket lines."),
        caption="Gen Z students blockade campuses and join the pickets.",
        data={"headline": ["GEN Z", "BLOCKADES"], "sub": "STUDENTS + WORKERS"},
    ),
    Segment(
        "question", 36.5, 45.5, "question",
        narration=("But anger alone can be waited out. The real question is organization: "
                   "can scattered protest become coordinated, cross-border strikes that halt capital itself?"),
        caption="Can scattered anger become coordinated, cross-border working-class power?",
        data={"lines": ["STREET ANGER", "↓", "TRANSNATIONAL", "WORKER POWER?"]},
    ),
    Segment(
        "cta", 45.5, 50.0, "cta",
        narration="Follow Global News one point oh, for news in real time.",
        caption="Follow for real-time coverage.",
        data={},
    ),
]

TICKER_ITEMS = [
    "FRANCE: UP TO 800,000 ON OCT 17",
    "410,000 ACROSS 289 CITIES & TOWNS ON OCT 24",
    "ROME: 100,000+ RALLY",
    "MADRID: 25,000 MARCH",
    "15+ EUROPEAN COUNTRIES MOBILIZED",
    "BOOKS, NOT BOMBS",
]

YOUTUBE_METADATA = {
    "title": "Europe's Autumn of Revolt: Can Workers Unite Across Borders? #Shorts",
    "description": (
        "October–November 2026: hundreds of thousands march across 15+ European countries. "
        "Up to 800,000 in France on Oct 17; 410,000 across 289 cities and towns on Oct 24; "
        "100,000+ in Rome; 25,000 in Madrid.\n\n"
        "Falling real wages, speculative housing, and 'bombs over books' austerity have pushed "
        "workers and Gen Z students into the streets. The question now: can fragmented anger "
        "become coordinated, transnational working-class power?\n\n"
        "GLOBAL NEWS 1.0 — NEWS IN REAL TIME\n\n"
        "#Shorts #Europe #GeneralStrike #Labor #Protests #France #Italy #Spain #GenZ"
    ),
    "tags": ["europe protests", "general strike", "labor", "france strike", "rome protest",
             "madrid protest", "gen z", "austerity", "cost of living", "global news 1.0"],
}


def check_timeline() -> None:
    """Assert segments are contiguous and cover exactly TOTAL_DURATION."""
    t = 0.0
    for s in SEGMENTS:
        assert abs(s.start - t) < 1e-6, f"gap/overlap before segment {s.key}"
        assert s.end > s.start, f"empty segment {s.key}"
        t = s.end
    assert abs(t - TOTAL_DURATION) < 1e-6, f"timeline ends at {t}, expected {TOTAL_DURATION}"
