"""Editorial content for the Volkswagen crisis Short: facts, narration and on-screen copy.

Every number shown on screen or spoken lives in FACTS, so a correction is a one-line change.
"""

# --------------------------------------------------------------------------------------
# Facts (Q3 2026 results published 29 Oct 2026; wage-freeze plan reported Oct 2026)
# --------------------------------------------------------------------------------------
FACTS = {
    "report_date": "Oct 29, 2026",
    "op_loss_q3_2026_bn": -5.86,     # operating loss, EUR bn (~$6.5B)
    "op_loss_q3_2025_bn": -1.29,     # prior-year Q3 operating loss, EUR bn
    "net_loss_q3_2026_bn": -5.82,    # net loss after tax, EUR bn
    "deliveries_m": 1.88,            # Q3 2026 vehicle deliveries, millions
    "deliveries_chg_pct": -15.1,
    "revenue_bn": 75.28,
    "revenue_chg_pct": -6.3,
    "margin_cap_pct": 1.0,           # 2026 operating margin guidance: up to 1%
    "china_deliveries_k": 406,
    "china_chg_pct": -38.5,
    "porsche_impairment_bn": 6.4,
    "china_writedown_bn": 1.0,
    "other_restructuring_bn": 0.3,
    "one_off_total_bn": 7.8,         # reported total of one-off items (parts are rounded)
    "workers": 660_000,
    "freeze_from": 2026,
    "freeze_to": 2030,
    "real_wage_loss_pct": -10.0,     # IG Metall / works council estimate
    "jobs_at_risk": 100_000,
}

SCENES = [(0.0, 12.0), (12.0, 25.0), (25.0, 38.0), (38.0, 50.0)]

VOICES = {
    "en": "en-US-ChristopherNeural",
    "pt": "pt-BR-AntonioNeural",
}

