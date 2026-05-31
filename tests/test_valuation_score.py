"""Unit tests for tools.stock._valuation_score — the analyst-upside + forward-
valuation component added to fix the score's valuation blind spot (audit W1).
"""
from __future__ import annotations
import unittest

try:
    from tools.stock import _valuation_score
except ModuleNotFoundError:  # pragma: no cover - tool deps not installed
    _valuation_score = None


@unittest.skipUnless(_valuation_score is not None, "tool dependencies not installed")
class ValuationScoreTests(unittest.TestCase):
    def test_strong_upside_rewarded(self) -> None:
        pts, sigs = _valuation_score(0.30, 20.0)
        self.assertGreaterEqual(pts, 3)
        self.assertTrue(sigs)

    def test_near_zero_upside_is_penalized_not_neutral(self) -> None:
        # The AAPL case: ~0% implied upside must cost points, not be ignored.
        pts, _ = _valuation_score(-0.005, 32.0)
        self.assertLess(pts, 0)

    def test_large_negative_upside_penalized_hard(self) -> None:
        # Trades well above analyst target -> material downside risk.
        pts, _ = _valuation_score(-0.15, 18.0)
        self.assertLessEqual(pts, -3)

    def test_rich_forward_pe_penalized(self) -> None:
        cheap, _ = _valuation_score(0.10, 15.0)
        rich, _ = _valuation_score(0.10, 60.0)
        self.assertLess(rich, cheap)

    def test_monotonic_in_upside(self) -> None:
        seq = [_valuation_score(u, 20.0)[0]
               for u in (-0.20, -0.05, 0.0, 0.08, 0.15, 0.30)]
        self.assertEqual(seq, sorted(seq))

    def test_none_inputs_are_neutral(self) -> None:
        self.assertEqual(_valuation_score(None, None), (0, []))


if __name__ == "__main__":
    unittest.main()
