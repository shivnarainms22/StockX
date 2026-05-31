"""Validate the Macro view's _compute_risk_metrics (VaR / max-drawdown /
commodity betas / stress) against an independent recomputation on identical data.

The function embeds a yfinance.download call, so we mock ONLY that network call
(returning deterministic synthetic OHLC) and exercise the real math. This also
surfaces the commodity-beta ddof inconsistency (cov ddof=1 / var ddof=0).
"""
from __future__ import annotations
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy as np
    import pandas as pd
    from gui.views.macro import _compute_risk_metrics, _SYMBOL_NAMES
except Exception:  # pragma: no cover - Qt/import unavailable
    _compute_risk_metrics = None

_COMMODITIES = ["CL=F", "GC=F", "NG=F", "HG=F"]


def _fake_download_frame(tickers: list[str], n: int = 80, seed: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-02", periods=n, freq="B")
    closes = {}
    for i, t in enumerate(tickers):
        closes[t] = 100.0 * np.cumprod(1 + rng.normal(0.0004, 0.013 + 0.002 * i, n))
    close_df = pd.DataFrame(closes, index=idx)
    # Mimic yfinance multi-ticker shape: MultiIndex columns (field, ticker).
    cols = pd.MultiIndex.from_product([["Close"], tickers])
    return pd.DataFrame(close_df.values, index=idx, columns=cols)


@unittest.skipUnless(_compute_risk_metrics is not None, "Qt/gui import unavailable")
class RiskMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.portfolio = [
            {"ticker": "AAA", "qty": 10.0, "avg_cost": 50.0},
            {"ticker": "BBB", "qty": 5.0, "avg_cost": 80.0},
        ]
        all_syms = list(set(["AAA", "BBB"] + _COMMODITIES + ["SPY"]))
        cls.frame = _fake_download_frame(all_syms)
        with patch("yfinance.download", return_value=cls.frame):
            cls.result = _compute_risk_metrics(cls.portfolio)

        # Independent recomputation on the same closes.
        closes = cls.frame["Close"].dropna(how="all")
        rets = closes.pct_change().dropna()
        w = {"AAA": 10 * 50, "BBB": 5 * 80}
        tot = sum(w.values())
        w = {k: v / tot for k, v in w.items()}
        port = np.zeros(len(rets))
        for t, wt in w.items():
            port += rets[t].fillna(0).values * wt
        cls.port = port
        cls.rets = rets

    def test_var_95_is_5th_percentile(self) -> None:
        self.assertAlmostEqual(self.result["var_95"],
                               float(np.percentile(self.port, 5) * 100), places=6)

    def test_var_99_is_1st_percentile(self) -> None:
        self.assertAlmostEqual(self.result["var_99"],
                               float(np.percentile(self.port, 1) * 100), places=6)

    def test_max_drawdown_matches(self) -> None:
        cum = np.cumprod(1 + self.port)
        dd = (cum - np.maximum.accumulate(cum)) / np.maximum.accumulate(cum) * 100
        self.assertAlmostEqual(self.result["max_drawdown"], float(np.min(dd)), places=6)

    def test_commodity_beta_uses_mixed_ddof(self) -> None:
        # Reproduce StockX's exact (mixed-ddof) formula and confirm the function
        # matches it — documenting that the result is cov(ddof=1)/var(ddof=0),
        # i.e. biased high by n/(n-1) vs a consistent-ddof beta.
        cr = self.rets["CL=F"].fillna(0).values
        mixed = float(np.cov(self.port, cr)[0, 1] / np.var(cr))            # as implemented
        beta_var_ddof1 = float(np.cov(self.port, cr)[0, 1] / np.var(cr, ddof=1))
        name = _SYMBOL_NAMES.get("CL=F", "CL=F")
        self.assertAlmostEqual(self.result["commodity_betas"][name], mixed, places=6)
        n = len(cr)
        self.assertAlmostEqual(mixed / beta_var_ddof1, n / (n - 1), places=6)

    def test_stress_test_is_beta_times_move(self) -> None:
        name = _SYMBOL_NAMES.get("CL=F", "CL=F")
        beta = self.result["commodity_betas"][name]
        plus20 = next(s for s in self.result["stress_tests"]
                      if s["commodity"] == name and s["move"] == "+20%")
        self.assertAlmostEqual(plus20["portfolio_impact"], round(beta * 20, 2), places=2)


if __name__ == "__main__":
    unittest.main()
