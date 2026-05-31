"""Tests for the pure portfolio math extracted from PortfolioView:
value/cost aggregation and trailing-twelve-month dividend (incl. the tz-aware
yfinance index that previously raised and silently zeroed dividend income).
"""
from __future__ import annotations
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import pandas as pd
    from gui.views.portfolio import aggregate_by_currency, ttm_dividend
except Exception:  # pragma: no cover - Qt/import unavailable
    aggregate_by_currency = None


@unittest.skipUnless(aggregate_by_currency is not None, "Qt/gui import unavailable")
class AggregateByCurrency(unittest.TestCase):
    def test_single_currency_value_and_cost(self) -> None:
        pf = [{"ticker": "AAA", "qty": 10, "avg_cost": 50.0},
              {"ticker": "BBB", "qty": 5, "avg_cost": 80.0}]
        prices = {"AAA": 60.0, "BBB": 100.0}
        out = aggregate_by_currency(pf, prices, {"AAA": "USD", "BBB": "USD"})
        # value 10*60 + 5*100 = 1100 ; cost 10*50 + 5*80 = 900
        self.assertEqual(out["USD"], (1100.0, 900.0))

    def test_currencies_kept_separate(self) -> None:
        pf = [{"ticker": "AAA", "qty": 1, "avg_cost": 100.0},
              {"ticker": "RR.NS", "qty": 2, "avg_cost": 50.0}]
        out = aggregate_by_currency(
            pf, {"AAA": 110.0, "RR.NS": 60.0}, {"AAA": "USD", "RR.NS": "INR"})
        self.assertEqual(set(out), {"USD", "INR"})
        self.assertEqual(out["USD"], (110.0, 100.0))
        self.assertEqual(out["INR"], (120.0, 100.0))

    def test_missing_price_falls_back_to_cost_flat(self) -> None:
        pf = [{"ticker": "AAA", "qty": 4, "avg_cost": 25.0}]
        out = aggregate_by_currency(pf, {}, {})  # no price, no currency
        self.assertEqual(out["USD"], (100.0, 100.0))  # value == cost (flat)

    def test_empty_portfolio(self) -> None:
        self.assertEqual(aggregate_by_currency([], {}, {}), {})


@unittest.skipUnless(aggregate_by_currency is not None, "pandas/gui unavailable")
class TtmDividend(unittest.TestCase):
    def test_tz_aware_index_does_not_raise_and_sums_last_year(self) -> None:
        # yfinance returns a tz-aware index; this previously raised TypeError.
        recent = pd.Timestamp.now(tz="America/New_York")
        idx = pd.DatetimeIndex([recent - pd.DateOffset(months=m) for m in (1, 4, 7, 10, 14)])
        divs = pd.Series([0.25, 0.25, 0.25, 0.25, 0.25], index=idx)
        # Last 12 months -> the 4 within a year (the 14-month-old one excluded).
        self.assertAlmostEqual(ttm_dividend(divs), 1.00, places=6)

    def test_tz_naive_index_works(self) -> None:
        now = pd.Timestamp.now()
        idx = pd.DatetimeIndex([now - pd.DateOffset(months=m) for m in (2, 5, 8, 11)])
        divs = pd.Series([0.5] * 4, index=idx)
        self.assertAlmostEqual(ttm_dividend(divs), 2.0, places=6)

    def test_empty_or_none_is_zero(self) -> None:
        self.assertEqual(ttm_dividend(pd.Series([], dtype=float)), 0.0)
        self.assertEqual(ttm_dividend(None), 0.0)


if __name__ == "__main__":
    unittest.main()
