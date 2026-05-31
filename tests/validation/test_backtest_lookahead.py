"""Validate that services.backtest is lookahead-safe — the single most important
correctness property of a backtest engine. A backtest that secretly trades on
information it could not have had at decision time is the #1 way these tools lie.

Two independent proofs:
  1. Adversarial: a strategy that peeks at the CURRENT bar's return prints
     impossible profits with a naive (unshifted) simulation, but the real engine
     (held = target.shift(1)) collapses it to a realistic result.
  2. Black-box causality: mutating a FUTURE price must not change any earlier
     held position or equity value.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    from services.backtest import run_backtest
    from services import perf_metrics as pm
except ModuleNotFoundError:  # pragma: no cover
    pd = None


def _synthetic_prices(seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.012, 600)
    close = 100.0 * np.cumprod(1 + rets)
    idx = pd.date_range("2022-01-03", periods=len(close), freq="B")
    return pd.DataFrame({"Close": close}, index=idx)


@unittest.skipUnless(pd is not None, "pandas not installed")
class BacktestLookahead(unittest.TestCase):
    def setUp(self) -> None:
        self.prices = _synthetic_prices()
        self.asset_returns = self.prices["Close"].pct_change().fillna(0.0)
        # Adversarial signal: long exactly on the bars that go up (uses the same
        # bar's return — the textbook lookahead cheat).
        self.peek_target = (self.asset_returns > 0).astype(float)

    def test_engine_neutralizes_a_same_bar_peek(self) -> None:
        # Naive buggy simulation: apply the peek with NO shift.
        cheat_net = self.peek_target * self.asset_returns
        cheat_sharpe = pm.sharpe(cheat_net)

        # Real engine: strategy returns the raw peek; engine shifts it itself.
        res = run_backtest(
            self.prices, lambda p: self.peek_target,
            commission_bps=0.0, slippage_bps=0.0,
        )
        engine_sharpe = res.metrics["sharpe"]

        # The cheat is absurd; the engine's result is mortal. Demand a big gap.
        self.assertGreater(cheat_sharpe, 8.0)
        self.assertLess(engine_sharpe, cheat_sharpe / 3)

    def test_held_position_equals_prior_bar_signal(self) -> None:
        res = run_backtest(
            self.prices, lambda p: self.peek_target,
            commission_bps=0.0, slippage_bps=0.0,
        )
        expected = self.peek_target.shift(1).fillna(0.0)
        pd.testing.assert_series_equal(
            res.positions, expected, check_names=False
        )

    def test_future_price_change_cannot_alter_past(self) -> None:
        # Black-box causality: perturbing the LAST bar must leave every earlier
        # held position and equity value untouched.
        from services.backtest import sma_crossover
        strat = sma_crossover(fast=10, slow=30)

        base = run_backtest(self.prices, strat)
        bumped = self.prices.copy()
        bumped.iloc[-1, bumped.columns.get_loc("Close")] *= 1.25  # wild future move
        after = run_backtest(bumped, strat)

        pd.testing.assert_series_equal(
            base.positions.iloc[:-1], after.positions.iloc[:-1], check_names=False
        )
        pd.testing.assert_series_equal(
            base.equity.iloc[:-1], after.equity.iloc[:-1], check_names=False
        )


if __name__ == "__main__":
    unittest.main()
