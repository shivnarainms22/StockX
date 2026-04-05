"""
StockX — Curated economic knowledge base.
Expert-validated relationships, chokepoints, crisis parallels, and seasonal patterns.
Used to inject precise data into scenario analysis prompts.
"""
from __future__ import annotations


# ── Inflation pass-through rates ─────────────────────────────────────────────

INFLATION_PASSTHROUGH: dict[str, dict] = {
    "CL=F": {
        "cpi_impact_per_dollar": 0.03,
        "lag_months": 2,
        "description": "$10/barrel oil move -> ~$0.25/gallon at pump, ~0.3% CPI impact over 2 months",
    },
    "BZ=F": {
        "cpi_impact_per_dollar": 0.025,
        "lag_months": 2,
        "description": "Brent crude tracks WTI; primary benchmark for Europe/Asia fuel pricing",
    },
    "NG=F": {
        "cpi_impact_per_dollar": 0.15,
        "lag_months": 3,
        "description": "$1/MMBtu nat gas move -> ~$5-8/month household utility bills; 80% of fertilizer cost",
    },
    "HO=F": {
        "cpi_impact_per_dollar": 0.04,
        "lag_months": 1,
        "description": "Heating oil directly impacts Northeast US heating costs and diesel transport",
    },
    "ZW=F": {
        "cpi_impact_per_dollar": 0.002,
        "lag_months": 4,
        "description": "Wheat is 2-3% of bread retail price; larger impact on developing nations (20-40% of food basket)",
    },
    "ZC=F": {
        "cpi_impact_per_dollar": 0.001,
        "lag_months": 6,
        "description": "Corn: ~30% of livestock feed cost; flows through to meat/poultry prices in 4-6 months",
    },
    "ZS=F": {
        "cpi_impact_per_dollar": 0.001,
        "lag_months": 5,
        "description": "Soybeans: cooking oil, animal feed; major export commodity for Brazil/Argentina",
    },
    "KC=F": {
        "cpi_impact_per_dollar": 0.005,
        "lag_months": 3,
        "description": "Coffee: green bean cost is ~30-40% of retail price; high elasticity in specialty segment",
    },
    "SB=F": {
        "cpi_impact_per_dollar": 0.001,
        "lag_months": 4,
        "description": "Sugar: ingredient in processed foods; also used for ethanol in Brazil",
    },
    "HG=F": {
        "cpi_impact_per_dollar": 0.0005,
        "lag_months": 6,
        "description": "Copper: construction/electronics input; Dr. Copper = global growth barometer",
    },
    "GC=F": {
        "cpi_impact_per_dollar": 0.0,
        "lag_months": 0,
        "description": "Gold: no direct CPI pass-through; safe-haven asset, inflation hedge, central bank reserve",
    },
    "SI=F": {
        "cpi_impact_per_dollar": 0.0001,
        "lag_months": 3,
        "description": "Silver: ~50% industrial use (solar panels, electronics); 50% investment demand",
    },
}


# ── Global chokepoints ───────────────────────────────────────────────────────

CHOKEPOINTS: dict[str, dict] = {
    "strait_of_hormuz": {
        "name": "Strait of Hormuz",
        "global_oil_pct": 21,
        "daily_flow_mbpd": 17.0,
        "global_trade_pct": 5,
        "connects": "Persian Gulf to Gulf of Oman / Indian Ocean",
        "primary_commodities": ["CL=F", "BZ=F", "NG=F"],
        "countries_dependent": ["Saudi Arabia", "Iraq", "UAE", "Kuwait", "Qatar", "Iran"],
        "historical_disruption": "1984 Tanker War, 2019 tanker attacks — oil spiked 15% intraday",
    },
    "suez_canal": {
        "name": "Suez Canal",
        "global_oil_pct": 9,
        "daily_flow_mbpd": 5.5,
        "global_trade_pct": 12,
        "connects": "Mediterranean Sea to Red Sea",
        "primary_commodities": ["CL=F", "BZ=F", "NG=F"],
        "countries_dependent": ["Egypt (toll revenue ~$9B/year)"],
        "historical_disruption": "2021 Ever Given blockage — 6 days, $9.6B daily trade halted, oil +6%",
    },
    "strait_of_malacca": {
        "name": "Strait of Malacca",
        "global_oil_pct": 25,
        "daily_flow_mbpd": 16.0,
        "global_trade_pct": 25,
        "connects": "Indian Ocean to South China Sea / Pacific",
        "primary_commodities": ["CL=F", "BZ=F", "NG=F", "HG=F"],
        "countries_dependent": ["China", "Japan", "South Korea", "Taiwan"],
        "historical_disruption": "No major closure; piracy disruptions 2005-2012",
    },
    "panama_canal": {
        "name": "Panama Canal",
        "global_oil_pct": 1,
        "daily_flow_mbpd": 0.5,
        "global_trade_pct": 5,
        "connects": "Atlantic Ocean to Pacific Ocean",
        "primary_commodities": ["ZS=F", "ZC=F", "NG=F"],
        "countries_dependent": ["US (grain exports)", "China (imports)"],
        "historical_disruption": "2023-2024 drought reduced transits 36% — shipping costs doubled",
    },
    "turkish_straits": {
        "name": "Turkish Straits (Bosphorus/Dardanelles)",
        "global_oil_pct": 3,
        "daily_flow_mbpd": 2.4,
        "global_trade_pct": 3,
        "connects": "Black Sea to Mediterranean",
        "primary_commodities": ["CL=F", "ZW=F", "ZC=F"],
        "countries_dependent": ["Russia", "Ukraine", "Kazakhstan", "Romania"],
        "historical_disruption": "2022 Black Sea grain blockade — wheat +60%, corn +30%",
    },
}


