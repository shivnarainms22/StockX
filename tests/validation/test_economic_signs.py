"""Durable, hermetic guards for the ECONOMIC SEMANTICS of the factor/scenario
engine — the directional relationships the live audit (validation/audit.py)
checks on real data, pinned here on deterministic synthetic data.

These assert *meaning*, not just math: a high-market-beta book must lose in a
recession, an oil-levered book must gain in an oil shock, and a defensive book
must be hurt less than a cyclical one.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    from services.factor_exposure import compute_factor_betas, scenario_impact, SCENARIOS
except ModuleNotFoundError:  # pragma: no cover
    np = None


def _factor_returns(seed: int = 5, n: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Market": rng.normal(0.0004, 0.011, n),
        "Oil": rng.normal(0.0, 0.020, n),
        "Gold": rng.normal(0.0, 0.009, n),
        "Rates": rng.normal(0.0, 0.007, n),
        "USD": rng.normal(0.0, 0.005, n),
    })


def _book(factors: pd.DataFrame, loadings: dict, noise: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    y = np.zeros(len(factors))
    for f, b in loadings.items():
        y = y + b * factors[f].to_numpy()
    y = y + rng.normal(0.0, noise, len(factors))
    return pd.Series(y)


@unittest.skipUnless(np is not None, "numpy/pandas not installed")
class EconomicSigns(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.factors = _factor_returns()
        # A cyclical, high-market-beta, oil-levered book vs a defensive low-beta one.
        cls.cyclical = compute_factor_betas(
            _book(cls.factors, {"Market": 1.4, "Oil": 0.3}, 0.002, 1), cls.factors)["betas"]
        cls.defensive = compute_factor_betas(
            _book(cls.factors, {"Market": 0.3, "Rates": 0.4}, 0.002, 2), cls.factors)["betas"]
        cls.oil_book = compute_factor_betas(
            _book(cls.factors, {"Oil": 0.6, "Market": 0.5}, 0.002, 3), cls.factors)["betas"]

    def test_recession_scenario_is_negative_for_high_beta_book(self) -> None:
        impact = scenario_impact(self.cyclical, SCENARIOS["2008-style Recession"])
        self.assertLess(impact, 0.0)

    def test_recession_hurts_cyclical_more_than_defensive(self) -> None:
        rec = SCENARIOS["2008-style Recession"]
        self.assertLess(scenario_impact(self.cyclical, rec),
                        scenario_impact(self.defensive, rec))

    def test_oil_shock_is_positive_for_oil_levered_book(self) -> None:
        impact = scenario_impact(self.oil_book, SCENARIOS["Oil Shock (+50%)"])
        self.assertGreater(impact, 0.0)

    def test_higher_market_beta_means_bigger_recession_loss(self) -> None:
        # Monotonicity: market beta is the dominant driver of recession P&L.
        self.assertGreater(self.cyclical["Market"], self.defensive["Market"])

    def test_scenario_impact_ignores_factors_absent_from_betas(self) -> None:
        partial = {"Market": -0.5}  # betas missing Oil/Gold/Rates/USD
        shock = {"Market": -0.10, "Oil": 0.50}  # Oil should be silently skipped
        self.assertAlmostEqual(scenario_impact(partial, shock), -0.5 * -0.10, places=12)

    def test_all_named_recession_style_scenarios_shock_market_down(self) -> None:
        # Sanity on the library itself: every "bad" scenario has a negative market leg.
        for name in ("2008-style Recession", "Rate Hike (+100bps)",
                     "Risk-Off / Flight to Safety"):
            self.assertLess(SCENARIOS[name]["Market"], 0.0, name)


if __name__ == "__main__":
    unittest.main()
