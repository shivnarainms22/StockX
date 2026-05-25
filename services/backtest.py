"""StockX — vectorized, lookahead-safe backtest engine (long/flat).

Signal generation (Strategy) is separate from execution simulation and metrics.
A Strategy maps a price DataFrame to a target position Series in {0, 1}.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from services import perf_metrics as pm
from services.indicators import (
    sma_series, ema_series, rsi_series, macd_series, bollinger_series,
)

Strategy = Callable[[pd.DataFrame], pd.Series]


# ── Strategy factories (return a Strategy with bound parameters) ──────────────

def sma_crossover(fast: int = 20, slow: int = 50) -> Strategy:
    def _strat(prices: pd.DataFrame) -> pd.Series:
        f = sma_series(prices["Close"], fast)
        s = sma_series(prices["Close"], slow)
        return (f > s).astype(float)
    return _strat


def ema_crossover(fast: int = 12, slow: int = 26) -> Strategy:
    def _strat(prices: pd.DataFrame) -> pd.Series:
        f = ema_series(prices["Close"], fast)
        s = ema_series(prices["Close"], slow)
        return (f > s).astype(float)
    return _strat


def rsi_reversion(period: int = 14, lower: float = 30, upper: float = 70) -> Strategy:
    def _strat(prices: pd.DataFrame) -> pd.Series:
        rsi = rsi_series(prices["Close"], period)
        raw = pd.Series(float("nan"), index=prices.index)
        raw[rsi < lower] = 1.0   # enter long when oversold
        raw[rsi > upper] = 0.0   # exit when overbought
        return raw.ffill().fillna(0.0)
    return _strat


def macd_crossover(fast: int = 12, slow: int = 26, signal: int = 9) -> Strategy:
    def _strat(prices: pd.DataFrame) -> pd.Series:
        line, sig, _ = macd_series(prices["Close"], fast, slow, signal)
        return (line > sig).astype(float)
    return _strat


def bollinger_reversion(period: int = 20, num_std: float = 2.0) -> Strategy:
    def _strat(prices: pd.DataFrame) -> pd.Series:
        upper, mid, lower = bollinger_series(prices["Close"], period, num_std)
        close = prices["Close"]
        raw = pd.Series(float("nan"), index=prices.index)
        raw[close < lower] = 1.0   # enter long below lower band
        raw[close > mid] = 0.0     # exit on reversion to the mean
        return raw.ffill().fillna(0.0)
    return _strat


STRATEGIES: dict[str, tuple[Callable[..., Strategy], dict]] = {
    "SMA Crossover":       (sma_crossover, {"fast": 20, "slow": 50}),
    "EMA Crossover":       (ema_crossover, {"fast": 12, "slow": 26}),
    "RSI Reversion":       (rsi_reversion, {"period": 14, "lower": 30, "upper": 70}),
    "MACD Crossover":      (macd_crossover, {"fast": 12, "slow": 26, "signal": 9}),
    "Bollinger Reversion": (bollinger_reversion, {"period": 20, "num_std": 2.0}),
}


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series          # the position actually held each bar (shifted)
    trades: list[dict]
    metrics: dict
    benchmark_equity: pd.Series   # buy-and-hold the same ticker


def _extract_trades(held: pd.Series, asset_returns: pd.Series) -> list[dict]:
    """A trade is a contiguous run where held == 1; return its compounded return."""
    trades: list[dict] = []
    entry = None
    cum = 1.0
    n = len(held)
    for i in range(n):
        p = held.iloc[i]
        if p > 0:
            if entry is None:
                entry, cum = held.index[i], 1.0
            cum *= (1 + asset_returns.iloc[i])
        if entry is not None and (p == 0 or i == n - 1):
            trades.append({"entry": entry, "exit": held.index[i], "ret": cum - 1.0})
            entry, cum = None, 1.0
    return trades


def run_backtest(
    prices: pd.DataFrame,
    strategy: Strategy,
    *,
    initial_cash: float = 10_000.0,
    commission_bps: float = 5.0,
    slippage_bps: float = 5.0,
) -> BacktestResult:
    if prices is None or len(prices) < 2:
        raise ValueError("Not enough price data to backtest.")

    close = prices["Close"]
    asset_returns = close.pct_change().fillna(0.0)

    target = strategy(prices).clip(0.0, 1.0).fillna(0.0)
    held = target.shift(1).fillna(0.0)               # lookahead-safe

    cost_rate = (commission_bps + slippage_bps) / 1e4
    turnover = held.diff().abs().fillna(held.abs())  # cost on entering too
    net_returns = held * asset_returns - turnover * cost_rate

    equity = initial_cash * (1 + net_returns).cumprod()
    benchmark_equity = initial_cash * (1 + asset_returns).cumprod()

    trades = _extract_trades(held, asset_returns)
    trade_rets = [t["ret"] for t in trades]

    metrics = {
        "total_return": pm.total_return(equity),
        "cagr": pm.cagr(equity),
        "annualized_vol": pm.annualized_vol(net_returns),
        "sharpe": pm.sharpe(net_returns),
        "sortino": pm.sortino(net_returns),
        "max_drawdown": pm.max_drawdown(equity),
        "calmar": pm.calmar(equity),
        "win_rate": pm.win_rate(trade_rets),
        "exposure": pm.exposure(held),
        "num_trades": len(trades),
        "alpha": pm.alpha(net_returns, asset_returns),
        "beta": pm.beta(net_returns, asset_returns),
    }
    return BacktestResult(equity, net_returns, held, trades, metrics, benchmark_equity)
