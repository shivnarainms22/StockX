"""
StockX — Contextual signal engine for macro indicators.
Returns semantic color keys ("positive", "negative", "caution", "neutral")
so the GUI maps them to theme constants. No GUI imports here.
"""
from __future__ import annotations


# ── FRED Indicator Signal Config ─────────────────────────────────────────────
# rising_sentiment: "negative" = rising is bad, "positive" = rising is good,
#                   "context" = depends on the zone the value falls in
# zones: ordered list, first matching zone wins. "max" is exclusive upper bound.
# For CPI/PPI the raw value is an index (~310), so zones are meaningless —
# we only use direction-based logic for those.

FRED_SIGNAL_CONFIG: dict[str, dict] = {
    "UNRATE": {
        "rising_sentiment": "negative",
        "zones": [
            {"max": 4.0,  "label": "healthy",  "color": "positive"},
            {"max": 5.5,  "label": "elevated",  "color": "caution"},
            {"max": 9999, "label": "high",       "color": "negative"},
        ],
    },
    "FEDFUNDS": {
        "rising_sentiment": "negative",
        "zones": [
            {"max": 2.5,  "label": "accommodative", "color": "positive"},
            {"max": 4.5,  "label": "neutral",        "color": "caution"},
            {"max": 9999, "label": "restrictive",     "color": "negative"},
        ],
    },
    "T10Y2Y": {
        "rising_sentiment": "positive",
        "zones": [
            {"max": 0.0,  "label": "inverted",  "color": "negative"},
            {"max": 0.5,  "label": "flat",       "color": "caution"},
            {"max": 9999, "label": "normal",     "color": "positive"},
        ],
    },
    "DCOILWTICO": {
        "rising_sentiment": "context",
        "zones": [
            {"max": 40,   "label": "deflationary",          "color": "negative"},
            {"max": 90,   "label": "moderate",               "color": "positive"},
            {"max": 110,  "label": "inflationary pressure",  "color": "caution"},
            {"max": 9999, "label": "demand destruction risk", "color": "negative"},
        ],
    },
    "DTWEXBGS": {
        "rising_sentiment": "context",
        "zones": [
            {"max": 105,  "label": "weak dollar",            "color": "caution"},
            {"max": 115,  "label": "moderate",                "color": "positive"},
            {"max": 9999, "label": "strong dollar headwind",  "color": "negative"},
        ],
    },
    "CPIAUCSL": {
        "rising_sentiment": "negative",
        "zones": [],  # raw index — direction only
    },
    "PPIACO": {
        "rising_sentiment": "negative",
        "zones": [],  # raw index — direction only
    },
    # ── Europe ──
    "ECBDFR": {
        "rising_sentiment": "negative",
        "zones": [
            {"max": 1.5,  "label": "accommodative", "color": "positive"},
            {"max": 3.5,  "label": "neutral",        "color": "caution"},
            {"max": 9999, "label": "restrictive",     "color": "negative"},
        ],
    },
    "CP0000EZ19M086NEST": {
        "rising_sentiment": "negative",
        "zones": [],  # index — direction only
    },
    "LRHUTTTTEZM156S": {
        "rising_sentiment": "negative",
        "zones": [
            {"max": 6.0,  "label": "healthy",  "color": "positive"},
            {"max": 8.0,  "label": "elevated",  "color": "caution"},
            {"max": 9999, "label": "high",       "color": "negative"},
        ],
    },
    # ── China ──
    "CHNCPIALLMINMEI": {
        "rising_sentiment": "negative",
        "zones": [],  # index — direction only
    },
    "MPMIEM3338M086S": {
        "rising_sentiment": "positive",  # rising PMI = expanding economy = good
        "zones": [
            {"max": 49.0, "label": "contraction",  "color": "negative"},
            {"max": 50.5, "label": "stagnation",    "color": "caution"},
            {"max": 9999, "label": "expansion",      "color": "positive"},
        ],
    },
    # ── Japan ──
    "JPNCPIALLMINMEI": {
        "rising_sentiment": "negative",
        "zones": [],  # index — direction only
    },
    # ── India ──
    "INDCPIALLMINMEI": {
        "rising_sentiment": "negative",
        "zones": [],  # index — direction only
    },
    "IRSTCI01INM156N": {
        "rising_sentiment": "negative",
        "zones": [
            {"max": 5.5,  "label": "accommodative", "color": "positive"},
            {"max": 6.5,  "label": "neutral",        "color": "caution"},
            {"max": 9999, "label": "restrictive",     "color": "negative"},
        ],
    },
    # ── Global ──
    "DCOILBRENTEU": {
        "rising_sentiment": "context",
        "zones": [
            {"max": 45,   "label": "deflationary",          "color": "negative"},
            {"max": 95,   "label": "moderate",               "color": "positive"},
            {"max": 115,  "label": "inflationary pressure",  "color": "caution"},
            {"max": 9999, "label": "demand destruction risk", "color": "negative"},
        ],
    },
}


