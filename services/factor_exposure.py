"""StockX — portfolio macro-factor exposure (multivariate OLS) + scenario stress.

Regression and scenario math are pure; fetch_factor_data wraps yfinance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Factor label -> proxy ticker (all daily return series; consistent units).
FACTORS: dict[str, str] = {
    "Market": "SPY",
    "Oil": "CL=F",
    "Gold": "GC=F",
    "Rates": "TLT",   # 20y Treasury ETF: rising rates -> TLT falls
    "USD": "UUP",
}

# Named multi-factor shocks (factor label -> return), labeled by economic meaning.
SCENARIOS: dict[str, dict[str, float]] = {
    "2008-style Recession": {"Market": -0.30, "Oil": -0.40, "Gold": 0.08, "Rates": 0.12, "USD": 0.06},
    "Oil Shock (+50%)":      {"Oil": 0.50, "Market": -0.06, "Gold": 0.05, "USD": 0.03},
    "Rate Hike (+100bps)":   {"Rates": -0.08, "Market": -0.07, "USD": 0.04},
    "Risk-Off / Flight to Safety": {"Market": -0.15, "Gold": 0.10, "Rates": 0.06, "USD": 0.07},
    "Soft Landing":          {"Market": 0.12, "Oil": 0.05, "Rates": 0.03},
}


def compute_factor_betas(port_returns, factor_returns: pd.DataFrame) -> dict:
    """Multivariate OLS (with intercept). Returns {betas: {label: float}, r_squared}."""
    y = np.asarray(port_returns, dtype=float)
    labels = list(factor_returns.columns)
    X = factor_returns.to_numpy(dtype=float)
    A = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    betas = {lab: float(coef[i + 1]) for i, lab in enumerate(labels)}
    pred = A @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {"betas": betas, "r_squared": float(r2)}


def scenario_impact(betas: dict, shocks: dict) -> float:
    """Expected portfolio return = sum of beta * shock over shared factors."""
    return float(sum(betas[f] * s for f, s in shocks.items() if f in betas))


def fetch_factor_data(portfolio: list[dict], period: str = "1y"):
    """(port_returns Series, factor_returns DataFrame) or (None, None)."""
    import yfinance as yf

    tickers = [h["ticker"] for h in portfolio]
    if not tickers:
        return None, None
    weights, total = {}, 0.0
    for h in portfolio:
        v = h.get("qty", 0) * h.get("avg_cost", 0)
        weights[h["ticker"]] = v
        total += v
    if total <= 0:
        return None, None
    for t in weights:
        weights[t] /= total

    all_syms = list(set(tickers) | set(FACTORS.values()))
    try:
        data = yf.download(all_syms, period=period, progress=False, threads=True)
        closes = data["Close"].dropna(how="all")
    except Exception:
        return None, None
    returns = closes.pct_change().dropna(how="all")
    if returns is None or len(returns) < 30:
        return None, None

    port = pd.Series(0.0, index=returns.index)
    for t, w in weights.items():
        if t in returns.columns:
            port = port.add(returns[t].fillna(0.0) * w, fill_value=0.0)

    factor_cols = {lab: returns[sym] for lab, sym in FACTORS.items() if sym in returns.columns}
    if len(factor_cols) < 2:
        return None, None
    factor_df = pd.DataFrame(factor_cols)
    combined = pd.concat([port.rename("__port__"), factor_df], axis=1).dropna()
    if len(combined) < 30:
        return None, None
    return combined["__port__"], combined.drop(columns="__port__")
