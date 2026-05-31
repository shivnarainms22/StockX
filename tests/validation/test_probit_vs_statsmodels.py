"""Validate services.yield_curve.fit_recession_probit (Nelder-Mead MLE) against
statsmodels.Probit (Newton/IRLS) on identical data. Both maximize the same
log-likelihood, so the fitted coefficients must agree.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import statsmodels.api as sm
    from scipy.stats import norm
    from services.yield_curve import (
        fit_recession_probit,
        recession_probability_from_coef,
    )
except ModuleNotFoundError:  # pragma: no cover
    sm = None


@unittest.skipUnless(sm is not None, "validate extras (statsmodels) not installed")
class ProbitVsStatsmodels(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(11)
        n = 4000
        spread = rng.normal(1.0, 1.5, n)            # 10y-3m spread, %
        true_b0, true_b1 = 0.5, -1.2                # inversion -> higher P(recession)
        p = norm.cdf(true_b0 + true_b1 * spread)
        y = (rng.uniform(size=n) < p).astype(float)
        cls.spread, cls.y = spread, y
        cls.b0, cls.b1 = fit_recession_probit(spread, y)
        X = sm.add_constant(spread)
        cls.sm_res = sm.Probit(y, X).fit(disp=0)

    def test_intercept_matches_statsmodels(self) -> None:
        # Both maximize the same concave log-likelihood; the actual gap is ~1e-4,
        # so a tight delta also catches a degenerate / unconverged MLE.
        self.assertAlmostEqual(self.b0, self.sm_res.params[0], delta=5e-3)

    def test_slope_matches_statsmodels(self) -> None:
        self.assertAlmostEqual(self.b1, self.sm_res.params[1], delta=5e-3)

    def test_predicted_probability_matches_statsmodels(self) -> None:
        for s in (-1.0, 0.0, 1.5, 3.0):
            mine = recession_probability_from_coef(self.b0, self.b1, s)
            theirs = float(self.sm_res.predict([1.0, s])[0])
            self.assertAlmostEqual(mine, theirs, delta=5e-3)

    def test_inversion_raises_recession_probability(self) -> None:
        # Economic sanity: inverted (negative) spread => higher P than steep curve.
        p_inverted = recession_probability_from_coef(self.b0, self.b1, -1.0)
        p_steep = recession_probability_from_coef(self.b0, self.b1, 3.0)
        self.assertGreater(p_inverted, p_steep)


if __name__ == "__main__":
    unittest.main()
