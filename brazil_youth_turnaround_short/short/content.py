"""Editorial content: facts, narration script and on-screen copy (EN / PT-BR).

Every number shown or spoken comes from FACTS so the graphics and the
voiceover can never drift apart.
"""

FACTS = {
    "r1_date": "OCT 4, 2026",
    "r2_date": "OCT 25, 2026",
    "flavio_pct": 47.03,
    "flavio_votes_m": 56.1,
    "lula_pct": 45.16,
    "lula_votes_m": 53.8,
    "youth_eligible_m": 19.2,
    "youth_voted_r1_m": 14.9,
    "abstention_r1": 21.08,
    "abstention_r2": 19.2,
    "municipalities_abst_down_pct": 80,
    "r2_turnout_m": 128.2,
}

# Scene windows in seconds (start, end). Total runtime: 50 s.
SCENES = [(0.0, 12.0), (12.0, 25.0), (25.0, 38.0), (38.0, 50.0)]
DURATION = 50.0

VOICES = {
    "en": "en-US-ChristopherNeural",
    "pt": "pt-BR-AntonioNeural",
}

# One narration block per scene; each block is synthesised separately and
# anchored to the start of its scene, so picture and voice stay locked.
NARRATION = {
    "en": [
        "October fourth. Round one. Flávio Bolsonaro, 47.03 percent. Lula, 45.16. "
        "Behind. But 19.2 million young voters were in play.",

        "Then the streets answered. Assemblies. Debates. Rallies. Feeds on fire. "
        "Free transit on election day. Abstention fell in 80 percent of municipalities. "
        "128.2 million voted.",

        "October twenty-fifth. The runoff. For the first time in Brazilian history, "
        "the round-one runner-up overturned the result. "
        "Lula wins a fourth term, and credits the youth in the streets.",

        "But a ballot is only the starting line. Transit as a right. Youth with real power. "
        "Popular participation. An end to structural inequality. The vote opened the door. Mobilization walks through it.",
    ],
    "pt": [
        "Quatro de outubro. Primeiro turno. Flávio Bolsonaro, 47,03 por cento. Lula, 45,16. "
        "Atrás. Mas 19,2 milhões de jovens podiam decidir.",

        "Então as ruas responderam. Assembleias. Debates. Atos. Redes em chamas. "
        "Transporte grátis no dia da eleição. A abstenção caiu em 80 por cento dos municípios. "
        "128,2 milhões votaram.",

        "Vinte e cinco de outubro. O segundo turno. Pela primeira vez na história do Brasil, "
        "quem ficou em segundo virou o resultado. "
        "Lula conquista o quarto mandato, e agradece à juventude nas ruas.",

        "Mas o voto é só a linha de largada. Transporte como direito. Juventude com poder real. "
        "Participação popular. Fim da desigualdade estrutural. O voto abriu a porta. A mobilização atravessa.",
    ],
}

