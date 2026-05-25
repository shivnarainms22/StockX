from __future__ import annotations
import unittest

try:
    import pandas as pd
    from services import perf_metrics as pm
except ModuleNotFoundError:  # pragma: no cover
    pm = None


@unittest.skipUnless(pm is not None, "pandas not installed")
class PerfMetricsTests(unittest.TestCase):
    def test_total_return(self) -> None:
        eq = pd.Series([100.0, 110.0, 130.0])
        self.assertAlmostEqual(pm.total_return(eq), 0.30)

    def test_total_return_empty_is_zero(self) -> None:
        self.assertEqual(pm.total_return(pd.Series([], dtype=float)), 0.0)

    def test_max_drawdown(self) -> None:
        eq = pd.Series([100.0, 120.0, 90.0, 130.0])  # trough 90 vs peak 120
        self.assertAlmostEqual(pm.max_drawdown(eq), -0.25)

    def test_sharpe_zero_when_no_variance(self) -> None:
        self.assertEqual(pm.sharpe(pd.Series([0.0, 0.0, 0.0])), 0.0)

    def test_sharpe_positive_for_steady_gains(self) -> None:
        self.assertGreater(pm.sharpe(pd.Series([0.01] * 252 + [0.005] * 10)), 0.0)

    def test_win_rate(self) -> None:
        self.assertAlmostEqual(pm.win_rate([0.1, -0.05, 0.2]), 2 / 3)

    def test_win_rate_empty_is_zero(self) -> None:
        self.assertEqual(pm.win_rate([]), 0.0)

    def test_exposure(self) -> None:
        self.assertAlmostEqual(pm.exposure(pd.Series([0.0, 1.0, 1.0, 0.0])), 0.5)

    def test_beta_of_series_with_itself_is_one(self) -> None:
        r = pd.Series([0.01, -0.02, 0.03, 0.0, -0.01])
        self.assertAlmostEqual(pm.beta(r, r), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
