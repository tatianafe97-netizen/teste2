"""Editorial content for the GLOBAL NEWS 1.0 Iran War briefing Short.

All figures below were provided as the verified fact sheet for the November 2026
update. Every claim is attributed to its source (IRGC, FM Araghchi, President Trump,
Secretary Rubio, Iran's army, Houthi claims) so the broadcast stays objective.
"""

CHANNEL = "GLOBAL NEWS 1.0 - NEWS IN REAL TIME"

FACTS = {
    "war_start": "Feb 28, 2026",
    "war_cost": "$47.1B",
    "brent": 116.72,
    "tankers": 2,
    "depth_m": 100,
    "depth_ft": 300,
}

# Scene windows in seconds (start, end). Total runtime = 50 s.
SCENES = [(0.0, 12.0), (12.0, 25.0), (25.0, 38.0), (38.0, 50.0)]
DURATION = 50.0

VOICES = {"en": "en-US-ChristopherNeural", "pt": "pt-BR-AntonioNeural"}
RATE = "+8%"

# One narration block per scene so the voice is locked to the visuals.
NARRATION = {
    "en": [
        "Breaking: in the Strait of Hormuz, the IRGC says two oil tankers exploded "
        "after hitting mines on an unauthorized route. Brent crude is at $116.72 a barrel.",

        "Trump says the war will end very soon, but wants one or two more targets, "
        "like Pickaxe Mountain, south of Natanz, buried over 300 feet deep. "
        "Estimated US cost: $47.1 billion.",

        "FM Araghchi says Qatar-mediated talks produced a Two-Day Plan: US measures on "
        "Day 1, Hormuz reopens on Day 2. Saudi defenses intercepted drones after "
        "Houthi claims on Ras Tanura and Abqaiq.",

        "Secretary Marco Rubio says Trump prefers a diplomatic resolution. Iran's army "
        "warns a renewed war could last longer. Follow Global News 1.0 for real-time updates.",
    ],
    "pt": [
        "Urgente: em Ormuz, a Guarda Revolucionária diz que dois petroleiros explodiram "
        "ao atingir minas numa rota não autorizada. O Brent está a 116,72 dólares.",

        "Trump diz que a guerra acaba muito em breve, mas quer mais um ou dois alvos, "
        "como Pickaxe Mountain, ao sul de Natanz, a mais de 100 metros. "
        "Custo estimado: 47,1 bilhões.",

        "O chanceler Araghchi diz que o Catar mediou um Plano de Dois Dias: medidas dos "
        "EUA no Dia 1, Ormuz reaberto no Dia 2. A Arábia Saudita interceptou drones "
        "após ameaças houthis a Ras Tanura e Abqaiq.",

        "Marco Rubio diz que Trump prefere a diplomacia. O exército iraniano alerta que "
        "uma nova guerra pode durar mais. Siga o Global News 1.0.",
    ],
}

