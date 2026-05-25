from __future__ import annotations
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy as np
    import pandas as pd
    from PyQt6.QtCore import QCoreApplication  # noqa: F401
    from gui.views.optimize import _run_optimize_job
except ModuleNotFoundError:  # pragma: no cover
    pd = None


@unittest.skipUnless(pd is not None, "PyQt6/scipy not installed")
class OptimizeJobTests(unittest.TestCase):
    def test_job_returns_result_and_png(self) -> None:
        rng = np.random.default_rng(0)
        idx = pd.date_range("2020-01-01", periods=300, freq="B")
        df = pd.DataFrame({"A": rng.normal(0.0005, 0.01, 300),
                           "B": rng.normal(0.0003, 0.02, 300)}, index=idx)
        result, png = _run_optimize_job(df, current_weights=[0.5, 0.5])
        self.assertIn("weights", result.max_sharpe)
        self.assertIsInstance(png, (bytes, bytearray))


if __name__ == "__main__":
    unittest.main()