# ── Commodity input-output relationships ─────────────────────────────────────

COMMODITY_IO: dict[str, list[dict]] = {
    "NG=F": [
        {"output": "fertilizer (ammonia/urea)", "cost_share_pct": 80,
         "downstream": ["ZW=F", "ZC=F", "ZS=F"],
         "note": "Natural gas is the primary feedstock for nitrogen fertilizer"},
        {"output": "electricity generation", "cost_share_pct": 35,
         "downstream": [],
         "note": "35% of US electricity; impacts utility costs nationwide"},
        {"output": "petrochemicals (methanol)", "cost_share_pct": 60,
         "downstream": [],
         "note": "Methanol used in plastics, adhesives, solvents"},
    ],
    "CL=F": [
        {"output": "gasoline/diesel", "cost_share_pct": 55,
         "downstream": [],
         "note": "Crude is ~55% of gasoline retail price"},
        {"output": "jet fuel", "cost_share_pct": 65,
         "downstream": [],
         "note": "Fuel is 25-35% of airline operating costs"},
        {"output": "plastics/petrochemicals", "cost_share_pct": 30,
         "downstream": [],
         "note": "Naphtha/ethylene feedstock for packaging, consumer goods"},
        {"output": "shipping fuel (bunker)", "cost_share_pct": 50,
         "downstream": [],
         "note": "Impacts ALL global trade costs via shipping rates"},
    ],
    "HG=F": [
        {"output": "electrical wiring/infrastructure", "cost_share_pct": 15,
         "downstream": [],
         "note": "Construction and power grid; 28% of copper demand"},
        {"output": "EV batteries and motors", "cost_share_pct": 8,
         "downstream": [],
         "note": "EVs use 3-4x more copper than ICE vehicles"},
    ],
    "ZC=F": [
        {"output": "livestock feed", "cost_share_pct": 30,
         "downstream": [],
         "note": "30% of chicken/pork production cost; 6-month lag to retail"},
        {"output": "ethanol", "cost_share_pct": 40,
         "downstream": ["CL=F"],
         "note": "40% of US corn goes to ethanol; links corn to oil price"},
    ],
    "ZW=F": [
        {"output": "bread and baked goods", "cost_share_pct": 5,
         "downstream": [],
         "note": "Low share in developed nations; 20-40% in developing nations"},
    ],
}


# ── Demand destruction thresholds ────────────────────────────────────────────
# When prices exceed these levels, demand contracts and second-order effects
# flip the narrative — even "beneficiaries" face risk.

