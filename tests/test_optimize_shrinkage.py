"""Tests for the robust-optimizer upgrade: Ledoit-Wolf shrinkage covariance and
the per-asset weight cap. Shrinkage is validated against sklearn's reference.
"""
from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    from services.optimize import shrunk_covariance, optimize_portfolio
    try:
        from sklearn.covariance import ledoit_wolf
        HAVE_SK = True
    except ImportError:  # pragma: no cover
        HAVE_SK = False
except ModuleNotFoundError:  # pragma: no cover
    np = None


def _noisy(T: int, N: int, seed: int = 2) -> "pd.DataFrame":
    """One common factor + idiosyncratic noise -> realistic correlated returns."""
    rng = np.random.default_rng(seed)
    f = rng.normal(0.0, 0.01, (T, 1))
    loadings = rng.normal(1.0, 0.3, (1, N))
    X = f @ loadings + rng.normal(0.0, 0.008, (T, N))
    return pd.DataFrame(X, columns=[f"A{i}" for i in range(N)])


@unittest.skipUnless(np is not None, "scipy/pandas not installed")
class Shrinkage(unittest.TestCase):
    def test_symmetric(self) -> None:
        cov = shrunk_covariance(_noisy(120, 6))
        np.testing.assert_allclose(cov, cov.T, atol=1e-12)

    def test_positive_semidefinite(self) -> None:
        cov = shrunk_covariance(_noisy(80, 10))
        self.assertGreaterEqual(float(np.linalg.eigvalsh(cov).min()), -1e-10)

    def test_better_or_equal_conditioned_than_sample(self) -> None:
        df = _noisy(40, 12)  # small T, many assets -> ill-conditioned sample cov
        Xc = df.to_numpy() - df.to_numpy().mean(axis=0)
        sample = Xc.T @ Xc / len(df)
        self.assertLessEqual(np.linalg.cond(shrunk_covariance(df)),
                             np.linalg.cond(sample) + 1e-9)

    @unittest.skipUnless(HAVE_SK, "sklearn (validate extra) not installed")
    def test_matches_sklearn_ledoit_wolf(self) -> None:
        df = _noisy(150, 7, seed=11)
        ref, _shrink = ledoit_wolf(df.to_numpy())
        np.testing.assert_allclose(shrunk_covariance(df), ref, atol=1e-10)


@unittest.skipUnless(np is not None, "scipy/pandas not installed")
class WeightCap(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(5)
        means = [0.0008, 0.0006, 0.0010, 0.0004, 0.0007]
        cls.df = pd.DataFrame(rng.normal(means, 0.012, (800, 5)), columns=list("ABCDE"))

    def test_cap_respected_for_max_sharpe_and_min_var(self) -> None:
        res = optimize_portfolio(self.df, max_weight=0.30)
        for pt in (res.max_sharpe, res.min_var):
            w = np.array(pt["weights"])
            self.assertLessEqual(w.max(), 0.30 + 1e-6)
            self.assertAlmostEqual(w.sum(), 1.0, places=6)

    def test_infeasible_cap_clamps_to_equal_weight_floor(self) -> None:
        # n=2 with cap 0.30 is infeasible (0.6 < 1); effective cap becomes 0.5.
        res = optimize_portfolio(self.df[["A", "B"]], max_weight=0.30)
        w = np.array(res.max_sharpe["weights"])
        self.assertLessEqual(w.max(), 0.5 + 1e-6)
        self.assertAlmostEqual(w.sum(), 1.0, places=6)

    def test_frontier_monotonic_under_cap(self) -> None:
        res = optimize_portfolio(self.df, max_weight=0.30)
        order = np.argsort(res.frontier_ret)
        vols = np.array(res.frontier_vol)[order]
        self.assertTrue(np.all(np.diff(vols) >= -1e-6))

    def test_no_cap_is_backward_compatible(self) -> None:
        res = optimize_portfolio(self.df)  # max_weight=None
        w = np.array(res.max_sharpe["weights"])
        self.assertAlmostEqual(w.sum(), 1.0, places=6)
        self.assertTrue(np.all(w >= -1e-9))


if __name__ == "__main__":
    unittest.main()
