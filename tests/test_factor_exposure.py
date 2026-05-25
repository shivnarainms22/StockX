from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    from services.factor_exposure import (
        FACTORS, SCENARIOS, compute_factor_betas, scenario_impact,
    )
except ModuleNotFoundError:  # pragma: no cover
    pd = None


@unittest.skipUnless(pd is not None, "numpy/pandas not installed")
class FactorBetaTests(unittest.TestCase):
    def test_recovers_known_betas(self) -> None:
        rng = np.random.default_rng(0)
        n = 500
        market = rng.normal(0, 0.01, n)
        oil = rng.normal(0, 0.02, n)
        port = 2.0 * market - 1.0 * oil + rng.normal(0, 1e-7, n)
        fr = pd.DataFrame({"Market": market, "Oil": oil})
        res = compute_factor_betas(pd.Series(port), fr)
        self.assertAlmostEqual(res["betas"]["Market"], 2.0, places=2)
        self.assertAlmostEqual(res["betas"]["Oil"], -1.0, places=2)
        self.assertGreater(res["r_squared"], 0.99)


@unittest.skipUnless(pd is not None, "numpy/pandas not installed")
class ScenarioTests(unittest.TestCase):
    def test_scenario_impact_is_dot_product_over_shared_factors(self) -> None:
        betas = {"Market": 1.0, "Oil": 0.5}
        shocks = {"Market": -0.1, "Oil": 0.2, "Gold": 0.5}  # Gold ignored
        self.assertAlmostEqual(scenario_impact(betas, shocks), 1.0 * -0.1 + 0.5 * 0.2)

    def test_scenarios_only_reference_defined_factors(self) -> None:
        valid = set(FACTORS)
        for name, shocks in SCENARIOS.items():
            self.assertTrue(set(shocks) <= valid, f"{name} references unknown factor")


if __name__ == "__main__":
    unittest.main()
