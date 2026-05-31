"""Validate services.optimize (scipy SLSQP) against the closed-form mean-variance
solution on a case where the long-only constraint is non-binding (all weights
positive), so the constrained optimum equals the analytic unconstrained one.

Closed form (sum(w)=1, rf=0):
    min-variance : w = S^-1 1   / (1' S^-1 1)
    max-Sharpe   : w = S^-1 mu  / (1' S^-1 mu)
The oracle is built from the SAME mu/cov the optimizer consumes, isolating the
SLSQP solver's correctness from any data/annualization differences.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    from services.optimize import optimize_portfolio, shrunk_covariance
except ModuleNotFoundError:  # pragma: no cover
    np = None


@unittest.skipUnless(np is not None, "numpy/pandas not installed")
class OptimizeVsClosedForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(7)
        n_days, n_assets = 3000, 3
        # Distinct positive drifts + a well-conditioned covariance → interior
        # (all-positive) optimum so the long-only bound never binds.
        means = np.array([0.0006, 0.0009, 0.0011])
        vols = np.array([0.010, 0.013, 0.016])
        corr = np.array([[1.0, 0.2, 0.1], [0.2, 1.0, 0.25], [0.1, 0.25, 1.0]])
        cov_d = corr * np.outer(vols, vols)
        draws = rng.multivariate_normal(means, cov_d, size=n_days)
        cls.returns_df = pd.DataFrame(draws, columns=["A", "B", "C"])
        cls.mu = cls.returns_df.mean().to_numpy() * 252
        # The optimizer uses the Ledoit-Wolf shrunk covariance, so the closed-form
        # oracle must use the same Sigma to validate the solver (not the estimator).
        cls.cov = shrunk_covariance(cls.returns_df) * 252
        inv = np.linalg.inv(cls.cov)
        ones = np.ones(3)
        cls.w_minvar = inv @ ones / (ones @ inv @ ones)
        cls.w_tangency = inv @ cls.mu / (ones @ inv @ cls.mu)
        cls.res = optimize_portfolio(cls.returns_df, rf=0.0)

    def test_precondition_optimum_is_interior(self) -> None:
        # Guards the assumption the long-only bound is non-binding.
        self.assertTrue(np.all(self.w_minvar > 0), self.w_minvar)
        self.assertTrue(np.all(self.w_tangency > 0), self.w_tangency)

    def test_min_variance_weights_match_closed_form(self) -> None:
        np.testing.assert_allclose(
            self.res.min_var["weights"], self.w_minvar, atol=1e-4
        )

    def test_max_sharpe_weights_match_closed_form(self) -> None:
        np.testing.assert_allclose(
            self.res.max_sharpe["weights"], self.w_tangency, atol=1e-4
        )

    def test_weights_form_a_valid_long_only_simplex(self) -> None:
        for pt in (self.res.min_var, self.res.max_sharpe):
            w = np.array(pt["weights"])
            self.assertAlmostEqual(w.sum(), 1.0, places=6)
            self.assertTrue(np.all(w >= -1e-9), w)

    def test_efficient_frontier_volatility_is_non_decreasing(self) -> None:
        vols = np.array(self.res.frontier_vol)
        rets = np.array(self.res.frontier_ret)
        order = np.argsort(rets)
        vols_sorted = vols[order]
        # Frontier above the min-variance point: higher return costs more vol.
        diffs = np.diff(vols_sorted)
        self.assertTrue(np.all(diffs >= -1e-6), vols_sorted)

    def test_max_sharpe_has_highest_sharpe_on_frontier(self) -> None:
        # Tangency portfolio should not be beaten by any frontier grid point.
        rf = 0.0
        best = self.res.max_sharpe["sharpe"]
        for v, r in zip(self.res.frontier_vol, self.res.frontier_ret):
            s = (r - rf) / v if v > 0 else 0.0
            self.assertLessEqual(s, best + 1e-6)


if __name__ == "__main__":
    unittest.main()
