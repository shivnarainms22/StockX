from __future__ import annotations
import unittest

try:
    import numpy as np
    import pandas as pd
    from services.optimize import optimize_portfolio, OptimizeResult
except ModuleNotFoundError:  # pragma: no cover
    pd = None


def _returns(cols: dict, n: int = 300, seed: int = 1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    data = {name: rng.normal(mu, sd, n) for name, (mu, sd) in cols.items()}
    return pd.DataFrame(data, index=idx)


@unittest.skipUnless(pd is not None, "scipy/pandas not installed")
class OptimizeTests(unittest.TestCase):
    def test_weights_long_only_and_sum_to_one(self) -> None:
        df = _returns({"A": (0.0005, 0.01), "B": (0.0003, 0.02), "C": (0.0004, 0.015)})
        res = optimize_portfolio(df)
        w = res.max_sharpe["weights"]
        self.assertAlmostEqual(sum(w), 1.0, places=4)
        self.assertTrue(all(x >= -1e-6 for x in w))

    def test_max_sharpe_favors_dominant_asset(self) -> None:
        # A: higher return, lower vol -> should dominate the max-Sharpe weights.
        df = _returns({"A": (0.0010, 0.008), "B": (0.0001, 0.020)})
        res = optimize_portfolio(df)
        self.assertGreater(res.max_sharpe["weights"][0], res.max_sharpe["weights"][1])

    def test_min_variance_matches_analytic_two_asset(self) -> None:
        # Uncorrelated; analytic min-var weight on A = varB/(varA+varB).
        df = _returns({"A": (0.0, 0.02), "B": (0.0, 0.01)}, n=2000, seed=7)
        res = optimize_portfolio(df)
        cov = df.cov()
        va, vb = cov.iloc[0, 0], cov.iloc[1, 1]
        expected_a = vb / (va + vb)
        self.assertAlmostEqual(res.min_var["weights"][0], expected_a, places=2)

    def test_frontier_is_monotonic(self) -> None:
        df = _returns({"A": (0.0005, 0.01), "B": (0.0003, 0.02)})
        res = optimize_portfolio(df)
        # sort by return; vol should be non-decreasing along the efficient frontier
        pairs = sorted(zip(res.frontier_ret, res.frontier_vol))
        vols = [v for _, v in pairs]
        self.assertTrue(all(b >= a - 1e-6 for a, b in zip(vols, vols[1:])))

    def test_current_point_present_when_weights_passed(self) -> None:
        df = _returns({"A": (0.0005, 0.01), "B": (0.0003, 0.02)})
        res = optimize_portfolio(df, current_weights=[0.5, 0.5])
        self.assertIsNotNone(res.current)
        self.assertAlmostEqual(sum(res.current["weights"]), 1.0, places=4)

    def test_single_asset_weight_is_one(self) -> None:
        df = _returns({"A": (0.0005, 0.01)})
        res = optimize_portfolio(df)
        self.assertAlmostEqual(res.max_sharpe["weights"][0], 1.0, places=4)


@unittest.skipUnless(pd is not None, "scipy/pandas not installed")
class FrontierChartTests(unittest.TestCase):
    def test_render_returns_png(self) -> None:
        from services.charting import render_efficient_frontier
        df = _returns({"A": (0.0005, 0.01), "B": (0.0003, 0.02)})
        res = optimize_portfolio(df, current_weights=[0.5, 0.5])
        png = render_efficient_frontier(res)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_render_empty_frontier_returns_empty(self) -> None:
        from services.charting import render_efficient_frontier
        empty = OptimizeResult([], [], [], {}, {}, None)
        self.assertEqual(render_efficient_frontier(empty), b"")


if __name__ == "__main__":
    unittest.main()
