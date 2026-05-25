"""StockX — mean-variance portfolio optimization (scipy SLSQP, long-only).

Engine math is pure and network-free; fetch_returns is the thin yfinance wrapper.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

_TRADING_DAYS = 252


@dataclass
class OptimizeResult:
    tickers: list[str]
    frontier_vol: list[float]
    frontier_ret: list[float]
    max_sharpe: dict
    min_var: dict
    current: dict | None


def fetch_returns(tickers: list[str], period: str = "2y") -> pd.DataFrame:
    """Daily returns DataFrame for the given tickers (columns = tickers w/ data)."""
    import yfinance as yf
    series = {}
    for t in tickers:
        hist = yf.Ticker(t).history(period=period)
        if hist is not None and len(hist) > 2:
            series[t] = hist["Close"].pct_change()
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).dropna()


def _point(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> dict:
    ret = float(weights @ mu)
    vol = float(np.sqrt(max(weights @ cov @ weights, 0.0)))
    sharpe = float((ret - rf) / vol) if vol > 0 else 0.0
    return {"weights": [float(w) for w in weights], "ret": ret, "vol": vol, "sharpe": sharpe}


def _solve(objective, n: int, extra_constraints=()) -> np.ndarray:
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}, *extra_constraints]
    bounds = [(0.0, 1.0)] * n
    x0 = np.repeat(1.0 / n, n)
    res = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=cons)
    if not res.success or np.any(np.isnan(res.x)):
        return x0  # equal-weight fallback keeps the UI alive
    clipped = np.clip(res.x, 0.0, None)
    total = clipped.sum()
    return clipped / total if total > 0 else x0


def optimize_portfolio(
    returns_df: pd.DataFrame,
    *,
    rf: float = 0.0,
    current_weights: list[float] | None = None,
) -> OptimizeResult:
    tickers = list(returns_df.columns)
    n = len(tickers)
    mu = returns_df.mean().to_numpy() * _TRADING_DAYS
    cov = returns_df.cov().to_numpy() * _TRADING_DAYS

    if n == 1:
        w = np.array([1.0])
        pt = _point(w, mu, cov, rf)
        cur = _point(np.array(current_weights), mu, cov, rf) if current_weights else None
        return OptimizeResult(tickers, [pt["vol"]], [pt["ret"]], pt, pt, cur)

    def neg_sharpe(w):
        ret = w @ mu
        vol = np.sqrt(max(w @ cov @ w, 1e-12))
        return -(ret - rf) / vol

    def variance(w):
        return w @ cov @ w

    max_sharpe = _point(_solve(neg_sharpe, n), mu, cov, rf)
    min_var = _point(_solve(variance, n), mu, cov, rf)

    # Efficient frontier: minimise variance for a grid of target returns.
    lo, hi = min_var["ret"], float(mu.max())
    frontier_vol, frontier_ret = [], []
    for target in np.linspace(lo, hi, 25):
        cons = ({"type": "eq", "fun": lambda w, t=target: w @ mu - t},)
        w = _solve(variance, n, extra_constraints=cons)
        pt = _point(w, mu, cov, rf)
        frontier_vol.append(pt["vol"])
        frontier_ret.append(pt["ret"])

    current = _point(np.array(current_weights), mu, cov, rf) if current_weights else None
    return OptimizeResult(tickers, frontier_vol, frontier_ret, max_sharpe, min_var, current)