DEMAND_DESTRUCTION: dict[str, dict] = {
    "CL=F": {
        "threshold_price": 120,
        "description": "Oil >$120/bbl triggers consumer demand destruction",
        "historical": "2008: oil at $147 preceded recession; 2022: $130 Brent caused ~2M bpd demand destruction",
        "second_order": [
            "Airline traffic drops 10-15%, route cuts follow within 3 months",
            "Consumer discretionary spending drops 3-5%",
            "EV adoption accelerates (2022 spike drove record EV sales)",
            "Recession probability rises above 50%",
            "Fed faces stagflation dilemma — can't raise rates without deepening recession",
        ],
    },
    "NG=F": {
        "threshold_price": 8.0,
        "description": "Nat gas >$8/MMBtu triggers industrial demand destruction",
        "historical": "2022 EU crisis: TTF hit $100/MMBtu equivalent, industrial output fell 10%, fertilizer plants shut across Europe",
        "second_order": [
            "Fertilizer plants shut down — food inflation follows 6-12 months later",
            "Industrial users switch to coal/oil alternatives, raising emissions",
            "Low-income households face energy poverty, political pressure mounts",
            "Utilities pass costs through — electricity bills spike 30-50%",
        ],
    },
    "KC=F": {
        "threshold_price": 3.50,
        "description": "Coffee >$3.50/lb triggers consumer substitution",
        "historical": "2011: coffee hit $3.00/lb, Starbucks raised prices 3x in one year, consumer visits dropped 5-8%",
        "second_order": [
            "Consumers trade down to instant coffee, tea, or home brewing",
            "Coffee chains absorb margin hit or lose foot traffic — no good option",
            "Smallholder farmers actually hurt by demand collapse despite high prices",
        ],
    },
    "ZW=F": {
        "threshold_price": 12.0,
        "description": "Wheat >$12/bu triggers food security crises",
        "historical": "2022: wheat hit $13.60 after Ukraine invasion, Egypt and others faced bread shortages",
        "second_order": [
            "Developing nations face food crises (wheat is 20-40% of food basket)",
            "Export bans spread (India, Argentina), worsening global supply",
            "Social unrest in import-dependent nations (2011 Arab Spring pattern)",
            "Consumers switch to rice/corn, pushing those prices up too",
        ],
    },
    "ZC=F": {
        "threshold_price": 8.0,
        "description": "Corn >$8/bu triggers ethanol and feed cost crises",
        "historical": "2012: US drought pushed corn to $8.40, livestock producers liquidated herds",
        "second_order": [
            "Ethanol blending becomes uneconomic, refiners reduce biofuel mix",
            "Livestock feed costs surge — producers liquidate herds, protein prices spike 6-12 months later",
            "Food vs. fuel debate intensifies, political pressure on ethanol mandates",
        ],
    },
    "HG=F": {
        "threshold_price": 5.50,
        "description": "Copper >$5.50/lb triggers construction and EV cost pressure",
        "historical": "2024: copper neared $5.20, construction projects deferred, EV makers flagged battery cost pressure",
        "second_order": [
            "Construction projects deferred — wiring and plumbing costs prohibitive",
            "EV battery costs spike, slowing adoption despite policy incentives",
            "Infrastructure spending (grids, data centres) faces budget overruns",
            "Recycling and substitution (aluminium wiring) accelerates",
        ],
    },
    "CT=F": {
        "threshold_price": 1.20,
        "description": "Cotton >$1.20/lb triggers apparel industry margin collapse",
        "historical": "2011: cotton hit $2.20/lb, fast-fashion margins collapsed, polyester substitution surged",
        "second_order": [
            "Fast-fashion retailers face margin collapse or pass costs to consumers",
            "Synthetic fabric substitution accelerates (polyester, nylon)",
            "Apparel price inflation 10-20%, consumers defer purchases",
        ],
    },
    "GC=F": {
        "threshold_price": 3000,
        "description": "Gold >$3000/oz signals deep economic fear",
        "historical": "Gold above $2000 historically correlates with real rates near zero and elevated systemic risk",
        "second_order": [
            "Jewellery demand drops sharply (India/China — largest markets)",
            "Central bank buying may slow at extreme prices despite reserve diversification motive",
            "Signals market expects prolonged uncertainty — risk-off positioning intensifies",
        ],
    },
}


# ── Historical crisis parallels ──────────────────────────────────────────────

