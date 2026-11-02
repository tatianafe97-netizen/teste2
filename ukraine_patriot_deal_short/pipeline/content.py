"""Editorial content: narration per scene and all on-screen strings (EN / PT-BR).

Facts used (as supplied in the editorial brief, Oct/Nov 2026):
  * US State Department approved a $2.1B Foreign Military Sale of 500 Patriot
    PAC-3 MSE interceptors to Ukraine.
  * No US taxpayer funds: financed entirely by Canada, Germany, Norway and
    European Commission credit facilities.
  * Lockheed Martin is principal contractor; no additional US personnel are
    required in Ukraine.
  * New-build PAC-3s are not expected until the 2030s, so Kyiv is pressing the
    Pentagon to transfer interceptors from current US stocks now and backfill
    them with the new production run.

No per-country funding split or exact delivery year is shown, because none was
part of the verified fact set.
"""
from __future__ import annotations

VOICES = {
    "en": "en-US-ChristopherNeural",
    "pt": "pt-BR-AntonioNeural",
}
DEFAULT_RATE = "+8%"

# One narration block per scene; each is placed at its scene's start so the
# voice and graphics stay locked together.
NARRATION = {
    "en": [
        "Breaking: the U.S. State Department approves a $2.1 billion sale of "
        "500 Patriot PAC-3 MSE interceptors to Ukraine. Lockheed Martin is the "
        "principal contractor.",

        "Follow the money: zero U.S. taxpayer dollars. Canada, Germany, Norway, "
        "and European Commission credit facilities fund the entire package, "
        "a clear shift in who pays.",

        "Here's the catch: new PAC-3 interceptors aren't expected until the 2030s. "
        "So Kyiv is pressing the Pentagon to transfer missiles from U.S. stockpiles "
        "now, then backfill them with new production.",

        "Allies foot the bill, no additional U.S. personnel are required, and "
        "Ukraine's air shield gets stronger, if the missiles arrive in time. "
        "Follow Global News 1.0 for real-time updates.",
    ],
    "pt": [
        "Urgente: o Departamento de Estado dos EUA aprova a venda de 500 "
        "interceptadores Patriot PAC-3 MSE à Ucrânia, por 2,1 bilhões de dólares. "
        "A Lockheed Martin é a principal contratada.",

        "Siga o dinheiro: zero dólar do contribuinte americano. Canadá, Alemanha, "
        "Noruega e linhas de crédito da Comissão Europeia bancam todo o pacote, "
        "uma mudança em quem paga a conta.",

        "O porém: novos PAC-3 só devem chegar nos anos 2030. Por isso, Kiev "
        "pressiona o Pentágono a transferir mísseis dos estoques dos EUA agora, "
        "e repor tudo com a nova produção.",

        "Aliados pagam, sem pessoal americano adicional, e o escudo aéreo da "
        "Ucrânia se fortalece, se os mísseis chegarem a tempo. Siga o Global "
        "News 1.0 para atualizações em tempo real.",
    ],
}

# Keywords that trigger on-screen animations when spoken (first match wins,
# matched case-insensitively against the start of each spoken word).
CUES = {
    "en": {
        "count500": ["500"],
        "value": ["$2.1"],
        "lockheed": ["Lockheed"],
        "zero": ["zero"],
        "canada": ["Canada"],
        "germany": ["Germany"],
        "norway": ["Norway"],
        "eu": ["European"],
        "shift": ["shift"],
        "catch": ["catch"],
        "2030s": ["2030s", "2030"],
        "kyiv": ["Kyiv"],
        "backfill": ["backfill"],
        "allies": ["Allies"],
        "personnel": ["personnel"],
        "shield": ["shield"],
        "follow": ["Follow"],
    },
    "pt": {
        "count500": ["500"],
        "value": ["2,1"],
        "lockheed": ["Lockheed"],
        "zero": ["zero"],
        "canada": ["Canadá"],
        "germany": ["Alemanha"],
        "norway": ["Noruega"],
        "eu": ["Comissão", "linhas"],
        "shift": ["mudança"],
        "catch": ["porém"],
        "2030s": ["2030"],
        "kyiv": ["Kiev"],
        "backfill": ["repor"],
        "allies": ["Aliados"],
        "personnel": ["pessoal"],
        "shield": ["escudo"],
        "follow": ["Siga"],
    },
}