# --------------------------------------------------------------------------------------
# Copy per language. Narration is split per scene so each block lands on its own visual.
# --------------------------------------------------------------------------------------
STRINGS = {
    "en": {
        "channel": "GLOBAL NEWS 1.0",
        "channel_full": "GLOBAL NEWS 1.0 - NEWS IN REAL TIME",
        "header_top": "GLOBAL NEWS 1.0  •  ECONOMY & LABOR:",
        "header_main": "VOLKSWAGEN IN CRISIS",
        "live": "LIVE",
        "narration": [
            "Volkswagen just posted a 5.86 billion euro third-quarter operating loss. "
            "Deliveries fell 15.1 percent, revenue 6.3 percent, and margins are capped at one percent.",

            "China is the deepest wound. Deliveries there collapsed 38.5 percent as local EV makers take over. "
            "Add 6.4 billion in Porsche impairments and US tariffs, and the damage compounds.",

            "Workers get the bill. Unions say VW plans to freeze pay for all 660,000 staff until 2030: "
            "a ten percent real pay cut after inflation, with up to 100,000 jobs at risk.",

            "IG Metall calls the plan absurd, and a showdown is coming. "
            "Who pays for Volkswagen's crisis? Follow Global News 1.0 for real-time updates.",
        ],
        "kickers": ["FINANCIAL SHOCK", "CHINA & TARIFFS", "LABOR", "SHOWDOWN"],
        "titles": [
            "THE €5.8B Q3 COLLAPSE",
            "THE CHINA EV SHOCK",
            "660,000 WORKERS FROZEN",
            "UNION SHOWDOWN",
        ],
        # scene 1
        "s1_counter_label": "Q3 2026 OPERATING LOSS",
        "s1_counter_sub": "Net loss after tax: €5.82B  •  ≈ $6.5B",
        "s1_ax1_title": "OPERATING RESULT (€ BN)",
        "s1_ax1_cats": ["Q3 2025", "Q3 2026"],
        "s1_ax2_title": "Q3 2026 CHANGE (%)",
        "s1_ax2_cats": ["DELIVERIES\n1.88M", "REVENUE\n€75.28B"],
        "s1_tiles": [("1.88M", "VEHICLES DELIVERED"), ("€75.28B", "REVENUE"), ("≤ 1%", "2026 MARGIN CAP")],
        "s1_source": "Source: Volkswagen Group Q3 2026 results, Oct 29, 2026",
        # scene 2
        "s2_left_head": "CHINA DELIVERIES",
        "s2_left_sub": "406K units in Q3",
        "s2_right_head": "ONE-OFF CHARGES",
        "s2_right_sub": "Porsche • China • restructuring",
        "s2_ax1_title": "CHINA VOLUME (PRIOR YEAR = 100)",
        "s2_ax1_cats": ["Q3 2025", "Q3 2026"],
        "s2_ax2_title": "IMPAIRMENTS (€ BN)",
        "s2_ax2_cats": ["Porsche\ngoodwill", "China\nassets", "Restructuring\n& other"],
        "s2_banner_head": "US TARIFFS",
        "s2_banner_text": "Tariffs + China EV price war squeeze every margin",
        "s2_source": "Source: Volkswagen Group Q3 2026 results",
        # scene 3
        "s3_counter_label": "WORKERS WORLDWIDE",
        "s3_counter_sub": "Pay frozen at 2026 levels until 2030",
        "s3_ax_title": "PURCHASING POWER INDEX (2026 = 100)",
        "s3_nominal": "Nominal pay (frozen)",
        "s3_real": "Real pay after inflation",
        "s3_tiles": [("0%", "PAY RISE TO 2030"), ("≈ -10%", "REAL WAGES"), ("100K", "JOBS AT RISK")],
        "s3_source": "Source: VW Global Works Council, IG Metall. Real-pay path illustrative.",
        # scene 4
        "s4_left_head": "THE BOARD",
        "s4_left_items": ["Wage freeze to 2030", "Bonus cuts", "Up to 100K jobs cut", "€7.8B one-off hit"],
        "s4_right_head": "THE UNIONS",
        "s4_right_items": ["IG Metall", "Global Works Council", "Plan called “absurd”", "Defending 660K jobs"],
        "s4_question": "WHO PAYS FOR VW'S CRISIS?",
        "s4_cta": "FOLLOW GLOBAL NEWS 1.0",
        "s4_cta_sub": "FOR REAL-TIME UPDATES",
        "ticker": [
            "VW Q3 OPERATING LOSS €5.86B",
            "DELIVERIES -15.1%",
            "REVENUE €75.28B (-6.3%)",
            "CHINA DELIVERIES -38.5%",
            "PORSCHE IMPAIRMENT €6.4B",
            "2026 MARGIN ≤1%",
            "660,000 WAGES FROZEN TO 2030",
            "UP TO 100,000 JOBS AT RISK",
        ],
    },
    "pt": {
        "channel": "GLOBAL NEWS 1.0",
        "channel_full": "GLOBAL NEWS 1.0 - NEWS IN REAL TIME",
        "header_top": "GLOBAL NEWS 1.0  •  ECONOMIA & TRABALHO:",
        "header_main": "VOLKSWAGEN EM CRISE",
        "live": "AO VIVO",
        "narration": [
            "A Volkswagen teve prejuízo operacional de 5,86 bilhões de euros. "
            "Entregas caíram 15,1 por cento, a receita 6,3, e a margem não passa de um por cento.",

            "A China é a ferida mais funda: as entregas despencaram 38,5 por cento diante dos elétricos locais. "
            "Somam-se 6,4 bilhões em baixas da Porsche e as tarifas americanas.",

            "A conta vai para os trabalhadores. Sindicatos dizem que a VW quer congelar o salário de 660 mil "
            "funcionários até 2030: um corte real de dez por cento, e até 100 mil vagas em risco.",

            "O IG Metall chama o plano de absurdo, e o confronto se aproxima. "
            "Quem paga pela crise? Siga o Global News 1.0 para atualizações em tempo real.",
        ],
        "kickers": ["CHOQUE FINANCEIRO", "CHINA & TARIFAS", "TRABALHO", "CONFRONTO"],
        "titles": [
            "O COLAPSO DE €5,8 BI",
            "O CHOQUE DOS ELÉTRICOS",
            "660 MIL SALÁRIOS CONGELADOS",
            "SINDICATOS EM GUERRA",
        ],
        "s1_counter_label": "PREJUÍZO OPERACIONAL 3T 2026",
        "s1_counter_sub": "Prejuízo líquido: €5,82 bi  •  ≈ US$ 6,5 bi",
        "s1_ax1_title": "RESULTADO OPERACIONAL (€ BI)",
        "s1_ax1_cats": ["3T 2025", "3T 2026"],
        "s1_ax2_title": "VARIAÇÃO 3T 2026 (%)",
        "s1_ax2_cats": ["ENTREGAS\n1,88 MI", "RECEITA\n€75,28 BI"],
        "s1_tiles": [("1,88 MI", "VEÍCULOS ENTREGUES"), ("€75,28 BI", "RECEITA"), ("≤ 1%", "MARGEM 2026")],
        "s1_source": "Fonte: Volkswagen Group, resultados 3T 2026, 29/10/2026",
        "s2_left_head": "ENTREGAS NA CHINA",
        "s2_left_sub": "406 mil unidades no 3T",
        "s2_right_head": "BAIXAS CONTÁBEIS",
        "s2_right_sub": "Porsche • China • reestruturação",
        "s2_ax1_title": "CHINA (ANO ANTERIOR = 100)",
        "s2_ax1_cats": ["3T 2025", "3T 2026"],
        "s2_ax2_title": "BAIXAS (€ BI)",
        "s2_ax2_cats": ["Ágio\nPorsche", "Ativos\nChina", "Reestrut.\n& outros"],
        "s2_banner_head": "TARIFAS DOS EUA",
        "s2_banner_text": "Tarifas + guerra de preços dos elétricos chineses",
        "s2_source": "Fonte: Volkswagen Group, resultados 3T 2026",
        "s3_counter_label": "TRABALHADORES NO MUNDO",
        "s3_counter_sub": "Salários congelados no nível de 2026 até 2030",
        "s3_ax_title": "PODER DE COMPRA (2026 = 100)",
        "s3_nominal": "Salário nominal (congelado)",
        "s3_real": "Salário real após inflação",
        "s3_tiles": [("0%", "REAJUSTE ATÉ 2030"), ("≈ -10%", "SALÁRIO REAL"), ("100 MIL", "EMPREGOS EM RISCO")],
        "s3_source": "Fonte: Conselho Mundial de Trabalhadores da VW, IG Metall. Trajetória ilustrativa.",
        "s4_left_head": "A DIRETORIA",
        "s4_left_items": ["Salários congelados até 2030", "Corte de bônus", "Até 100 mil vagas", "Baixas de €7,8 bi"],
        "s4_right_head": "OS SINDICATOS",
        "s4_right_items": ["IG Metall", "Conselho de Trabalhadores", "Plano “absurdo”", "Defesa de 660 mil vagas"],
        "s4_question": "QUEM PAGA PELA CRISE DA VW?",
        "s4_cta": "SIGA O GLOBAL NEWS 1.0",
        "s4_cta_sub": "ATUALIZAÇÕES EM TEMPO REAL",
        "ticker": [
            "VW: PREJUÍZO OPERACIONAL DE €5,86 BI NO 3T",
            "ENTREGAS -15,1%",
            "RECEITA €75,28 BI (-6,3%)",
            "CHINA -38,5%",
            "BAIXA DA PORSCHE €6,4 BI",
            "MARGEM 2026 ≤1%",
            "660 MIL SALÁRIOS CONGELADOS ATÉ 2030",
            "ATÉ 100 MIL EMPREGOS EM RISCO",
        ],
    },
}