CRISIS_PARALLELS: list[dict] = [
    {
        "name": "1973 OPEC Oil Embargo",
        "year": 1973,
        "trigger": "OPEC embargo on US/Western nations during Yom Kippur War",
        "duration_months": 6,
        "impacts": {
            "CL=F": "+300%", "GC=F": "+68%", "S&P 500": "-48%",
            "Airlines": "-55%", "USD": "-15%",
        },
        "resolution": "Embargo lifted March 1974; led to IEA creation and strategic petroleum reserves",
    },
    {
        "name": "2008 Oil Price Spike",
        "year": 2008,
        "trigger": "Speculation + China demand + tight supply; peak $147/barrel July 2008",
        "duration_months": 12,
        "impacts": {
            "CL=F": "+180% to peak, then -77% in 5 months",
            "Airlines": "-60%", "Consumer Discretionary": "-40%",
            "GC=F": "+25%", "Auto sector": "-50%",
        },
        "resolution": "Financial crisis demand destruction; oil collapsed to $32 by Dec 2008",
    },
    {
        "name": "2020 COVID-19 Crash",
        "year": 2020,
        "trigger": "Global lockdowns, demand collapse, OPEC+ price war",
        "duration_months": 4,
        "impacts": {
            "CL=F": "-70% (briefly negative)", "GC=F": "+25%",
            "HG=F": "-26% then +100% recovery", "NG=F": "-25%",
            "Airlines": "-65%", "Tech": "+40% (work from home)",
        },
        "resolution": "Unprecedented fiscal stimulus; V-shaped recovery in most commodities by Q3 2020",
    },
    {
        "name": "2022 Russia-Ukraine War",
        "year": 2022,
        "trigger": "Russian invasion of Ukraine; sanctions on Russian energy exports",
        "duration_months": 18,
        "impacts": {
            "ZW=F": "+60%", "NG=F (EU TTF)": "+140%", "BZ=F": "+30%",
            "GC=F": "+8%", "Fertilizer stocks": "+80%",
            "EU utilities": "-45%", "Defence stocks": "+30%",
        },
        "resolution": "Grain corridor deal, EU LNG diversification, demand destruction",
    },
    {
        "name": "2011 Fukushima Nuclear Disaster",
        "year": 2011,
        "trigger": "Earthquake/tsunami → Fukushima Daiichi meltdown",
        "duration_months": 12,
        "impacts": {
            "Uranium (UX)": "-40%", "NG=F": "+15% (replacement fuel)",
            "Solar stocks": "+20%", "GC=F": "+12%",
            "Japanese Yen": "+5% (repatriation flows)",
        },
        "resolution": "Japan shut all 54 reactors; global nuclear reassessment; Germany nuclear exit",
    },
    {
        "name": "2021 Suez Canal Blockage",
        "year": 2021,
        "trigger": "Ever Given container ship grounded in Suez Canal for 6 days",
        "duration_months": 0.2,
        "impacts": {
            "CL=F": "+6%", "Shipping rates": "+25%",
            "Container lines": "+15%",
        },
        "resolution": "Ship freed after 6 days; short-lived but exposed supply chain fragility",
    },
]


# ── Seasonal patterns ────────────────────────────────────────────────────────

SEASONAL_PATTERNS: dict[str, list[dict]] = {
    "NG=F": [
        {"months": [11, 12, 1, 2], "effect": "bullish", "magnitude_pct": 35,
         "description": "Winter heating demand increases nat gas consumption 30-40%"},
        {"months": [4, 5], "effect": "bearish", "magnitude_pct": -15,
         "description": "Post-winter injection season; storage refill depresses prices"},
    ],
    "ZW=F": [
        {"months": [3, 4], "effect": "bullish", "magnitude_pct": 5,
         "description": "Planting uncertainty; weather risk premium builds"},
        {"months": [8, 9, 10], "effect": "bearish", "magnitude_pct": -12,
         "description": "Northern hemisphere harvest pressure; supply peaks"},
    ],
    "ZC=F": [
        {"months": [3, 4], "effect": "bullish", "magnitude_pct": 5,
         "description": "Planting season; acreage uncertainty"},
        {"months": [9, 10, 11], "effect": "bearish", "magnitude_pct": -10,
         "description": "US harvest pressure; peak supply"},
    ],
    "GC=F": [
        {"months": [1, 2], "effect": "bullish", "magnitude_pct": 4,
         "description": "Chinese New Year demand; Indian wedding season wind-down"},
        {"months": [10, 11], "effect": "bullish", "magnitude_pct": 3,
         "description": "Indian wedding/Diwali season; festive gold buying"},
        {"months": [6, 7], "effect": "bearish", "magnitude_pct": -3,
         "description": "Summer doldrums; low physical demand"},
    ],
    "CL=F": [
        {"months": [5, 6, 7, 8], "effect": "bullish", "magnitude_pct": 8,
         "description": "US driving season; peak gasoline demand"},
        {"months": [9, 10], "effect": "bearish", "magnitude_pct": -5,
         "description": "Post-summer demand decline; refinery maintenance season"},
    ],
    "KC=F": [
        {"months": [10, 11, 12], "effect": "bullish", "magnitude_pct": 6,
         "description": "Pre-winter buying; Brazil off-crop concerns"},
        {"months": [4, 5, 6], "effect": "bearish", "magnitude_pct": -5,
         "description": "Brazil harvest arrives; supply peak"},
    ],
}


# ── Emerging market & global trade vulnerability ─────────────────────────────
# Import dependencies that make countries acutely vulnerable to commodity shocks.

