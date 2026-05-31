"""Validate services.perf_metrics against empyrical (pyfolio/zipline reference)
on a real SPY price fixture.

Where StockX and empyrical agree by construction we assert tight equality. Where
they legitimately differ by convention, we (a) document the difference and (b)
validate StockX against an independent re-derivation of *its own* definition, so
the check still catches coding errors without papering over the divergence.
"""
from __future__ import annotations
import os
import unittest

try:
    import numpy as np
    import pandas as pd
    import empyrical as ep
    from services import perf_metrics as pm
except ModuleNotFoundError:  # pragma: no cover - validate extras not installed
    ep = None

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "spy_prices.csv")


@unittest.skipUnless(ep is not None, "validate extras (empyrical) not installed")
class PerfMetricsVsEmpyrical(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        px = pd.read_csv(_FIXTURE, index_col="Date")["Close"]
        cls.equity = px
        cls.returns = px.pct_change().dropna()

    # ── Conventions that match empyrical exactly ──────────────────────────────
    def test_sharpe_matches_empyrical(self) -> None:
        self.assertAlmostEqual(
            pm.sharpe(self.returns), ep.sharpe_ratio(self.returns), places=9
        )

    def test_annualized_vol_matches_empyrical(self) -> None:
        self.assertAlmostEqual(
            pm.annualized_vol(self.returns), ep.annual_volatility(self.returns), places=9
        )

    def test_max_drawdown_matches_empyrical(self) -> None:
        self.assertAlmostEqual(
            pm.max_drawdown(self.equity), ep.max_drawdown(self.returns), places=9
        )

    def test_beta_matches_empyrical(self) -> None:
        # SPY vs a noisy derived benchmark — beta is identical math in both libs.
        bench = self.returns * 0.5 + 0.0003
        self.assertAlmostEqual(
            pm.beta(self.returns, bench), ep.beta(self.returns, bench), places=9
        )

    # ── Conventions that differ defensibly; loose tol + documented reason ─────
    def test_cagr_matches_empyrical_within_period_count_convention(self) -> None:
        # StockX cagr uses len(equity) periods; empyrical annual_return uses
        # len(returns) = len(equity)-1. ~0.2% gap at n=500 from that off-by-one.
        self.assertAlmostEqual(
            pm.cagr(self.equity), ep.annual_return(self.returns), delta=2e-3
        )

    def test_calmar_matches_empyrical_within_period_count_convention(self) -> None:
        # Inherits the same period-count convention as cagr (its numerator); the
        # absolute gap scales with CAGR magnitude, so allow a little headroom.
        self.assertAlmostEqual(
            pm.calmar(self.equity), ep.calmar_ratio(self.returns), delta=5e-3
        )

    # ── Conventions StockX defines differently from empyrical ─────────────────
    def test_sortino_uses_sample_downside_std_not_target_semideviation(self) -> None:
        # StockX sortino divides by the SAMPLE std (ddof=1) of only-negative
        # excess returns. empyrical uses target semideviation (RMS of min(r,0)
        # over ALL periods), which is ~14% different here. We validate StockX
        # against an independent re-derivation of its own stated definition.
        r = self.returns.to_numpy()
        downside = r[r < 0]
        oracle = r.mean() / downside.std(ddof=1) * np.sqrt(252)
        self.assertAlmostEqual(pm.sortino(self.returns), oracle, places=9)
        # And confirm the documented divergence from empyrical is real, not a bug.
        self.assertNotAlmostEqual(
            pm.sortino(self.returns), ep.sortino_ratio(self.returns), places=2
        )

    def test_alpha_uses_arithmetic_annualization(self) -> None:
        # StockX annualizes alpha arithmetically (mean*252); empyrical annualizes
        # geometrically. Validate StockX against its own arithmetic definition.
        bench = self.returns * 0.5 + 0.0003
        b = pm.beta(self.returns, bench)
        oracle = self.returns.mean() * 252 - b * bench.mean() * 252
        self.assertAlmostEqual(pm.alpha(self.returns, bench), oracle, places=9)
        # Non-zero rf: rf must be subtracted from BOTH sides (CAPM intercept).
        rf = 0.02
        oracle_rf = (self.returns.mean() * 252 - rf) - b * (bench.mean() * 252 - rf)
        self.assertAlmostEqual(pm.alpha(self.returns, bench, rf=rf), oracle_rf, places=9)


if __name__ == "__main__":
    unittest.main()
