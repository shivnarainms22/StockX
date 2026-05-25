from __future__ import annotations
import unittest

try:
    import pandas as pd
    from services.indicators import (
        sma_series, ema_series, rsi_series, macd_series, bollinger_series,
        calc_rsi, calc_macd, calc_ema, calc_bollinger,
    )
except ModuleNotFoundError:  # pragma: no cover
    pd = None


def _hist(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [0] * len(closes)},
        index=idx,
    )


@unittest.skipUnless(pd is not None, "pandas not installed")
class IndicatorSeriesTests(unittest.TestCase):
    def test_sma_series_matches_rolling_mean(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(list(sma_series(s, 2).dropna()), [1.5, 2.5, 3.5])

    def test_ema_series_returns_full_series(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(len(ema_series(s, 2)), 4)

    def test_rsi_series_bounded_0_100(self) -> None:
        s = pd.Series([float(x) for x in range(1, 40)])
        rsi = rsi_series(s).dropna()
        self.assertTrue((rsi >= 0).all() and (rsi <= 100).all())

    def test_scalar_calc_rsi_equals_series_last(self) -> None:
        h = _hist([float(x) for x in range(1, 40)])
        self.assertAlmostEqual(calc_rsi(h), float(rsi_series(h["Close"]).iloc[-1]))

    def test_scalar_calc_macd_equals_series_last(self) -> None:
        h = _hist([float(x) for x in range(1, 60)])
        ml, sl, hg = calc_macd(h)
        s_ml, s_sl, s_hg = (s.iloc[-1] for s in macd_series(h["Close"]))
        self.assertAlmostEqual(ml, float(s_ml))
        self.assertAlmostEqual(hg, float(s_hg))

    def test_scalar_calc_bollinger_equals_series_last(self) -> None:
        h = _hist([float(x) for x in range(1, 40)])
        u, m, l = calc_bollinger(h)
        su, sm, sl = (s.iloc[-1] for s in bollinger_series(h["Close"]))
        self.assertAlmostEqual(m, float(sm))


if __name__ == "__main__":
    unittest.main()
