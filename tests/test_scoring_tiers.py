from __future__ import annotations

import unittest

try:
    from tools.stock import _rating_for_total_score
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    _rating_for_total_score = None


@unittest.skipUnless(_rating_for_total_score is not None, "tool dependencies not installed")
class ScoreTierTests(unittest.TestCase):
    def test_score_tiers(self) -> None:
        self.assertEqual(_rating_for_total_score(32), "STRONG BUY")
        self.assertEqual(_rating_for_total_score(25), "BUY")
        self.assertEqual(_rating_for_total_score(16), "WATCH / HOLD")
        self.assertEqual(_rating_for_total_score(8), "CAUTION")
        self.assertEqual(_rating_for_total_score(3), "AVOID")


if __name__ == "__main__":
    unittest.main()