def get_fred_signal(
    series_id: str, value: float, previous: float | None
) -> dict[str, str]:
    """Return {"color": ..., "zone_label": ..., "tooltip": ...} for a FRED reading."""
    cfg = FRED_SIGNAL_CONFIG.get(series_id)
    if cfg is None:
        return {"color": "neutral", "zone_label": "", "tooltip": ""}

    # Determine zone
    zone_label = ""
    zone_color = "neutral"
    for z in cfg["zones"]:
        if value < z["max"]:
            zone_label = z["label"]
            zone_color = z["color"]
            break

    # Direction
    delta = (value - previous) if previous is not None else None
    rising = delta is not None and delta > 0.001
    falling = delta is not None and delta < -0.001

    sentiment = cfg["rising_sentiment"]

    if cfg["zones"]:
        # Zone-based series: zone determines base color
        if sentiment == "context":
            color = zone_color
        elif sentiment == "negative":
            if rising:
                color = "negative"
            elif falling:
                color = "positive"
            else:
                color = zone_color
        else:  # positive
            if rising:
                color = "positive"
            elif falling:
                color = "negative"
            else:
                color = zone_color
    else:
        # Direction-only series (CPI, PPI)
        if sentiment == "negative":
            color = "negative" if rising else ("positive" if falling else "neutral")
        else:
            color = "positive" if rising else ("negative" if falling else "neutral")

    # Tooltip
    direction_str = ""
    if delta is not None and abs(delta) > 0.001:
        direction_str = f" ({'rising' if rising else 'falling'} {delta:+.2f})"
    label_str = f" ({zone_label})" if zone_label else ""

    return {
        "color": color,
        "zone_label": zone_label,
        "tooltip": f"{value:.2f}{label_str}{direction_str}",
    }


# ── Commodity Impact Roles ───────────────────────────────────────────────────
# Splits COMMODITY_SECTOR_MAP tickers into producers (benefit from price rise)
# and consumers (hurt by price rise). Defines extreme move thresholds.

COMMODITY_IMPACT_ROLES: dict[str, dict] = {
    "CL=F": {
        "producers": ["XLE", "XOP", "CVX", "XOM", "COP", "OXY", "RELIANCE.NS", "ONGC.NS"],
        "consumers": ["JETS", "DAL", "UAL", "AAL", "FDX", "UPS"],
        "extreme_threshold_pct": 20,
        "demand_destruction": "Oil >$120: consumer spending drops globally, airline traffic -10-15%, India/China fuel subsidies strained, EV adoption accelerates",
    },
    "BZ=F": {
        "producers": ["XLE", "CVX", "XOM", "BP", "SHEL", "TTE", "EQNR", "2222.SR"],
        "consumers": ["JETS"],
        "extreme_threshold_pct": 20,
        "demand_destruction": "Brent >$130: global shipping costs spike, EU/India fuel subsidies strained, emerging market currency pressure",
    },
    "NG=F": {
        "producers": ["LNG", "AR", "EQT", "GAIL.NS"],
        "consumers": ["XLU", "MOS", "NTR", "CF"],
        "extreme_threshold_pct": 30,
        "demand_destruction": "Nat gas >$8: fertilizer plants shut globally, EU industry cuts output, India LNG import bill spikes",
    },
    "HO=F": {
        "producers": ["XLE"],
        "consumers": ["FDX", "UPS", "JBHT"],
        "extreme_threshold_pct": 25,
        "demand_destruction": "Heating oil spike: logistics costs surge, consumers cut discretionary spending on heating",
    },
    "GC=F": {
        "producers": ["GDX", "GDXJ", "NEM", "GOLD", "AEM", "KGC"],
        "consumers": [],
        "extreme_threshold_pct": 15,
        "demand_destruction": "Gold >$3000: jewellery demand drops sharply, central bank buying slows, signals deep economic fear",
    },
    "SI=F": {
        "producers": ["SIL", "PAAS", "AG", "MAG", "HL"],
        "consumers": [],
        "extreme_threshold_pct": 20,
        "demand_destruction": "Silver spike: industrial users (solar, electronics) seek substitutes, fabrication demand drops",
    },
    "PL=F": {
        "producers": ["IMPUY", "SBSW"],
        "consumers": [],
        "extreme_threshold_pct": 25,
        "demand_destruction": "Platinum spike: automakers accelerate shift to palladium/non-PGM catalysts",
    },
    "PA=F": {
        "producers": ["SBSW", "IMPUY"],
        "consumers": [],
        "extreme_threshold_pct": 25,
        "demand_destruction": "Palladium spike: automakers switch to platinum catalysts (substitution effect)",
    },
    "HG=F": {
        "producers": ["FCX", "SCCO", "TECK", "COPX", "BHP", "RIO", "HINDCOPPER.NS"],
        "consumers": ["TSLA", "RIVN"],
        "extreme_threshold_pct": 25,
        "demand_destruction": "Copper >$5.50/lb: construction slows globally, EV battery costs spike, China infrastructure spending hit (50% of global demand)",
    },
    "ALI=F": {
        "producers": ["AA", "CENX", "HINDALCO.NS"],
        "consumers": ["BLL"],
        "extreme_threshold_pct": 25,
        "demand_destruction": "Aluminum spike: packaging costs rise, China/India construction hit, aircraft manufacturing costs up",
    },
    "ZW=F": {
        "producers": ["ADM", "BG"],
        "consumers": ["DE", "CTVA", "MOS", "NTR"],
        "extreme_threshold_pct": 30,
        "demand_destruction": "Wheat >$12/bu: developing nations face food crises, consumers switch to rice/corn, export bans spread",
    },
    "ZC=F": {
        "producers": ["ADM", "BG"],
        "consumers": ["DE", "CTVA"],
        "extreme_threshold_pct": 30,
        "demand_destruction": "Corn spike: ethanol blending becomes uneconomic, livestock feed costs surge -> protein prices rise",
    },
    "ZS=F": {
        "producers": ["ADM", "BG"],
        "consumers": ["DAR"],
        "extreme_threshold_pct": 25,
        "demand_destruction": "Soybean spike: cooking oil prices surge, biodiesel margins collapse, feed costs rise",
    },
    "KC=F": {
        "producers": ["FARM"],
        "consumers": ["SBUX", "KDP"],
        "extreme_threshold_pct": 35,
        "demand_destruction": "Coffee >$3.50/lb: consumers trade down to instant/tea, coffee chains absorb margin hit or lose volume",
    },
    "SB=F": {
        "producers": [],
        "consumers": ["KO", "PEP", "MDLZ", "HSY"],
        "extreme_threshold_pct": 30,
        "demand_destruction": "Sugar spike: beverage/confectionery margins compressed, reformulation to artificial sweeteners accelerates",
    },
    "CT=F": {
        "producers": [],
        "consumers": ["PVH", "HBI", "RL", "VFC"],
        "extreme_threshold_pct": 30,
        "demand_destruction": "Cotton spike: fast-fashion margins collapse, synthetic fabric substitution increases, apparel prices rise",
    },
}


