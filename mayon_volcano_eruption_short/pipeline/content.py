"""Editorial content: narration script (one segment per scene) and on-screen copy.

Facts (Mayon Volcano, Albay, Philippines - eruption of 30 Oct 2026):
  * Moderately explosive eruption at 11:53 AM; ash plume 3,000 m (9,840 ft)
    above the crater rim.
  * PHIVOLCS raised the alert from Level 2 to Level 3; the 6-km Permanent
    Danger Zone (PDZ) is strictly off-limits.
  * 1,430+ people evacuated, scaling past 2,000 residents / 740+ families
    across Tabaco City, Camalig and Ligao City (APSEMO).
  * 22,000+ protective masks distributed; warnings on livestock
    contamination and rain-triggered lahar mudflows.
"""
from __future__ import annotations

CONTENT = {
    "en": {
        "voice": "en-US-ChristopherNeural",
        "segments": [
            # Scene 1 (0-12 s) - eruption scale
            "Breaking news: Mayon Volcano erupts! At 11:53 AM, a moderately "
            "explosive blast shot ash 3,000 meters, 9,840 feet, above the crater.",
            # Scene 2 (12-25 s) - danger zone map
            "PHIVOLCS raised the alert from Level 2 to Level 3. The 6-kilometer "
            "Permanent Danger Zone is strictly off-limits, as residents evacuate "
            "to Tabaco City, Camalig, and Ligao City.",
            # Scene 3 (25-38 s) - emergency response metrics
            "Over 1,430 people fled, now scaling past 2,000 from 740 families. "
            "22,000 masks are deployed against toxic sulfur and ash, as rain "
            "threatens deadly lahar flows.",
            # Scene 4 (38-50 s) - real-time alert outro
            "Level 3 holds. Pilots must avoid the summit, livestock face "
            "contamination, and shelters are on standby. Follow Global News 1.0 "
            "for real-time updates.",
        ],
        # words (lower-case, punctuation stripped) used to sync animations
        "cues": {
            "tabaco": "tabaco", "camalig": "camalig", "ligao": "ligao",
            "evac": "1,430", "evac2": "2,000", "masks": "22,000", "lahar": "lahar",
            "level": "level", "follow": "follow", "pdz": "6-kilometer",
        },
        "ui": {
            "header_1": "GLOBAL NEWS 1.0 • DISASTER DESK:",
            "header_2": "MAYON VOLCANO ERUPTS",
            "live": "LIVE",
            "info": "ALBAY, PHILIPPINES  •  13.257°N 123.685°E  •  30 OCT 2026",
            "chips": ["01 / ERUPTION SCALE", "02 / 6 KM DANGER ZONE",
                      "03 / EMERGENCY RESPONSE", "04 / REAL-TIME ALERT"],
            "chip_right": ["PHIVOLCS", "ALBAY PROVINCE", "INCIDENT SUMMARY", "SITREP"],
            "s1_panel": "HEIGHT PROFILE  •  MAYON (2,463 m)",
            "s1_time": "ERUPTION  11:53 AM PHT",
            "s1_type": "MODERATELY EXPLOSIVE",
            "s1_above": "ABOVE CRATER RIM",
            "alert_org": "PHIVOLCS",
            "alert_lbl": "ALERT LEVEL",
            "alert_from": "RAISED FROM LEVEL 2",
            "chart_x": "DISTANCE FROM CRATER (KM)",
            "chart_summit": "SUMMIT 2,463 m",
            "chart_pdz": "6 KM PDZ",
            "s2_panel": "SATELLITE VECTOR MAP  •  ALBAY",
            "pdz_label": "6 KM PERMANENT DANGER ZONE  •  NO ENTRY",
            "hub": "EVACUATION HUB",
            "towns": {"tabaco": "TABACO CITY", "camalig": "CAMALIG", "ligao": "LIGAO CITY"},
            "legazpi": "LEGAZPI CITY",
            "gulf": "ALBAY GULF",
            "legend": ["6 KM PDZ PERIMETER", "EVACUATION CORRIDOR", "EVACUATION HUB"],
            "schematic": "SCHEMATIC • NOT FOR NAVIGATION",
            "cards": [
                {"value": "1,430+ → 2,000+", "label": "RESIDENTS EVACUATED",
                 "sub": "740+ FAMILIES • TABACO • CAMALIG • LIGAO"},
                {"value": "22,000+", "label": "PROTECTIVE MASKS DEPLOYED",
                 "sub": "TOXIC SULFUR & ASH INHALATION RISK"},
                {"value": "LAHAR + ASHFALL", "label": "HAZARD WARNING IN EFFECT",
                 "sub": "RAIN-TRIGGERED MUDFLOWS • LIVESTOCK RISK"},
                {"value": "LEVEL 3", "label": "ALERT MAINTAINED • PHIVOLCS",
                 "sub": "6 KM PDZ STRICTLY OFF-LIMITS"},
            ],
            "s4_title": "REAL-TIME ALERT STATUS",
            "s4_rows": [
                ("ALERT", "LEVEL 3 • ACTIVE", "orange"),
                ("6 KM PDZ", "STRICTLY OFF-LIMITS", "red"),
                ("AVIATION", "FLIGHTS BANNED NEAR SUMMIT", "orange"),
                ("SHELTERS", "EVACUATION CENTERS OPEN", "sulfur"),
                ("ASHFALL", "WEAR MASKS • STAY INDOORS", "sulfur"),
                ("LAHAR", "AVOID RIVER CHANNELS IN RAIN", "red"),
            ],
            "cta_1": "FOLLOW GLOBAL NEWS 1.0",
            "cta_2": "FOR REAL-TIME UPDATES",
            "ticker_tag": "BREAKING",
            "ticker": ("MAYON VOLCANO ERUPTS — 3,000 M ASH PLUME ABOVE CRATER RIM  •  "
                       "PHIVOLCS RAISES ALERT LEVEL 2 → 3  •  6 KM PERMANENT DANGER ZONE OFF-LIMITS  •  "
                       "2,000+ RESIDENTS / 740+ FAMILIES EVACUATED  •  22,000+ MASKS DISTRIBUTED  •  "
                       "LAHAR & ASHFALL WARNING IN EFFECT  •  "),
            "footer": "SOURCES: PHIVOLCS • APSEMO  |  GLOBAL NEWS 1.0",
        },
    },
    "pt": {
        "voice": "pt-BR-AntonioNeural",
        "segments": [
            "Urgente. O vulcão Mayon entrou em erupção. Às 11h53, uma explosão "
            "moderada lançou cinzas a 3.000 metros acima da cratera.",
            "O PHIVOLCS elevou o alerta do nível 2 para o nível 3. A Zona de Perigo "
            "Permanente de 6 quilômetros está proibida, com evacuações para Tabaco, "
            "Camalig e Ligao.",
            "Mais de 1.430 moradores fugiram, já passando de 2.000 pessoas de 740 "
            "famílias. 22 mil máscaras foram distribuídas contra cinzas tóxicas, e a "
            "chuva ameaça lahares mortais.",
            "O nível 3 continua. Pilotos devem evitar o cume, e abrigos estão de "
            "prontidão. Siga o Global News 1.0 para atualizações em tempo real.",
        ],
        "cues": {
            "tabaco": "tabaco", "camalig": "camalig", "ligao": "ligao",
            "evac": "1.430", "evac2": "2.000", "masks": "22", "lahar": "lahares",
            "level": "nível", "follow": "siga", "pdz": "zona",
        },
        "ui": {
            "header_1": "GLOBAL NEWS 1.0 • MESA DE DESASTRES:",
            "header_2": "VULCÃO MAYON ENTRA EM ERUPÇÃO",
            "live": "AO VIVO",
            "info": "ALBAY, FILIPINAS  •  13.257°N 123.685°E  •  30 OUT 2026",
            "chips": ["01 / ESCALA DA ERUPÇÃO", "02 / ZONA DE PERIGO 6 KM",
                      "03 / RESPOSTA DE EMERGÊNCIA", "04 / ALERTA EM TEMPO REAL"],
            "chip_right": ["PHIVOLCS", "PROVÍNCIA DE ALBAY", "RESUMO", "BOLETIM"],
            "s1_panel": "PERFIL DE ALTITUDE  •  MAYON (2.463 m)",
            "s1_time": "ERUPÇÃO  11:53 (PHT)",
            "s1_type": "MODERADAMENTE EXPLOSIVA",
            "s1_above": "ACIMA DA CRATERA",
            "alert_org": "PHIVOLCS",
            "alert_lbl": "NÍVEL DE ALERTA",
            "alert_from": "ELEVADO DO NÍVEL 2",
            "chart_x": "DISTÂNCIA DA CRATERA (KM)",
            "chart_summit": "CUME 2.463 m",
            "chart_pdz": "ZPP 6 KM",
            "s2_panel": "MAPA VETORIAL DE SATÉLITE  •  ALBAY",
            "pdz_label": "ZONA DE PERIGO PERMANENTE 6 KM  •  PROIBIDA",
            "hub": "CENTRO DE EVACUAÇÃO",
            "towns": {"tabaco": "TABACO CITY", "camalig": "CAMALIG", "ligao": "LIGAO CITY"},
            "legazpi": "LEGAZPI CITY",
            "gulf": "GOLFO DE ALBAY",
            "legend": ["PERÍMETRO ZPP 6 KM", "CORREDOR DE EVACUAÇÃO", "CENTRO DE EVACUAÇÃO"],
            "schematic": "ESQUEMÁTICO • NÃO USAR PARA NAVEGAÇÃO",
            "cards": [
                {"value": "1.430+ → 2.000+", "label": "MORADORES EVACUADOS",
                 "sub": "740+ FAMÍLIAS • TABACO • CAMALIG • LIGAO"},
                {"value": "22.000+", "label": "MÁSCARAS DISTRIBUÍDAS",
                 "sub": "RISCO DE INALAÇÃO DE ENXOFRE E CINZAS"},
                {"value": "LAHAR + CINZAS", "label": "ALERTA DE RISCO EM VIGOR",
                 "sub": "LAMA COM CHUVA • RISCO AO GADO"},
                {"value": "NÍVEL 3", "label": "ALERTA MANTIDO • PHIVOLCS",
                 "sub": "ZPP DE 6 KM ESTRITAMENTE PROIBIDA"},
            ],
            "s4_title": "STATUS DE ALERTA EM TEMPO REAL",
            "s4_rows": [
                ("ALERTA", "NÍVEL 3 • ATIVO", "orange"),
                ("ZPP 6 KM", "ACESSO PROIBIDO", "red"),
                ("AVIAÇÃO", "VOOS PROIBIDOS NO CUME", "orange"),
                ("ABRIGOS", "CENTROS DE EVACUAÇÃO ABERTOS", "sulfur"),
                ("CINZAS", "USE MÁSCARA • FIQUE EM CASA", "sulfur"),
                ("LAHAR", "EVITE RIOS SOB CHUVA", "red"),
            ],
            "cta_1": "SIGA O GLOBAL NEWS 1.0",
            "cta_2": "ATUALIZAÇÕES EM TEMPO REAL",
            "ticker_tag": "URGENTE",
            "ticker": ("VULCÃO MAYON ENTRA EM ERUPÇÃO — COLUNA DE CINZAS DE 3.000 M  •  "
                       "PHIVOLCS ELEVA ALERTA DO NÍVEL 2 → 3  •  ZONA DE PERIGO DE 6 KM PROIBIDA  •  "
                       "2.000+ MORADORES / 740+ FAMÍLIAS EVACUADOS  •  22.000+ MÁSCARAS  •  "
                       "ALERTA DE LAHAR E CINZAS  •  "),
            "footer": "FONTES: PHIVOLCS • APSEMO  |  GLOBAL NEWS 1.0",
        },
    },
}