# On-screen labels per language.
LABELS = {
    "en": {
        "brand": "GLOBAL NEWS 1.0",
        "desk": "MIDDLE EAST DESK: IRAN WAR BRIEFING",
        "live": "LIVE",
        "date": "NOV 02 2026",
        "day_of_war": "WAR DAY {n} • SINCE FEB 28, 2026",
        "s1_title": "STRAIT OF HORMUZ • CHOKEPOINT",
        "s1_mine": "MINE STRIKE",
        "s1_tanker": "TANKER {n}",
        "s1_unauth": "UNAUTHORIZED ROUTE",
        "s1_lane": "SHIPPING LANE",
        "s1_src": "SOURCE: IRGC • POSITIONS ILLUSTRATIVE",
        "s1_brent": "BRENT CRUDE",
        "s1_bbl": "/BBL",
        "s1_tankers_hit": "2 TANKERS EXPLODED",
        "countries": {"IRAN": "IRAN", "SAUDI": "SAUDI ARABIA", "QATAR": "QATAR",
                      "UAE": "UAE", "OMAN": "OMAN", "GULF": "PERSIAN GULF",
                      "OMANGULF": "GULF OF OMAN", "STRAIT": "STRAIT OF HORMUZ"},
        "s2_title": "PICKAXE MOUNTAIN • DEPTH PROFILE",
        "s2_name": "KŪH-E KOLANG GAZ LĀ",
        "s2_loc": "SOUTH OF NATANZ • ZAGROS RANGE",
        "s2_depth": "DEPTH",
        "s2_depth_val": ">100 M / 300+ FT",
        "s2_tunnels": "TUNNEL COMPLEX",
        "s2_surface": "SURFACE",
        "s2_cost": "EST. US WAR COST",
        "s2_cost_sub": "TO US TAXPAYERS",
        "s2_quote": "TRUMP: WAR TO END\n\"VERY SOON,\" WANTS\n\"ONE OR TWO\" MORE\nTARGETS",
        "s2_target": "TARGET OF INTEREST",
        "s3_title": "QATAR-MEDIATED \"TWO-DAY PLAN\"",
        "s3_by": "ANNOUNCED BY IRANIAN FM ABBAS ARAGHCHI",
        "s3_day1": "DAY 1",
        "s3_day1_txt": "US\nMEASURES",
        "s3_day2": "DAY 2",
        "s3_day2_txt": "HORMUZ\nREOPENS",
        "s3_day2_sub": "NORMAL NAVIGATION",
        "s3_day1_sub": "FIRST STEP",
        "s3_status": "STATUS: PROPOSED",
        "s3_alert": "REGIONAL ALERT • SAUDI ARABIA",
        "s3_alert_txt": "Air defenses intercepted drones after\nHouthi claims on oil facilities",
        "s3_rt": "RAS TANURA",
        "s3_ab": "ABQAIQ",
        "s1_badge_sub": "IRGC • STRAIT OF HORMUZ",
        "s2_schem": "ZAGROS MOUNTAINS • SCHEMATIC, NOT TO SCALE",
        "s3_doha": "DOHA • QATAR-MEDIATED TALKS",
        "s3_claimed": "TARGETS CLAIMED:",
        "s3_source": "SOURCE: HOUTHI CLAIMS / SAUDI DEFENSE",
        "s3_inset": "SAUDI ARABIA • EASTERN PROVINCE",
        "s4_title": "DIPLOMACY vs. ESCALATION",
        "s4_us": "UNITED STATES",
        "s4_ir": "IRAN",
        "s4_us_pts": ["TRUMP: War will end\n\"very soon\"",
                      "Wants \"one or two\"\nmore targets",
                      "RUBIO: Trump prefers a\ndiplomatic resolution"],
        "s4_ir_pts": ["FM ARAGHCHI: Qatar-\nmediated \"Two-Day Plan\"",
                      "ARMY: Renewed war\ncould last longer"],
        "s4_dip": "DIPLOMACY",
        "s4_esc": "ESCALATION",
        "s4_follow": "FOLLOW GLOBAL NEWS 1.0",
        "s4_follow_sub": "FOR REAL-TIME UPDATES",
        "ticker": [
            "BRENT CRUDE $116.72/BBL",
            "IRGC: 2 TANKERS HIT MINES IN HORMUZ",
            "EST. US WAR COST $47.1B",
            "QATAR TALKS: PROPOSED \"TWO-DAY PLAN\"",
            "SAUDI AIR DEFENSES INTERCEPT DRONES",
            "PICKAXE MOUNTAIN: >100 M UNDERGROUND",
        ],
    },
    "pt": {
        "brand": "GLOBAL NEWS 1.0",
        "desk": "MESA ORIENTE MÉDIO: GUERRA NO IRÃ",
        "live": "AO VIVO",
        "date": "02 NOV 2026",
        "day_of_war": "DIA {n} DA GUERRA • DESDE 28 FEV 2026",
        "s1_title": "ESTREITO DE ORMUZ • GARGALO",
        "s1_mine": "MINA",
        "s1_tanker": "PETROLEIRO {n}",
        "s1_unauth": "ROTA NÃO AUTORIZADA",
        "s1_lane": "ROTA DE NAVEGAÇÃO",
        "s1_src": "FONTE: IRGC • POSIÇÕES ILUSTRATIVAS",
        "s1_brent": "PETRÓLEO BRENT",
        "s1_bbl": "/BARRIL",
        "s1_tankers_hit": "2 PETROLEIROS EXPLODIRAM",
        "countries": {"IRAN": "IRÃ", "SAUDI": "ARÁBIA SAUDITA", "QATAR": "CATAR",
                      "UAE": "EAU", "OMAN": "OMÃ", "GULF": "GOLFO PÉRSICO",
                      "OMANGULF": "GOLFO DE OMÃ", "STRAIT": "ESTREITO DE ORMUZ"},
        "s2_title": "PICKAXE MOUNTAIN • PERFIL",
        "s2_name": "KŪH-E KOLANG GAZ LĀ",
        "s2_loc": "SUL DE NATANZ • ZAGROS",
        "s2_depth": "PROFUNDIDADE",
        "s2_depth_val": ">100 M / 300+ PÉS",
        "s2_tunnels": "COMPLEXO DE TÚNEIS",
        "s2_surface": "SUPERFÍCIE",
        "s2_cost": "CUSTO EST. DA GUERRA",
        "s2_cost_sub": "PARA CONTRIBUINTES DOS EUA",
        "s2_quote": "TRUMP: GUERRA ACABA\n\"MUITO EM BREVE\";\nQUER \"UM OU DOIS\"\nALVOS A MAIS",
        "s2_target": "ALVO DE INTERESSE",
        "s3_title": "\"PLANO DE DOIS DIAS\" VIA CATAR",
        "s3_by": "ANUNCIADO PELO CHANCELER ABBAS ARAGHCHI",
        "s3_day1": "DIA 1",
        "s3_day1_txt": "MEDIDAS\nDOS EUA",
        "s3_day2": "DIA 2",
        "s3_day2_txt": "ORMUZ\nREABRE",
        "s3_day2_sub": "NAVEGAÇÃO NORMAL",
        "s3_day1_sub": "PRIMEIRO PASSO",
        "s3_status": "STATUS: PROPOSTA",
        "s3_alert": "ALERTA REGIONAL • ARÁBIA SAUDITA",
        "s3_alert_txt": "Defesa aérea interceptou drones\napós ameaças houthis",
        "s3_rt": "RAS TANURA",
        "s3_ab": "ABQAIQ",
        "s1_badge_sub": "IRGC • ESTREITO DE ORMUZ",
        "s2_schem": "MONTES ZAGROS • ESQUEMÁTICO, FORA DE ESCALA",
        "s3_doha": "DOHA • NEGOCIAÇÕES MEDIADAS PELO CATAR",
        "s3_claimed": "ALVOS REIVINDICADOS:",
        "s3_source": "FONTE: HOUTHIS / DEFESA SAUDITA",
        "s3_inset": "ARÁBIA SAUDITA • PROVÍNCIA ORIENTAL",
        "s4_title": "DIPLOMACIA vs. ESCALADA",
        "s4_us": "ESTADOS UNIDOS",
        "s4_ir": "IRÃ",
        "s4_us_pts": ["TRUMP: Guerra acaba\n\"muito em breve\"",
                      "Quer \"um ou dois\"\nalvos a mais",
                      "RUBIO: Trump prefere\nsolução diplomática"],
        "s4_ir_pts": ["ARAGHCHI: \"Plano de\nDois Dias\" via Catar",
                      "EXÉRCITO: Nova guerra\npode durar mais"],
        "s4_dip": "DIPLOMACIA",
        "s4_esc": "ESCALADA",
        "s4_follow": "SIGA O GLOBAL NEWS 1.0",
        "s4_follow_sub": "ATUALIZAÇÕES EM TEMPO REAL",
        "ticker": [
            "BRENT US$ 116,72/BARRIL",
            "IRGC: 2 PETROLEIROS ATINGEM MINAS EM ORMUZ",
            "CUSTO EST. DA GUERRA US$ 47,1 BI",
            "CATAR: PROPOSTO \"PLANO DE DOIS DIAS\"",
            "DEFESA SAUDITA INTERCEPTA DRONES",
            "PICKAXE MOUNTAIN: >100 M DE PROFUNDIDADE",
        ],
    },
}