def get_commodity_move_signal(
    symbol: str, pct_1d: float | None, pct_1w: float | None = None
) -> dict:
    """Classify a commodity move and return contextual descriptions.

    Returns:
        severity: "normal" | "elevated" | "extreme"
        producer_desc: str — how producers are affected
        consumer_desc: str — how consumers are affected
        warning: str | None — demand destruction warning if extreme
        card_signal: "positive" | "negative" | "caution" — for card tinting
    """
    if pct_1d is None:
        return {
            "severity": "normal",
            "producer_desc": "",
            "consumer_desc": "",
            "warning": None,
            "card_signal": "neutral",
        }

    roles = COMMODITY_IMPACT_ROLES.get(symbol, {})
    threshold = roles.get("extreme_threshold_pct", 20)
    has_producers = bool(roles.get("producers"))
    has_consumers = bool(roles.get("consumers"))

    abs_1d = abs(pct_1d)
    abs_1w = abs(pct_1w) if pct_1w is not None else 0.0
    up = pct_1d >= 0

    # Severity
    if abs_1w >= threshold or abs_1d >= 10:
        severity = "extreme"
    elif abs_1d >= 5:
        severity = "elevated"
    else:
        severity = "normal"

    # Producer description
    if has_producers:
        if severity == "extreme":
            producer_desc = "short-term gain but demand destruction risk" if up else "severe pressure, potential capex cuts"
        elif up:
            producer_desc = "benefit from higher prices"
        else:
            producer_desc = "under pressure from lower prices"
    else:
        producer_desc = ""

    # Consumer description
    if has_consumers:
        if severity == "extreme":
            consumer_desc = "severe cost pressure, customer loss likely" if up else "major cost relief, demand recovery"
        elif up:
            consumer_desc = "higher input costs, margin pressure"
        else:
            consumer_desc = "cost relief, margin expansion"
    else:
        consumer_desc = ""

    # Warning
    warning = roles.get("demand_destruction") if severity == "extreme" else None

    # Card signal
    if severity == "extreme":
        card_signal = "caution"
    elif up:
        card_signal = "positive"
    else:
        card_signal = "negative"

    return {
        "severity": severity,
        "producer_desc": producer_desc,
        "consumer_desc": consumer_desc,
        "warning": warning,
        "card_signal": card_signal,
    }


# ── Detail Panel Indicator Signals ───────────────────────────────────────────

def get_stochastic_signal(k: float | None) -> str:
    """Return semantic color for stochastic %K value."""
    if k is None:
        return "neutral"
    if k >= 80:
        return "negative"  # overbought
    if k <= 20:
        return "positive"  # oversold
    return "neutral"


def get_bollinger_signal(pct_position: float | None) -> str:
    """Return semantic color for Bollinger Band position (0-100%)."""
    if pct_position is None:
        return "neutral"
    if pct_position >= 80:
        return "caution"  # stretched near upper band
    if pct_position <= 20:
        return "positive"  # near lower band, potential bounce
    return "neutral"


def get_proximity_signal(
    price: float | None, level: float | None, is_support: bool
) -> str:
    """Return semantic color based on price proximity to support/resistance."""
    if price is None or level is None or level == 0:
        return "neutral"
    proximity = abs(price - level) / level
    if proximity > 0.02:
        return "neutral"  # not close enough to matter
    return "positive" if is_support else "negative"