TEXT = {
    "en": {
        "channel": "GLOBAL NEWS 1.0",
        "tagline": "NEWS IN REAL TIME",
        "desk": "DEFENSE DESK: UKRAINE AIR DEFENSE",
        "live": "LIVE",
        "scene_tags": [
            "THE $2.1B PACKAGE BREAKDOWN",
            "FOLLOW THE MONEY",
            "THE 2030s BOTTLENECK",
            "STRATEGIC IMPACT",
        ],
        # Scene 1
        "s1_kicker": "BREAKING",
        "s1_kicker_note": "FOREIGN MILITARY SALE APPROVED",
        "s1_head": ["U.S. APPROVES $2.1B", "PATRIOT SALE TO UKRAINE"],
        "s1_patriot": "PATRIOT",
        "s1_model": "PAC-3 MSE",
        "s1_interceptors": "INTERCEPTORS",
        "s1_grid_label": "1 PIP = 1 INTERCEPTOR",
        "s1_value_label": "PACKAGE VALUE",
        "s1_value_fmt": "${v:.1f}B",
        "s1_contractor": ["LOCKHEED", "MARTIN"],
        "s1_contractor_label": "PRINCIPAL CONTRACTOR",
        "s1_source": "SOURCE: U.S. STATE DEPARTMENT",
        # Scene 2
        "s2_kicker": "FOLLOW THE MONEY",
        "s2_head": ["WHO PAYS THE $2.1B BILL?"],
        "s2_funders": [
            ("CA", "CANADA", ""),
            ("DE", "GERMANY", ""),
            ("NO", "NORWAY", ""),
            ("EU", "EUROPEAN", "COMMISSION CREDIT"),
        ],
        "s2_usa": "U.S. $0",
        "s2_kyiv": "KYIV",
        "s2_total": "$2.1B • 100% FUNDED BY ALLIES",
        "s2_stamp": ["$0", "U.S. TAXPAYER", "FUNDS"],
        "s2_map_note": "FUNDING FLOW • SCHEMATIC",
        # Scene 3
        "s3_kicker": "THE CATCH",
        "s3_head": ["NEW MISSILES:", "NOT UNTIL THE 2030s"],
        "s3_lanes": ["UKRAINE'S NEED", "NEW PRODUCTION", "KYIV'S PROPOSAL"],
        "s3_need": "IMMEDIATE AIR DEFENSE NEED",
        "s3_leadtime": "MANUFACTURING LEAD TIME",
        "s3_delivery": "NEW PAC-3 DELIVERIES",
        "s3_swap": "STOCKPILE SWAP",
        "s3_backfill": "BACKFILL U.S.",
        "s3_now": "NOW",
        "s3_gap": "THE GAP",
        "s3_2030s": "2030s",
        "s3_flow_title": "KYIV'S PLAN: U.S. STOCKPILE SWAP & BACKFILL",
        "s3_nodes": [("LOCKHEED", "NEW BUILD"), ("U.S.", "STOCKPILE"), ("UKRAINE", "FRONT LINE")],
        "s3_arrows": [("BACKFILL", "2030s"), ("TRANSFER", "NOW")],
        # Scene 4
        "s4_kicker": "STRATEGIC IMPACT",
        "s4_head": ["UKRAINE'S INTEGRATED", "AIR DEFENSE SHIELD"],
        "s4_tiers": [
            ("UPPER TIER", "PATRIOT PAC-3 MSE", "+500"),
            ("MEDIUM RANGE", "LAYERED SAM NETWORK", ""),
            ("SHORT RANGE", "POINT DEFENSE", ""),
        ],
        "s4_checks": [
            ("ok", "500 PAC-3 MSE APPROVED"),
            ("ok", "$2.1B ALLY-FUNDED • $0 U.S."),
            ("ok", "NO ADDITIONAL U.S. PERSONNEL"),
            ("warn", "2030s DELIVERY UNLESS STOCKS SWAPPED"),
        ],
        "s4_scope": "AIR PICTURE • UKRAINE",
        "lower_third": ["FOLLOW GLOBAL NEWS 1.0", "FOR REAL-TIME UPDATES"],
        "ticker_label": "BREAKING",
        "ticker": (
            "U.S. STATE DEPT APPROVES $2.1B PATRIOT SALE TO UKRAINE  •  "
            "500 PAC-3 MSE INTERCEPTORS  •  FUNDED BY CANADA, GERMANY, NORWAY "
            "& EUROPEAN COMMISSION CREDIT  •  $0 U.S. TAXPAYER FUNDS  •  "
            "LOCKHEED MARTIN PRINCIPAL CONTRACTOR  •  NO ADDITIONAL U.S. "
            "PERSONNEL  •  NEW-BUILD DELIVERIES EXPECTED IN THE 2030s  •  "
        ),
    },
    "pt": {
        "channel": "GLOBAL NEWS 1.0",
        "tagline": "NOTÍCIAS EM TEMPO REAL",
        "desk": "DEFESA: DEFESA AÉREA DA UCRÂNIA",
        "live": "AO VIVO",
        "scene_tags": [
            "O PACOTE DE US$ 2,1 BI",
            "SIGA O DINHEIRO",
            "O GARGALO DOS ANOS 2030",
            "IMPACTO ESTRATÉGICO",
        ],
        "s1_kicker": "URGENTE",
        "s1_kicker_note": "VENDA MILITAR APROVADA",
        "s1_head": ["EUA APROVAM VENDA DE", "US$ 2,1 BI EM PATRIOTS"],
        "s1_patriot": "PATRIOT",
        "s1_model": "PAC-3 MSE",
        "s1_interceptors": "INTERCEPTADORES",
        "s1_grid_label": "1 PONTO = 1 INTERCEPTADOR",
        "s1_value_label": "VALOR DO PACOTE",
        "s1_value_fmt": "US${v:.1f}BI",
        "s1_contractor": ["LOCKHEED", "MARTIN"],
        "s1_contractor_label": "CONTRATADA PRINCIPAL",
        "s1_source": "FONTE: DEPARTAMENTO DE ESTADO DOS EUA",
        "s2_kicker": "SIGA O DINHEIRO",
        "s2_head": ["QUEM PAGA OS US$ 2,1 BI?"],
        "s2_funders": [
            ("CA", "CANADÁ", ""),
            ("DE", "ALEMANHA", ""),
            ("NO", "NORUEGA", ""),
            ("EU", "COMISSÃO", "EUROPEIA (CRÉDITO)"),
        ],
        "s2_usa": "EUA US$ 0",
        "s2_kyiv": "KIEV",
        "s2_total": "US$ 2,1 BI • 100% PAGO PELOS ALIADOS",
        "s2_stamp": ["US$ 0", "DO CONTRIBUINTE", "AMERICANO"],
        "s2_map_note": "FLUXO DE FINANCIAMENTO • ESQUEMÁTICO",
        "s3_kicker": "O PORÉM",
        "s3_head": ["NOVOS MÍSSEIS:", "SÓ NOS ANOS 2030"],
        "s3_lanes": ["NECESSIDADE", "NOVA PRODUÇÃO", "PROPOSTA DE KIEV"],
        "s3_need": "NECESSIDADE IMEDIATA",
        "s3_leadtime": "PRAZO DE FABRICAÇÃO",
        "s3_delivery": "NOVAS ENTREGAS",
        "s3_swap": "TROCA DE ESTOQUE",
        "s3_backfill": "REPOSIÇÃO EUA",
        "s3_now": "AGORA",
        "s3_gap": "A LACUNA",
        "s3_2030s": "ANOS 2030",
        "s3_flow_title": "PLANO DE KIEV: TROCA E REPOSIÇÃO DE ESTOQUES",
        "s3_nodes": [("LOCKHEED", "NOVA PRODUÇÃO"), ("EUA", "ESTOQUE"), ("UCRÂNIA", "LINHA DE FRENTE")],
        "s3_arrows": [("REPOSIÇÃO", "ANOS 2030"), ("TRANSFERE", "AGORA")],
        "s4_kicker": "IMPACTO ESTRATÉGICO",
        "s4_head": ["O ESCUDO AÉREO", "INTEGRADO DA UCRÂNIA"],
        "s4_tiers": [
            ("CAMADA ALTA", "PATRIOT PAC-3 MSE", "+500"),
            ("MÉDIO ALCANCE", "REDE SAM EM CAMADAS", ""),
            ("CURTO ALCANCE", "DEFESA DE PONTO", ""),
        ],
        "s4_checks": [
            ("ok", "500 PAC-3 MSE APROVADOS"),
            ("ok", "US$ 2,1 BI DOS ALIADOS • US$ 0 DOS EUA"),
            ("ok", "SEM PESSOAL AMERICANO ADICIONAL"),
            ("warn", "ENTREGA SÓ NOS ANOS 2030 SEM TROCA"),
        ],
        "s4_scope": "QUADRO AÉREO • UCRÂNIA",
        "lower_third": ["SIGA O GLOBAL NEWS 1.0", "ATUALIZAÇÕES EM TEMPO REAL"],
        "ticker_label": "URGENTE",
        "ticker": (
            "EUA APROVAM VENDA DE US$ 2,1 BI EM MÍSSEIS PATRIOT À UCRÂNIA  •  "
            "500 INTERCEPTADORES PAC-3 MSE  •  PAGO POR CANADÁ, ALEMANHA, NORUEGA "
            "E CRÉDITO DA COMISSÃO EUROPEIA  •  US$ 0 DO CONTRIBUINTE AMERICANO  •  "
            "LOCKHEED MARTIN É A CONTRATADA PRINCIPAL  •  SEM PESSOAL AMERICANO "
            "ADICIONAL  •  NOVAS ENTREGAS SÓ NOS ANOS 2030  •  "
        ),
    },
}
