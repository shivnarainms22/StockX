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


def shrunk_covariance(returns_df: pd.DataFrame) -> np.ndarray:
    """Ledoit-Wolf shrinkage of the sample covariance toward a scaled identity.

    Raw sample covariance is noisy and makes mean-variance optimisation unstable
    (tiny input changes -> wildly different, over-concentrated weights). Shrinking
    toward mu*I yields a better-conditioned, far more stable estimate. Returns the
    shrunk covariance in the same (daily) units as the input returns; matches
    sklearn.covariance.ledoit_wolf (validated in tests).
    """
    X = returns_df.to_numpy(dtype=float)
    T, N = X.shape
    if T < 2 or N < 1:
        return returns_df.cov().to_numpy(dtype=float)
    Xc = X - X.mean(axis=0)
    S = (Xc.T @ Xc) / T                          # MLE sample covariance (ddof=0)
    mu = np.trace(S) / N
    F = mu * np.eye(N)                            # shrinkage target: scaled identity
    d2 = float(np.sum((S - F) ** 2))
    b_bar2 = 0.0                                  # mean sq. error of per-obs cov vs S
    for k in range(T):
        outer = np.outer(Xc[k], Xc[k])
        b_bar2 += float(np.sum((outer - S) ** 2))
    b_bar2 /= T * T
    b2 = min(b_bar2, d2)
    shrinkage = (b2 / d2) if d2 > 0 else 0.0
    return shrinkage * F + (1.0 - shrinkage) * S


def _max_feasible_return(mu: np.ndarray, cap: float) -> float:
    """Highest portfolio return with per-asset weight <= cap and weights summing 1."""
    remaining, r = 1.0, 0.0
    for i in np.argsort(mu)[::-1]:
        w = min(cap, remaining)
        r += w * float(mu[i])
        remaining -= w
        if remaining <= 1e-12:
            break
    return r


def _point(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> dict:
    ret = float(weights @ mu)
    vol = float(np.sqrt(max(weights @ cov @ weights, 0.0)))
    sharpe = float((ret - rf) / vol) if vol > 0 else 0.0
    return {"weights": [float(w) for w in weights], "ret": ret, "vol": vol, "sharpe": sharpe}


def _solve(objective, n: int, extra_constraints=(), upper: float = 1.0) -> np.ndarray:
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}, *extra_constraints]
    bounds = [(0.0, upper)] * n
    x0 = np.repeat(1.0 / n, n)
    res = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=cons)
    if not res.success or np.any(np.isnan(res.x)):
        return x0  # equal-weight fallback keeps the UI alive
    clipped = np.clip(res.x, 0.0, upper)  # honor the per-asset cap on cleanup too
    total = clipped.sum()
    return clipped / total if total > 0 else x0


def optimize_portfolio(
    returns_df: pd.DataFrame,
    *,
    rf: float = 0.0,
    current_weights: list[float] | None = None,
    max_weight: float | None = None,
) -> OptimizeResult:
    tickers = list(returns_df.columns)
    n = len(tickers)
    mu = returns_df.mean().to_numpy() * _TRADING_DAYS
    cov = shrunk_covariance(returns_df) * _TRADING_DAYS  # stable Ledoit-Wolf estimate
    # Per-asset cap (diversification); clamp to >= 1/n so the simplex stays feasible.
    cap = 1.0 if max_weight is None else max(float(max_weight), 1.0 / n + 1e-9)

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

    max_sharpe = _point(_solve(neg_sharpe, n, upper=cap), mu, cov, rf)
    min_var = _point(_solve(variance, n, upper=cap), mu, cov, rf)

    # Efficient frontier: minimise variance for a grid of feasible target returns.
    lo, hi = min_var["ret"], _max_feasible_return(mu, cap)
    frontier_vol, frontier_ret = [], []
    for target in np.linspace(lo, hi, 25):
        cons = ({"type": "eq", "fun": lambda w, t=target: w @ mu - t},)
        w = _solve(variance, n, extra_constraints=cons, upper=cap)
        pt = _point(w, mu, cov, rf)
        frontier_vol.append(pt["vol"])
        frontier_ret.append(pt["ret"])

    current = _point(np.array(current_weights), mu, cov, rf) if current_weights else None
    return OptimizeResult(tickers, frontier_vol, frontier_ret, max_sharpe, min_var, current)
