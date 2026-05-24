"""StockX — pure performance/risk metrics for backtests.

All functions take pandas Series (daily returns or equity curve) and degrade
gracefully on degenerate input (empty, flat, zero-variance) instead of raising.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_TRADING_DAYS = 252


def total_return(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def cagr(equity: pd.Series, periods_per_year: int = _TRADING_DAYS) -> float:
    n = len(equity)
    if n < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = n / periods_per_year
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0)


def annualized_vol(returns: pd.Series, periods_per_year: int = _TRADING_DAYS) -> float:
    if len(returns) < 2:
        return 0.0
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe(returns: pd.Series, rf: float = 0.0, periods_per_year: int = _TRADING_DAYS) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - rf / periods_per_year
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(excess.mean() / sd * np.sqrt(periods_per_year))


def sortino(returns: pd.Series, rf: float = 0.0, periods_per_year: int = _TRADING_DAYS) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - rf / periods_per_year
    downside = excess[excess < 0]
    dd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    if dd == 0 or np.isnan(dd):
        return 0.0
    return float(excess.mean() / dd * np.sqrt(periods_per_year))


def max_drawdown(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min())


def calmar(equity: pd.Series, periods_per_year: int = _TRADING_DAYS) -> float:
    mdd = abs(max_drawdown(equity))
    if mdd == 0:
        return 0.0
    return float(cagr(equity, periods_per_year) / mdd)


def win_rate(trade_returns: list[float]) -> float:
    if not trade_returns:
        return 0.0
    wins = sum(1 for r in trade_returns if r > 0)
    return float(wins / len(trade_returns))


def exposure(positions: pd.Series) -> float:
    if len(positions) == 0:
        return 0.0
    return float((positions != 0).mean())


def beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    df = pd.concat([returns, benchmark_returns], axis=1).dropna()
    if len(df) < 2:
        return 0.0
    r, b = df.iloc[:, 0], df.iloc[:, 1]
    var_b = b.var(ddof=1)
    if var_b == 0 or np.isnan(var_b):
        return 0.0
    return float(r.cov(b) / var_b)


def alpha(returns: pd.Series, benchmark_returns: pd.Series,
          rf: float = 0.0, periods_per_year: int = _TRADING_DAYS) -> float:
    b = beta(returns, benchmark_returns)
    ann_r = returns.mean() * periods_per_year
    ann_b = benchmark_returns.mean() * periods_per_year
    return float((ann_r - rf) - b * (ann_b - rf))