# On-screen copy. Keys are referenced by short/visuals.py.
TEXT = {
    "en": {
        "banner_1": "GLOBAL NEWS 1.0  •  SPECIAL REPORT:",
        "banner_2": "BRAZIL'S YOUTH UPRISING",
        "live": "LIVE",
        "channel": "NEWS IN REAL TIME",
        "ticker": "BRAZIL 2026 RUNOFF  •  YOUTH TURNOUT SURGE  •  ABSTENTION DOWN IN 80% OF MUNICIPALITIES  "
                  "•  FREE TRANSIT ON ELECTION DAY  •  FIRST RUNOFF COMEBACK IN BRAZILIAN PRESIDENTIAL HISTORY  •  ",
        # scene 1
        "s1_kicker": "01 / THE FIRST-ROUND DEFICIT",
        "s1_title": "ROUND 1  ·  OCT 4, 2026",
        "s1_flavio": "FLÁVIO BOLSONARO (PL)",
        "s1_lula": "LULA (PT)",
        "s1_votes": "{v}M VOTES",
        "s1_gap": "GAP: {pts} PTS  ·  {votes}M VOTES",
        "s1_youth_head": "THE YOUTH ELECTORATE",
        "s1_youth_sub": "ELIGIBLE VOTERS AGED 16–24",
        "s1_youth_voted": "{v}M VOTED IN ROUND 1",
        # scene 2
        "s2_kicker": "02 / THE GRASSROOTS SURGE",
        "s2_words": ["ASSEMBLIES.", "DEBATES.", "RALLIES.", "FEEDS ON FIRE."],
        "s2_words_sub": ["UNIVERSITIES", "SCHOOLS", "STREETS", "SOCIAL MEDIA"],
        "s2_waffle_head": "ABSTENTION FELL IN",
        "s2_waffle_sub": "OF MUNICIPALITIES",
        "s2_waffle_note": "EACH SQUARE = 1% OF MUNICIPALITIES",
        "s2_chart_head": "ABSTENTION RATE",
        "s2_r1": "ROUND 1",
        "s2_r2": "ROUND 2",
        "s2_turnout": "AT THE POLLS IN ROUND 2",
        "s2_transit": "FREE PUBLIC TRANSIT ON ELECTION DAY",
        # scene 3
        "s3_kicker": "03 / THE HISTORIC COMEBACK",
        "s3_nodes": [
            ("OCT 4", "ROUND 1", "LULA FINISHES SECOND — 45.16%"),
            ("OCT 5–24", "THE MOBILIZATION", "STREETS · CAMPUSES · SCHOOLS · FEEDS"),
            ("OCT 25", "THE RUNOFF", "LULA OVERTURNS THE RESULT"),
        ],
        "s3_stamp_1": "FIRST IN HISTORY",
        "s3_stamp_2": "2ND-PLACE ROUND 1 FINISHER WINS THE RUNOFF",
        "s3_term": "4TH TERM",
        "s3_quote": "LULA CREDITS BRAZIL'S YOUTH FOR TAKING TO THE STREETS",
        # scene 4
        "s4_kicker": "04 / STRUCTURAL REALITY",
        "s4_title": "THE BALLOT IS THE",
        "s4_title_2": "STARTING LINE",
        "s4_col_a": "INSTITUTIONAL POLITICS",
        "s4_col_b": "GRASSROOTS DEMANDS",
        "s4_rows": [
            ("TRANSIT AS A PRIVILEGE", "TRANSIT AS A RIGHT"),
            ("YOUTH AS VOTERS", "YOUTH WITH REAL POWER"),
            ("TOP-DOWN DECISIONS", "POPULAR PARTICIPATION"),
            ("INEQUALITY MANAGED", "INEQUALITY ENDED"),
        ],
        "s4_final_1": "STAY MOBILIZED",
        "s4_final_2": "BEYOND THE BALLOT BOX",
        "sign_off": "GLOBAL NEWS 1.0  —  NEWS IN REAL TIME",
    },
    "pt": {
        "banner_1": "GLOBAL NEWS 1.0  •  REPORTAGEM ESPECIAL:",
        "banner_2": "A REVOLTA DA JUVENTUDE BRASILEIRA",
        "live": "AO VIVO",
        "channel": "NOTÍCIAS EM TEMPO REAL",
        "ticker": "SEGUNDO TURNO 2026  •  JUVENTUDE NAS URNAS  •  ABSTENÇÃO CAI EM 80% DOS MUNICÍPIOS  "
                  "•  TRANSPORTE GRATUITO NO DIA DA ELEIÇÃO  •  PRIMEIRA VIRADA DA HISTÓRIA NO SEGUNDO TURNO  •  ",
        "s1_kicker": "01 / A DESVANTAGEM DO 1º TURNO",
        "s1_title": "1º TURNO  ·  4 OUT 2026",
        "s1_flavio": "FLÁVIO BOLSONARO (PL)",
        "s1_lula": "LULA (PT)",
        "s1_votes": "{v} MI DE VOTOS",
        "s1_gap": "DIFERENÇA: {pts} PTS  ·  {votes} MI DE VOTOS",
        "s1_youth_head": "O ELEITORADO JOVEM",
        "s1_youth_sub": "ELEITORES APTOS DE 16 A 24 ANOS",
        "s1_youth_voted": "{v} MI VOTARAM NO 1º TURNO",
        "s2_kicker": "02 / A ONDA DE BASE",
        "s2_words": ["ASSEMBLEIAS.", "DEBATES.", "ATOS.", "REDES EM CHAMAS."],
        "s2_words_sub": ["UNIVERSIDADES", "ESCOLAS", "RUAS", "REDES SOCIAIS"],
        "s2_waffle_head": "A ABSTENÇÃO CAIU EM",
        "s2_waffle_sub": "DOS MUNICÍPIOS",
        "s2_waffle_note": "CADA QUADRADO = 1% DOS MUNICÍPIOS",
        "s2_chart_head": "TAXA DE ABSTENÇÃO",
        "s2_r1": "1º TURNO",
        "s2_r2": "2º TURNO",
        "s2_turnout": "NAS URNAS NO 2º TURNO",
        "s2_transit": "TRANSPORTE PÚBLICO GRATUITO NO DIA DA ELEIÇÃO",
        "s3_kicker": "03 / A VIRADA HISTÓRICA",
        "s3_nodes": [
            ("4 OUT", "1º TURNO", "LULA TERMINA EM SEGUNDO — 45,16%"),
            ("5–24 OUT", "A MOBILIZAÇÃO", "RUAS · CAMPI · ESCOLAS · REDES"),
            ("25 OUT", "O 2º TURNO", "LULA VIRA O RESULTADO"),
        ],
        "s3_stamp_1": "INÉDITO NA HISTÓRIA",
        "s3_stamp_2": "2º COLOCADO NO 1º TURNO VENCE O 2º TURNO",
        "s3_term": "4º MANDATO",
        "s3_quote": "LULA AGRADECE À JUVENTUDE QUE FOI ÀS RUAS",
        "s4_kicker": "04 / REALIDADE ESTRUTURAL",
        "s4_title": "O VOTO É A",
        "s4_title_2": "LINHA DE LARGADA",
        "s4_col_a": "POLÍTICA INSTITUCIONAL",
        "s4_col_b": "DEMANDAS POPULARES",
        "s4_rows": [
            ("TRANSPORTE COMO PRIVILÉGIO", "TRANSPORTE COMO DIREITO"),
            ("JOVENS COMO ELEITORES", "JUVENTUDE COM PODER REAL"),
            ("DECISÕES DE CIMA", "PARTICIPAÇÃO POPULAR"),
            ("DESIGUALDADE GERIDA", "DESIGUALDADE SUPERADA"),
        ],
        "s4_final_1": "SEGUIR MOBILIZADO",
        "s4_final_2": "ALÉM DA URNA",
        "sign_off": "GLOBAL NEWS 1.0  —  NOTÍCIAS EM TEMPO REAL",
    },
}


def fmt_num(x, lang, decimals=None):
    """Format a number with the locale's decimal separator."""
    s = f"{x:.{decimals}f}" if decimals is not None else f"{x}"
    return s.replace(".", ",") if lang == "pt" else s
