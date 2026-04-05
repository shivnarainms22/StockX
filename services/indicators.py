"""
StockX — Shared technical indicator calculations.
Accepts pandas DataFrames with OHLCV columns (from yfinance).
Used by both tools/stock.py and gui/views/macro.py.
"""
from __future__ import annotations

from typing import Any


def calc_atr(hist: Any, period: int = 14) -> float:
    """Average True Range."""
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = (high - low).combine(
        (high - prev_close).abs(), max
    ).combine((low - prev_close).abs(), max)
    return float(tr.rolling(period).mean().iloc[-1])


def calc_adx(hist: Any, period: int = 14) -> tuple[float, float, float]:
    """Returns (ADX, +DI, -DI)."""
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = (high - low).combine((high - prev_close).abs(), max).combine(
        (low - prev_close).abs(), max
    )
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(span=period, adjust=False).mean()
    return float(adx.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])


def calc_stochastic(hist: Any, k_period: int = 14, d_period: int = 3) -> tuple[float, float]:
    """Returns (%K, %D)."""
    low_min = hist["Low"].rolling(k_period).min()
    high_max = hist["High"].rolling(k_period).max()
    k = 100 * (hist["Close"] - low_min) / (high_max - low_min)
    d = k.rolling(d_period).mean()
    return float(k.iloc[-1]), float(d.iloc[-1])


def calc_roc(hist: Any, period: int = 14) -> float:
    """Rate of Change (%)."""
    close = hist["Close"]
    if len(hist) < period:
        return 0.0
    return float((close.iloc[-1] - close.iloc[-period]) / close.iloc[-period] * 100)


def calc_obv(hist: Any) -> tuple[float, float]:
    """Returns (latest OBV, OBV 20-day SMA)."""
    close = hist["Close"]
    volume = hist["Volume"]
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (volume * direction).cumsum()
    return float(obv.iloc[-1]), float(obv.rolling(20).mean().iloc[-1])


def calc_vwap(hist: Any) -> float:
    """Volume-Weighted Average Price."""
    typical = (hist["High"] + hist["Low"] + hist["Close"]) / 3
    vol_sum = hist["Volume"].sum()
    if vol_sum == 0:
        return float(hist["Close"].iloc[-1])
    return float((typical * hist["Volume"]).sum() / vol_sum)


def find_support_resistance(hist: Any, lookback: int = 60) -> tuple[float, float]:
    """Find nearest support (swing low) and resistance (swing high)."""
    recent = hist.tail(lookback)
    current = float(hist["Close"].iloc[-1])
    highs = recent["High"].values
    lows = recent["Low"].values
    swing_highs = [
        highs[i] for i in range(2, len(highs) - 2)
        if highs[i] == max(highs[i - 2:i + 3])
    ]
    swing_lows = [
        lows[i] for i in range(2, len(lows) - 2)
        if lows[i] == min(lows[i - 2:i + 3])
    ]
    resistance = min((h for h in swing_highs if h > current), default=float(recent["High"].max()))
    support = max((l for l in swing_lows if l < current), default=float(recent["Low"].min()))
    return support, resistance


def calc_fibonacci(high: float, low: float) -> dict[str, float]:
    """Fibonacci retracement levels."""
    rng = high - low
    return {
        "23.6%": high - 0.236 * rng,
        "38.2%": high - 0.382 * rng,
        "50.0%": high - 0.500 * rng,
        "61.8%": high - 0.618 * rng,
        "78.6%": high - 0.786 * rng,
    }


# ── New indicator functions ──────────────────────────────────────────────────

def calc_rsi(hist: Any, period: int = 14) -> float:
    """Relative Strength Index (0-100)."""
    delta = hist["Close"].diff()
    gains = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    losses = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
    rs = gains / losses
    rsi = 100 - 100 / (1 + rs)
    return float(rsi.iloc[-1])


def calc_macd(
    hist: Any, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float, float, float]:
    """Returns (MACD line, signal line, histogram)."""
    close = hist["Close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


def calc_ema(hist: Any, span: int) -> float:
    """Exponential Moving Average of Close."""
    return float(hist["Close"].ewm(span=span, adjust=False).mean().iloc[-1])


def calc_bollinger(
    hist: Any, period: int = 20, num_std: float = 2.0
) -> tuple[float, float, float]:
    """Returns (upper band, middle band, lower band)."""
    close = hist["Close"]
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return float(upper.iloc[-1]), float(mid.iloc[-1]), float(lower.iloc[-1])


def calc_annualized_vol(hist: Any, window: int = 30) -> float:
    """30-day annualized volatility (%)."""
    import numpy as np
    returns = hist["Close"].pct_change().dropna()
    if len(returns) < window:
        return float(returns.std() * np.sqrt(252) * 100) if len(returns) > 1 else 0.0
    return float(returns.tail(window).std() * np.sqrt(252) * 100)


# ── Convenience: compute all indicators at once ──────────────────────────────

def calc_commodity_technicals(hist: Any) -> dict:
    """Compute all technical indicators for a commodity. Returns flat dict."""
    result: dict = {}
    try:
        result["rsi"] = calc_rsi(hist)
    except Exception:
        result["rsi"] = None

    try:
        ml, sl, hg = calc_macd(hist)
        result["macd_line"] = ml
        result["macd_signal"] = sl
        result["macd_hist"] = hg
    except Exception:
        result["macd_line"] = result["macd_signal"] = result["macd_hist"] = None

    try:
        result["stoch_k"], result["stoch_d"] = calc_stochastic(hist)
    except Exception:
        result["stoch_k"] = result["stoch_d"] = None

    try:
        result["ema20"] = calc_ema(hist, 20)
    except Exception:
        result["ema20"] = None

    try:
        result["ema50"] = calc_ema(hist, 50)
    except Exception:
        result["ema50"] = None

    try:
        result["support"], result["resistance"] = find_support_resistance(hist)
    except Exception:
        result["support"] = result["resistance"] = None

    try:
        result["bb_upper"], result["bb_mid"], result["bb_lower"] = calc_bollinger(hist)
    except Exception:
        result["bb_upper"] = result["bb_mid"] = result["bb_lower"] = None

    try:
        result["volatility_30d"] = calc_annualized_vol(hist)
    except Exception:
        result["volatility_30d"] = None

    try:
        result["atr14"] = calc_atr(hist)
    except Exception:
        result["atr14"] = None

    try:
        result["adx"], result["plus_di"], result["minus_di"] = calc_adx(hist)
    except Exception:
        result["adx"] = result["plus_di"] = result["minus_di"] = None

    try:
        result["price"] = float(hist["Close"].iloc[-1])
    except Exception:
        result["price"] = None

    return result
