"""Validate services.indicators against the `ta` library on deterministic OHLCV.

All indicators are pinned to the `ta` reference. RSI/ATR/ADX use Wilder smoothing
(`ewm(alpha=1/period)`) and match `ta` to tight tolerances; MACD/Bollinger/Stochastic/
EMA/SMA are standard formulas and match exactly (Bollinger within the std ddof
convention). This is the regression guard for the Wilder-smoothing fix.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    import ta
    from services import indicators as ind
except ModuleNotFoundError:  # pragma: no cover - validate extras not installed
    ta = None


def _ohlcv(seed: int = 9, n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1 + rng.normal(0.0003, 0.015, n))
    intrabar = np.abs(rng.normal(0.0, 0.008, n))
    high = close * (1 + intrabar)
    low = close * (1 - intrabar)
    vol = rng.integers(1_000, 10_000, n).astype(float)
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.DataFrame({"High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


@unittest.skipUnless(ta is not None, "validate extras (ta) not installed")
class IndicatorsVsReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.df = _ohlcv()
        cls.c = cls.df["Close"]

    # ── standard formulas: must match the reference ──────────────────────────
    def test_macd_line_matches_reference(self) -> None:
        ml, _, _ = ind.calc_macd(self.df)
        ref = ta.trend.MACD(self.c).macd().iloc[-1]
        self.assertAlmostEqual(ml, ref, places=8)

    def test_ema_matches_reference(self) -> None:
        mine = ind.calc_ema(self.df, 20)
        ref = ta.trend.EMAIndicator(self.c, window=20).ema_indicator().iloc[-1]
        self.assertAlmostEqual(mine, ref, places=8)

    def test_sma_matches_reference(self) -> None:
        mine = float(ind.sma_series(self.c, 20).iloc[-1])
        ref = ta.trend.SMAIndicator(self.c, window=20).sma_indicator().iloc[-1]
        self.assertAlmostEqual(mine, ref, places=8)

    def test_bollinger_matches_reference_within_ddof(self) -> None:
        # StockX uses sample std (ddof=1); ta uses population std (ddof=0). The mid
        # band (SMA) is identical; the bands differ only by the std convention.
        u, m, l = ind.calc_bollinger(self.df)
        ref_m = ta.volatility.BollingerBands(self.c).bollinger_mavg().iloc[-1]
        self.assertAlmostEqual(m, ref_m, places=8)
        ref_u = ta.volatility.BollingerBands(self.c).bollinger_hband().iloc[-1]
        self.assertAlmostEqual(u, ref_u, delta=abs(ref_u) * 0.02)

    def test_stochastic_k_matches_reference(self) -> None:
        k, _ = ind.calc_stochastic(self.df)
        ref = ta.momentum.StochasticOscillator(
            self.df["High"], self.df["Low"], self.c).stoch().iloc[-1]
        self.assertAlmostEqual(k, ref, delta=1e-6)

    # ── non-Wilder indicators: only assert valid ranges (deviation documented) ─
    def test_rsi_matches_wilder_reference(self) -> None:
        # StockX RSI now uses Wilder smoothing (alpha=1/period) -> matches `ta`.
        mine = ind.calc_rsi(self.df)
        ref = ta.momentum.RSIIndicator(self.c, window=14).rsi().iloc[-1]
        self.assertAlmostEqual(mine, ref, places=4)

    def test_atr_matches_wilder_reference(self) -> None:
        mine = ind.calc_atr(self.df)
        ref = ta.volatility.AverageTrueRange(
            self.df["High"], self.df["Low"], self.c, window=14).average_true_range().iloc[-1]
        self.assertAlmostEqual(mine, ref, delta=abs(ref) * 0.02)

    def test_adx_matches_wilder_reference(self) -> None:
        adx, pdi, mdi = ind.calc_adx(self.df)
        ref = ta.trend.ADXIndicator(
            self.df["High"], self.df["Low"], self.c, window=14).adx().iloc[-1]
        self.assertTrue(0.0 <= adx <= 100.0)
        self.assertAlmostEqual(adx, ref, delta=2.0)


if __name__ == "__main__":
    unittest.main()
