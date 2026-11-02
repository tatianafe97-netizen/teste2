"""Editorial content for the Poland Constitutional Tribunal Short.

The narration is split into four segments, one per scene, so every scene's
voiceover starts on its own cue (0s, 12s, 25s, 38s).

Markup: ``{Display|spoken}`` lets the captions show the correct Polish
spelling while the TTS voice gets a pronunciation-friendly respelling.
"""

# (start, end) in seconds for each of the four scenes
SCENES = [(0.0, 12.0), (12.0, 25.0), (25.0, 38.0), (38.0, 50.0)]
DURATION = 50.0
FPS = 30
WIDTH, HEIGHT = 1080, 1920

LANGS = {
    "en": {
        "voice": "en-US-ChristopherNeural",
        "rate": "+8%",
        "segments": [
            # Scene 1 - Mid-air U-turn
            "Breaking: Polish President Karol {Nawrocki|Navrotski} aborted an official "
            "flight to Senegal mid-air over southern Spain on October 30th, racing back "
            "to Warsaw on the most tracked flight on {Flightradar24|Flight Radar 24}.",
            # Scene 2 - Courtroom power struggle
            "Parliament-elected Judge Anna {Korwin-Piotrowska|Korvin Pyotrovska}, whom "
            "{Nawrocki|Navrotski} refused to swear in, took charge of the Tribunal and "
            "suspended its chief, Bogdan {Święczkowski|Shvyenchkovski}, and his deputy. "
            "Justice Minister Waldemar {Żurek|Zhoorek} wants their immunity lifted.",
            # Scene 3 - Nawrocki vs Tusk
            "{Nawrocki|Navrotski}, filmed pushing past judges at the entrance, condemned "
            "a forcible takeover of a constitutional body. Prime Minister Donald Tusk "
            "ruled out compromise: restoring the rule of law after years of "
            "{PiS|Peace} lawlessness requires decisive action.",
            # Scene 4 - European implications + CTA
            "With riot police ringing the Tribunal, Poland's rule-of-law battle, "
            "begun in 2015, is now an open standoff at the heart of Europe. Follow "
            "Global News {1.0|one point oh} for real-time updates.",
        ],
    },
    "pt": {
        "voice": "pt-BR-AntonioNeural",
        "rate": "+10%",
        "segments": [
            "Urgente: o presidente polonês Karol {Nawrocki|Navrótski} abortou em pleno "
            "voo, sobre o sul da Espanha, uma viagem ao Senegal em 30 de outubro, e "
            "voltou a Varsóvia no voo mais rastreado do {Flightradar24|Flight Radar 24}.",
            "A juíza Anna {Korwin-Piotrowska|Kórvin Piotróvska}, eleita pelo parlamento "
            "e não empossada por {Nawrocki|Navrótski}, assumiu o Tribunal e suspendeu "
            "seu presidente, Bogdan {Święczkowski|Chvientchkóvski}, e o vice. O ministro "
            "Waldemar {Żurek|Júrek} pede o fim da imunidade dos dois.",
            "{Nawrocki|Navrótski}, filmado forçando passagem entre juízes, denunciou a "
            "tomada à força de um órgão constitucional. O premiê Donald Tusk descartou "
            "acordo: restaurar o Estado de direito após anos de ilegalidade do "
            "{PiS|Pís} exige ação decisiva.",
            "Com a tropa de choque cercando o Tribunal, a batalha polonesa pelo "
            "Estado de direito, iniciada em 2015, virou um impasse aberto no coração "
            "da Europa. Siga o Global News {1.0|um ponto zero} para atualizações em "
            "tempo real.",
        ],
    },
}

TICKER = (
    "POLAND  •  Constitutional Tribunal standoff in Warsaw  •  President Nawrocki "
    "aborts Senegal trip mid-air  •  Judge Korwin-Piotrowska suspends Tribunal chief "
    "Święczkowski and deputy Sochański  •  Justice Minister Żurek seeks to lift their "
    "immunity  •  PM Tusk: “no compromise”  •  Riot police cordon the Tribunal  •  "
)