EM_VULNERABILITY: dict[str, list[dict]] = {
    "CL=F": [
        {"country": "Russia", "detail": "2nd largest oil exporter. Revenue funds 40% of federal budget. Sanctions cap at $60/bbl; above-cap = Russia earns more via shadow fleet. Below $50 = budget crisis",
         "tickers": []},
        {"country": "India", "detail": "3rd largest oil importer, 85% import dependent. $10/bbl rise = ~$15B annual import bill increase, INR weakens 1-2%. Now largest buyer of discounted Russian crude",
         "tickers": ["RELIANCE.NS", "ONGC.NS", "IOC.NS"]},
        {"country": "China", "detail": "Largest oil importer, 72% import dependent. Key buyer of Saudi/Russian crude. $10/bbl rise = ~$30B annual cost",
         "tickers": ["0386.HK", "0857.HK"]},
        {"country": "Japan", "detail": "4th largest importer, near 100% import dependent. Weak yen amplifies oil price impact",
         "tickers": []},
        {"country": "Turkey", "detail": "99% oil import dependent. Oil spikes cause lira crises and double-digit inflation",
         "tickers": []},
        {"country": "South Africa", "detail": "Net oil importer. Oil spikes hit ZAR and widen current account deficit",
         "tickers": []},
    ],
    "NG=F": [
        {"country": "Russia", "detail": "Largest gas exporter. Lost EU pipeline market post-2022, pivoting to China (Power of Siberia). Gas revenue down 60% from peak. LNG exports via Arctic route",
         "tickers": []},
        {"country": "EU", "detail": "Was 40% dependent on Russian gas pre-2022, now ~15%. LNG import costs 3-4x pipeline gas. Germany's industrial base most exposed",
         "tickers": ["EQNR", "TTE", "SHEL"]},
        {"country": "India", "detail": "LNG imports growing 10%/year. Fertilizer sector heavily dependent. Gas subsidy bill balloons on spikes",
         "tickers": ["GAIL.NS"]},
        {"country": "Japan/Korea", "detail": "World's largest LNG importers. Contract prices lag spot by 3-6 months",
         "tickers": []},
    ],
    "ZW=F": [
        {"country": "Egypt", "detail": "World's largest wheat importer. 60% from Russia/Ukraine. Bread subsidies cost $3B/year, spike to $5B+ on wheat surge",
         "tickers": []},
        {"country": "Indonesia", "detail": "Major wheat importer for noodles/bread. Price spike causes instant food inflation",
         "tickers": []},
        {"country": "MENA region", "detail": "Middle East/North Africa imports 50%+ of calories. 2011 wheat spike contributed to Arab Spring unrest",
         "tickers": []},
        {"country": "Russia/Ukraine", "detail": "Together were 30% of global wheat exports pre-2022. Black Sea grain corridor is critical. Russia uses wheat as geopolitical leverage",
         "tickers": []},
        {"country": "India", "detail": "2nd largest wheat producer but imposed export bans in 2022. Domestic price pressure affects 1.4B people",
         "tickers": []},
    ],
    "HG=F": [
        {"country": "China", "detail": "Consumes 50% of global copper. Construction/infrastructure spending directly tied. Copper demand is a proxy for Chinese GDP growth",
         "tickers": []},
        {"country": "Russia", "detail": "4th largest copper producer. Nornickel is world's largest high-grade nickel/copper producer. Sanctions complicate but don't block trade",
         "tickers": []},
        {"country": "Chile/Peru", "detail": "Produce 40% of global copper. CLP and PEN currencies track copper prices. National budgets depend on mining revenue",
         "tickers": ["SCCO"]},
        {"country": "India", "detail": "Growing copper demand for electrification. Hindustan Copper is sole domestic producer",
         "tickers": ["HINDCOPPER.NS"]},
    ],
    "GC=F": [
        {"country": "Russia", "detail": "3rd largest gold producer. Central bank holds 2300+ tonnes. Gold is sanctions-evasion tool; sold via UAE/Turkey intermediaries",
         "tickers": []},
        {"country": "India", "detail": "Largest gold consumer (jewellery + investment). Gold imports = 6-7% of total imports. Price spikes widen trade deficit, weaken INR",
         "tickers": []},
        {"country": "China", "detail": "2nd largest gold consumer. PBoC has been aggressively buying gold reserves (de-dollarization). 2000+ tonnes in reserves",
         "tickers": []},
        {"country": "Central banks", "detail": "Global central banks bought 1000+ tonnes in 2023-2024. Turkey, India, China, Poland leading buyers",
         "tickers": []},
    ],
    "ZS=F": [
        {"country": "China", "detail": "Imports 60% of global soybean trade (~100M tonnes/year). Primary protein/oil source. US-China trade tension = soy weapon",
         "tickers": []},
        {"country": "Brazil", "detail": "Largest soybean exporter. BRL tracks soy prices. Amazon deforestation linked to soy expansion",
         "tickers": []},
    ],
    "KC=F": [
        {"country": "Brazil", "detail": "Produces 35% of global coffee. Frost/drought in Minas Gerais causes global price spikes. 2021 frost → prices doubled",
         "tickers": []},
        {"country": "Vietnam", "detail": "2nd largest producer (robusta). Supply disruption spikes instant coffee prices globally",
         "tickers": []},
        {"country": "Ethiopia/Colombia", "detail": "Arabica producers. 20-25M farming families depend on coffee income. Price crashes cause social crises",
         "tickers": []},
    ],
}

