"""StockX — US Treasury yield curve + FRED-fitted recession probability.

Probit math (fit/predict) is pure; fetchers wrap services.research and return
None without a FRED key.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_MATURITIES = [
    ("1M", "DGS1MO", 1 / 12), ("3M", "DGS3MO", 0.25), ("6M", "DGS6MO", 0.5),
    ("1Y", "DGS1", 1.0), ("2Y", "DGS2", 2.0), ("3Y", "DGS3", 3.0),
    ("5Y", "DGS5", 5.0), ("7Y", "DGS7", 7.0), ("10Y", "DGS10", 10.0),
    ("20Y", "DGS20", 20.0), ("30Y", "DGS30", 30.0),
]


@dataclass
class YieldCurve:
    labels: list[str]
    years: list[float]
    yields: list[float]
    inverted: bool
    spread_10y_3m: float


def fit_recession_probit(spread, recession) -> tuple[float, float]:
    """MLE probit: P(recession) = Phi(b0 + b1*spread). Returns (b0, b1)."""
    from scipy.optimize import minimize
    from scipy.stats import norm

    x = np.asarray(spread, dtype=float)
    y = np.asarray(recession, dtype=float)

    def neg_ll(b):
        p = np.clip(norm.cdf(b[0] + b[1] * x), 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))

    res = minimize(neg_ll, [0.0, 0.0], method="Nelder-Mead")
    return float(res.x[0]), float(res.x[1])


def recession_probability_from_coef(b0: float, b1: float, spread: float) -> float:
    from scipy.stats import norm
    return float(np.clip(norm.cdf(b0 + b1 * spread), 0.0, 1.0))


def _add_months(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    total = (y * 12 + (m - 1)) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def fetch_yield_curve() -> YieldCurve | None:
    from services.research import fetch_fred_series
    labels, years, yields = [], [], []
    for label, sid, yr in _MATURITIES:
        obs = fetch_fred_series(sid, limit=1, frequency="d")
        if not obs:
            continue
        try:
            yields.append(float(obs[-1]["value"]))
            labels.append(label)
            years.append(yr)
        except (ValueError, KeyError):
            continue
    if len(yields) < 2:
        return None
    y_by_label = dict(zip(labels, yields))
    ten = y_by_label.get("10Y")
    three_m = y_by_label.get("3M")
    spread = (ten - three_m) if (ten is not None and three_m is not None) else 0.0
    return YieldCurve(labels, years, yields, inverted=spread < 0, spread_10y_3m=spread)


def recession_probability() -> dict | None:
    from services.research import fetch_fred_series
    spread_obs = fetch_fred_series("T10Y3M", limit=700, frequency="m")
    rec_obs = fetch_fred_series("USREC", limit=900, frequency="m")
    if not spread_obs or not rec_obs:
        return None
    spread = {o["date"][:7]: float(o["value"]) for o in spread_obs}
    rec = {o["date"][:7]: float(o["value"]) for o in rec_obs}
    months = sorted(spread)
    X, Y = [], []
    for m in months:
        fut = _add_months(m, 12)
        if fut in rec:
            X.append(spread[m])
            Y.append(rec[fut])
    if len(X) < 24 or sum(Y) == 0:
        return None
    b0, b1 = fit_recession_probit(X, Y)
    cur = spread[months[-1]]
    return {
        "probability": recession_probability_from_coef(b0, b1, cur),
        "spread": cur,
        "inverted": cur < 0,
        "coef": (b0, b1),
    }
