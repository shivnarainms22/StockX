"""Validate services.indicators against the `ta` library on deterministic OHLCV.

MACD / Bollinger / Stochastic / EMA / SMA are standard formulas and must match the
reference tightly. RSI / ATR / ADX use non-Wilder smoothing in StockX (ewm-span /
SMA instead of Wilder's alpha=1/n), so they deliberately deviate from the canonical
values — see validation/MACRO_AUDIT_REPORT.md. We do NOT assert the deviating values
against the reference (that would lock in a likely miscalibration); we only assert
they stay in valid ranges, and pin the *correct* indicators to the reference.
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
    def test_rsi_is_valid_range(self) -> None:
        # StockX RSI uses ewm-span smoothing (not Wilder); see MACRO_AUDIT_REPORT.
        # We only range-check it here so switching to Wilder later is NOT blocked
        # by this test (it would then need its own match-vs-reference assertion).
        mine = ind.calc_rsi(self.df)
        self.assertTrue(0.0 <= mine <= 100.0)

    def test_atr_is_positive(self) -> None:
        self.assertGreater(ind.calc_atr(self.df), 0.0)

    def test_adx_is_valid_range(self) -> None:
        adx, pdi, mdi = ind.calc_adx(self.df)
        self.assertTrue(0.0 <= adx <= 100.0)
        self.assertTrue(0.0 <= pdi <= 100.0 and 0.0 <= mdi <= 100.0)


if __name__ == "__main__":
    unittest.main()