# Global trade flow relationships — who exports/imports what
GLOBAL_TRADE_FLOWS: dict[str, dict] = {
    "CL=F": {
        "top_exporters": "Saudi Arabia, Russia, Iraq, UAE, Canada, US",
        "top_importers": "China, India, Japan, South Korea, EU",
        "trade_routes": "Persian Gulf → Asia (Strait of Hormuz), Russia → EU (pipelines), Middle East → EU (Suez)",
        "chokepoint_risk": "21% of global oil transits Strait of Hormuz; Suez disruption adds 10-14 days to EU deliveries",
    },
    "NG=F": {
        "top_exporters": "US (LNG), Qatar (LNG), Russia (pipeline+LNG), Australia (LNG), Norway (pipeline)",
        "top_importers": "EU, Japan, China, South Korea, India",
        "trade_routes": "Qatar → Asia (Strait of Hormuz), US Gulf → EU/Asia (Atlantic), Russia → EU (pipelines via Ukraine/Nord Stream)",
        "chokepoint_risk": "25% of global LNG transits Strait of Hormuz; Malacca Strait critical for Asia-bound LNG",
    },
    "ZW=F": {
        "top_exporters": "Russia, EU, Australia, Canada, US, Ukraine",
        "top_importers": "Egypt, Indonesia, Turkey, Algeria, Philippines, India",
        "trade_routes": "Black Sea → Mediterranean (Turkish Straits), US/Canada → global (Atlantic/Pacific)",
        "chokepoint_risk": "Turkey controls Black Sea wheat exports via Bosphorus; 2022 Ukraine blockade spiked prices 60%",
    },
    "HG=F": {
        "top_exporters": "Chile, Peru, Congo (DRC), Australia, Indonesia",
        "top_importers": "China (50% of global demand), EU, Japan, South Korea, India",
        "trade_routes": "Chile/Peru → China (Pacific), DRC → China (Indian Ocean/Malacca)",
        "chokepoint_risk": "Strait of Malacca critical for copper shipments to China",
    },
    "GC=F": {
        "top_exporters": "China (producer), Australia, Russia, South Africa, Ghana, Peru",
        "top_importers": "India, China, Turkey, UAE (refining hub), Switzerland (refining hub)",
        "trade_routes": "Australia/South Africa → refineries (Switzerland/UAE) → India/China",
        "chokepoint_risk": "Low physical chokepoint risk; gold moves by air. Sanctions risk (Russia gold)",
    },
}


# ── Currency-commodity correlations ──────────────────────────────────────────

CURRENCY_CORRELATIONS: dict[str, dict] = {
    "DXY_commodities": {
        "correlation": -0.7,
        "description": "Strong USD typically suppresses commodity prices; dollar-denominated assets become more expensive for foreign buyers",
    },
    "AUD_copper": {
        "correlation": 0.6,
        "description": "Australia is world's 6th largest copper producer; AUD tracks copper closely",
    },
    "CAD_oil": {
        "correlation": 0.65,
        "description": "Canada is 4th largest oil producer; CAD highly sensitive to crude prices",
    },
    "BRL_soybeans": {
        "correlation": 0.5,
        "description": "Brazil is largest soybean exporter; BRL strengthens with soy prices",
    },
    "ZAR_gold": {
        "correlation": 0.4,
        "description": "South Africa is major gold producer; ZAR correlates with gold prices",
    },
    "NOK_oil": {
        "correlation": 0.55,
        "description": "Norway is major oil exporter; NOK tracks Brent crude",
    },
    "INR_oil": {
        "correlation": -0.55,
        "description": "India imports 85% of oil; INR weakens when oil rises. $10/bbl rise ≈ 1-2% INR depreciation",
    },
    "CNY_copper": {
        "correlation": 0.45,
        "description": "China consumes 50% of global copper; CNY strengthens with copper (proxy for industrial activity)",
    },
    "CLP_copper": {
        "correlation": 0.7,
        "description": "Chile produces 25% of global copper; CLP is among the most copper-sensitive currencies",
    },
    "EUR_natgas": {
        "correlation": -0.4,
        "description": "EU is major gas importer; EUR weakens on gas spikes (2022: gas +140% → EUR hit parity with USD)",
    },
    "RUB_oil": {
        "correlation": 0.6,
        "description": "Russia's budget depends on oil revenue; RUB strengthens with oil. Post-sanctions correlation weakened due to capital controls",
    },
}


