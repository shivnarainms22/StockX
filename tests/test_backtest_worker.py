from __future__ import annotations
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import pandas as pd
    from PyQt6.QtCore import QCoreApplication  # noqa: F401
    from gui.views.backtest import _run_backtest_job
except ModuleNotFoundError:  # pragma: no cover
    pd = None


def _hist(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [1] * len(closes)},
        index=idx,
    )


@unittest.skipUnless(pd is not None, "PyQt6/pandas not installed")
class BacktestJobTests(unittest.TestCase):
    def test_job_returns_result_and_png(self) -> None:
        from services.backtest import sma_crossover
        result, png = _run_backtest_job(
            _hist([100.0 + (i % 7) for i in range(60)]),
            sma_crossover(3, 8), initial_cash=5_000,
        )
        self.assertIn("sharpe", result.metrics)
        self.assertIsInstance(png, (bytes, bytearray))


if __name__ == "__main__":
    unittest.main()
