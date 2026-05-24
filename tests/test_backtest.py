from __future__ import annotations
import unittest

try:
    import pandas as pd
    from services.backtest import (
        run_backtest, sma_crossover, ema_crossover, rsi_reversion,
        macd_crossover, bollinger_reversion, STRATEGIES,
    )
    from services import perf_metrics as pm
except ModuleNotFoundError:  # pragma: no cover
    pd = None


def _hist(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [1_000] * len(closes)},
        index=idx,
    )


def _always_long(prices):
    return pd.Series(1.0, index=prices.index)


@unittest.skipUnless(pd is not None, "pandas not installed")
class EngineTests(unittest.TestCase):
    def test_too_little_data_raises(self) -> None:
        with self.assertRaises(ValueError):
            run_backtest(_hist([100.0]), _always_long)

    def test_always_long_zero_cost_matches_buy_and_hold(self) -> None:
        h = _hist([100.0, 101.0, 103.0, 102.0, 105.0])
        res = run_backtest(h, _always_long, commission_bps=0, slippage_bps=0)
        self.assertTrue((res.equity.round(6) == res.benchmark_equity.round(6)).all())

    def test_no_lookahead_position_applies_next_bar(self) -> None:
        # Jump happens on bar 2; a "long when price > 100" signal can only act
        # from bar 3 onward, so it must NOT capture the jump.
        h = _hist([100.0, 100.0, 200.0, 200.0])

        def long_above_100(prices):
            return (prices["Close"] > 100).astype(float)

        res = run_backtest(h, long_above_100, commission_bps=0, slippage_bps=0)
        self.assertAlmostEqual(pm.total_return(res.equity), 0.0)
        self.assertAlmostEqual(pm.total_return(res.benchmark_equity), 1.0)

    def test_cost_charged_on_entry(self) -> None:
        h = _hist([100.0, 100.0, 100.0])  # flat -> only cost moves equity
        res = run_backtest(h, _always_long, initial_cash=1_000,
                           commission_bps=5, slippage_bps=5)  # 10 bps = 0.001
        self.assertAlmostEqual(res.equity.iloc[-1], 1_000 * (1 - 0.001), places=4)

    def test_uptrend_strategies_end_long(self) -> None:
        up = _hist([float(x) for x in range(1, 80)])
        for strat in (sma_crossover(5, 20), ema_crossover(5, 20), macd_crossover()):
            pos = strat(up).fillna(0.0)
            self.assertEqual(pos.iloc[-1], 1.0)

    def test_downtrend_crossover_ends_flat(self) -> None:
        down = _hist([float(x) for x in range(80, 1, -1)])
        self.assertEqual(sma_crossover(5, 20)(down).fillna(0.0).iloc[-1], 0.0)

    def test_rsi_reversion_goes_long_after_selloff(self) -> None:
        closes = [100.0] * 20 + [100.0 - 3 * i for i in range(1, 12)]
        pos = rsi_reversion()(_hist(closes)).fillna(0.0)
        self.assertEqual(pos.iloc[-1], 1.0)

    def test_registry_exposes_all_strategies(self) -> None:
        self.assertEqual(
            set(STRATEGIES),
            {"SMA Crossover", "EMA Crossover", "RSI Reversion",
             "MACD Crossover", "Bollinger Reversion"},
        )

    def test_result_has_expected_metric_keys(self) -> None:
        h = _hist([100.0 + (x % 5) for x in range(60)])
        res = run_backtest(h, sma_crossover(3, 8))
        for key in ("total_return", "cagr", "sharpe", "sortino", "max_drawdown",
                    "win_rate", "exposure", "num_trades", "alpha", "beta"):
            self.assertIn(key, res.metrics)


@unittest.skipUnless(pd is not None, "pandas not installed")
class ChartTests(unittest.TestCase):
    def test_render_equity_curve_returns_png_bytes(self) -> None:
        from services.charting import render_equity_curve
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        eq = pd.Series([100.0 + i for i in range(30)], index=idx)
        bm = pd.Series([100.0 + 0.5 * i for i in range(30)], index=idx)
        png = render_equity_curve(eq, bm)
        self.assertIsInstance(png, bytes)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_render_equity_curve_short_series_returns_empty(self) -> None:
        from services.charting import render_equity_curve
        idx = pd.date_range("2020-01-01", periods=1, freq="D")
        eq = pd.Series([100.0], index=idx)
        self.assertEqual(render_equity_curve(eq, eq), b"")


if __name__ == "__main__":
    unittest.main()