# ── Helper functions ─────────────────────────────────────────────────────────

def build_knowledge_context(
    scenario_text: str,
    current_month: int,
    current_prices: dict[str, float] | None = None,
) -> str:
    """Scan scenario text and assemble relevant knowledge base data for prompt injection."""
    text_lower = scenario_text.lower()
    sections: list[str] = []

    # Check chokepoints
    _CHOKEPOINT_KEYWORDS = {
        "strait_of_hormuz": ["hormuz", "persian gulf", "iran strait", "gulf of oman"],
        "suez_canal": ["suez", "red sea", "suez canal"],
        "strait_of_malacca": ["malacca", "south china sea", "singapore strait"],
        "panama_canal": ["panama"],
        "turkish_straits": ["bosphorus", "dardanelles", "turkish strait", "black sea"],
    }

    for slug, keywords in _CHOKEPOINT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            cp = CHOKEPOINTS[slug]
            sections.append(
                f"CHOKEPOINT DATA — {cp['name']}:\n"
                f"  Handles {cp['global_oil_pct']}% of global oil ({cp['daily_flow_mbpd']}M barrels/day)\n"
                f"  {cp['global_trade_pct']}% of global trade\n"
                f"  Connects: {cp['connects']}\n"
                f"  Key countries: {', '.join(cp['countries_dependent'])}\n"
                f"  Historical: {cp['historical_disruption']}"
            )

    # Check commodity keywords for pass-through data
    _COMMODITY_KEYWORDS = {
        "CL=F": ["oil", "crude", "petroleum", "wti", "brent"],
        "NG=F": ["natural gas", "gas", "lng", "nat gas"],
        "ZW=F": ["wheat", "grain"],
        "ZC=F": ["corn", "maize"],
        "ZS=F": ["soybean", "soy"],
        "GC=F": ["gold"],
        "HG=F": ["copper"],
        "KC=F": ["coffee"],
        "SB=F": ["sugar"],
    }

    matched_symbols: list[str] = []
    for sym, keywords in _COMMODITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            matched_symbols.append(sym)
            pt = INFLATION_PASSTHROUGH.get(sym)
            if pt:
                sections.append(
                    f"INFLATION PASS-THROUGH — {sym}:\n"
                    f"  {pt['description']}\n"
                    f"  CPI impact per $1 move: {pt['cpi_impact_per_dollar']}%\n"
                    f"  Lag: {pt['lag_months']} months"
                )

    # Input-output chains
    for sym in matched_symbols:
        ios = COMMODITY_IO.get(sym, [])
        for io in ios:
            sections.append(
                f"INPUT-OUTPUT — {sym} -> {io['output']}:\n"
                f"  Cost share: {io['cost_share_pct']}%\n"
                f"  {io['note']}"
            )

    # Historical parallels
    _CRISIS_KEYWORDS = {
        "embargo": [0], "oil shock": [0, 1], "oil spike": [1],
        "pandemic": [2], "covid": [2], "lockdown": [2],
        "ukraine": [3], "russia": [3], "invasion": [3],
        "nuclear": [4], "fukushima": [4], "reactor": [4],
        "suez": [5], "canal block": [5],
        "war": [0, 3], "conflict": [0, 3], "sanctions": [3],
    }

    matched_crises: set[int] = set()
    for kw, indices in _CRISIS_KEYWORDS.items():
        if kw in text_lower:
            matched_crises.update(indices)

    for idx in sorted(matched_crises):
        if idx < len(CRISIS_PARALLELS):
            crisis = CRISIS_PARALLELS[idx]
            impacts_str = ", ".join(f"{k}: {v}" for k, v in crisis["impacts"].items())
            sections.append(
                f"HISTORICAL PARALLEL — {crisis['name']} ({crisis['year']}):\n"
                f"  Trigger: {crisis['trigger']}\n"
                f"  Duration: {crisis['duration_months']} months\n"
                f"  Impacts: {impacts_str}\n"
                f"  Resolution: {crisis['resolution']}"
            )

    # Seasonal context
    seasonal_lines = get_seasonal_context(matched_symbols, current_month)
    if seasonal_lines:
        sections.append(seasonal_lines)

    # EM vulnerability for matched commodities
    for sym in matched_symbols:
        vulns = EM_VULNERABILITY.get(sym, [])
        if vulns:
            vuln_lines = [f"GLOBAL VULNERABILITY — {sym}:"]
            for v in vulns:
                ticker_str = f" [{', '.join(v['tickers'])}]" if v["tickers"] else ""
                vuln_lines.append(f"  {v['country']}: {v['detail']}{ticker_str}")
            sections.append("\n".join(vuln_lines))

    # Global trade flows for matched commodities
    for sym in matched_symbols:
        tf = GLOBAL_TRADE_FLOWS.get(sym)
        if tf:
            sections.append(
                f"GLOBAL TRADE FLOWS — {sym}:\n"
                f"  Exporters: {tf['top_exporters']}\n"
                f"  Importers: {tf['top_importers']}\n"
                f"  Routes: {tf['trade_routes']}\n"
                f"  Chokepoint risk: {tf['chokepoint_risk']}"
            )

    # Currency correlations
    _CURRENCY_KEYWORDS = {
        "dollar": "DXY_commodities", "usd": "DXY_commodities", "dxy": "DXY_commodities",
        "australia": "AUD_copper", "aud": "AUD_copper",
        "canada": "CAD_oil", "cad": "CAD_oil",
        "brazil": "BRL_soybeans", "brl": "BRL_soybeans",
        "india": "INR_oil", "inr": "INR_oil", "rupee": "INR_oil",
        "china": "CNY_copper", "yuan": "CNY_copper", "cny": "CNY_copper",
        "chile": "CLP_copper", "clp": "CLP_copper",
        "euro": "EUR_natgas", "eur": "EUR_natgas", "europe": "EUR_natgas",
        "russia": "RUB_oil", "ruble": "RUB_oil", "rub": "RUB_oil",
    }
    for kw, key in _CURRENCY_KEYWORDS.items():
        if kw in text_lower and key in CURRENCY_CORRELATIONS:
            cc = CURRENCY_CORRELATIONS[key]
            sections.append(
                f"CURRENCY CORRELATION — {key}: r={cc['correlation']}\n"
                f"  {cc['description']}"
            )

    # Demand destruction context — triggered by current prices exceeding thresholds
    if current_prices:
        for sym, price in current_prices.items():
            dd = DEMAND_DESTRUCTION.get(sym)
            if dd and price >= dd["threshold_price"]:
                lines = [
                    f"DEMAND DESTRUCTION WARNING — {sym} at ${price:,.2f}:",
                    f"  {dd['description']}",
                    f"  Historical: {dd['historical']}",
                    f"  Second-order effects:",
                ]
                for effect in dd["second_order"]:
                    lines.append(f"    - {effect}")
                sections.append("\n".join(lines))
    # Also inject threshold info for matched commodities not already warned about
    for sym in matched_symbols:
        dd = DEMAND_DESTRUCTION.get(sym)
        if not dd:
            continue
        # Skip if we already emitted a full warning (price above threshold)
        already_warned = (
            current_prices
            and sym in current_prices
            and current_prices[sym] >= dd["threshold_price"]
        )
        if already_warned:
            continue
        sections.append(
            f"DEMAND DESTRUCTION THRESHOLD — {sym}:\n"
            f"  Triggers at: ${dd['threshold_price']:,.2f}\n"
            f"  {dd['description']}\n"
            f"  Historical: {dd['historical']}"
            )

    if not sections:
        return ""

    return "CURATED KNOWLEDGE BASE (expert-validated data):\n\n" + "\n\n".join(sections)


def get_passthrough_summary(symbols: list[str]) -> str:
    """Format inflation pass-through data for given commodity symbols."""
    lines = []
    for sym in symbols:
        pt = INFLATION_PASSTHROUGH.get(sym)
        if pt:
            lines.append(f"  {sym}: {pt['description']}")
    return "\n".join(lines) if lines else ""


def get_seasonal_context(symbols: list[str], month: int) -> str:
    """Return relevant seasonal patterns for given symbols and current month."""
    lines = []
    for sym in symbols:
        patterns = SEASONAL_PATTERNS.get(sym, [])
        for p in patterns:
            if month in p["months"]:
                sign = "+" if p["magnitude_pct"] > 0 else ""
                lines.append(
                    f"  {sym} seasonal ({p['effect']}): "
                    f"typical {sign}{p['magnitude_pct']}% — {p['description']}"
                )
    if not lines:
        return ""
    return "SEASONAL PATTERNS (current month):\n" + "\n".join(lines)
