"""Validate services.factor_exposure.compute_factor_betas (numpy lstsq) against
statsmodels.OLS on identical data. Same normal-equations solution => identical
betas and R^2.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    from services.factor_exposure import compute_factor_betas, scenario_impact
except ModuleNotFoundError:  # pragma: no cover
    sm = None


@unittest.skipUnless(sm is not None, "validate extras (statsmodels) not installed")
class FactorOLSVsStatsmodels(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(23)
        n = 750
        factors = pd.DataFrame({
            "Market": rng.normal(0.0004, 0.011, n),
            "Oil": rng.normal(0.0002, 0.02, n),
            "Gold": rng.normal(0.0001, 0.009, n),
            "Rates": rng.normal(0.0, 0.007, n),
            "USD": rng.normal(0.0, 0.005, n),
        })
        true_betas = np.array([1.1, 0.15, -0.05, -0.3, -0.2])
        noise = rng.normal(0.0, 0.003, n)
        port = 0.0001 + factors.to_numpy() @ true_betas + noise
        cls.port = pd.Series(port)
        cls.factors = factors
        cls.out = compute_factor_betas(cls.port, factors)
        X = sm.add_constant(factors.to_numpy())
        cls.sm_res = sm.OLS(cls.port.to_numpy(), X).fit()

    def test_betas_match_statsmodels(self) -> None:
        mine = np.array([self.out["betas"][f] for f in self.factors.columns])
        np.testing.assert_allclose(mine, self.sm_res.params[1:], rtol=1e-6, atol=1e-9)

    def test_r_squared_matches_statsmodels(self) -> None:
        self.assertAlmostEqual(self.out["r_squared"], self.sm_res.rsquared, places=8)

    def test_betas_recover_true_signal_within_noise(self) -> None:
        # Sanity: estimated Market beta is near the planted 1.1.
        self.assertAlmostEqual(self.out["betas"]["Market"], 1.1, delta=0.05)

    def test_scenario_impact_is_betas_dot_shocks(self) -> None:
        # Independent oracle: weight the shocks by the STATSMODELS betas, so this
        # fails if scenario_impact disagrees with an external regression result.
        shocks = {"Market": -0.30, "Oil": -0.40, "Gold": 0.08, "Rates": 0.12, "USD": 0.06}
        sm_betas = dict(zip(self.factors.columns, self.sm_res.params[1:]))
        expected = sum(sm_betas[f] * s for f, s in shocks.items())
        self.assertAlmostEqual(scenario_impact(self.out["betas"], shocks), expected, places=6)


if __name__ == "__main__":
    unittest.main()
