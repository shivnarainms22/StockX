"""
StockX — Headline sentiment scorer (item 17).
Lexicon-based approach: no model downloads required.
Returns 0.0 (very bearish) to 1.0 (very bullish), 0.5 = neutral.
"""
from __future__ import annotations

import re

_POSITIVE: frozenset[str] = frozenset({
    "surge", "rally", "beat", "gain", "profit", "growth", "strong", "record",
    "upgrade", "buy", "outperform", "bullish", "recovery", "rise", "soar",
    "jump", "climb", "boost", "positive", "revenue", "earnings", "exceed",
    "above", "outlook", "optimistic", "expand", "demand", "breakout",
    "milestone", "win", "approval", "partner", "deal", "agreement", "launch",
    "momentum", "upbeat", "confidence", "opportunity", "dividend", "buyback",
    "acquire", "innovation", "breakthrough", "success", "increase",
})

_NEGATIVE: frozenset[str] = frozenset({
    "fall", "drop", "miss", "loss", "decline", "weak", "crash", "sell",
    "downgrade", "bearish", "recession", "concern", "risk", "plunge", "warn",
    "slump", "tumble", "below", "disappoint", "cut", "layoff", "restructure",
    "debt", "default", "lawsuit", "probe", "fine", "penalty", "fraud",
    "delay", "shortage", "inflation", "tariff", "ban", "block", "reject",
    "halt", "suspend", "recall", "downward", "pressure", "struggle", "fear",
    "uncertainty", "volatility", "selloff", "retreat",
})


def score_headline(text: str) -> float:
    """
    Score a news headline for sentiment.

    Returns:
        float in [0.0, 1.0]; 0.5 = neutral, >0.6 = bullish, <0.4 = bearish.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    pos = sum(1 for w in words if w in _POSITIVE)
    neg = sum(1 for w in words if w in _NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.5
    return max(0.0, min(1.0, (pos - neg) / (2 * total) + 0.5))
