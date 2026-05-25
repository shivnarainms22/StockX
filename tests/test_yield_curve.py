from __future__ import annotations
import unittest

try:
    import numpy as np
    from services.yield_curve import (
        fit_recession_probit, recession_probability_from_coef,
        fetch_yield_curve, recession_probability,
    )
except ModuleNotFoundError:  # pragma: no cover
    np = None


@unittest.skipUnless(np is not None, "scipy/numpy not installed")
class ProbitTests(unittest.TestCase):
    def test_inverted_curve_implies_higher_recession_prob(self) -> None:
        rng = np.random.default_rng(0)
        spread = rng.uniform(-2.0, 3.0, 600)
        recession = (spread < 0).astype(float)  # clear inverse relationship
        b0, b1 = fit_recession_probit(spread, recession)
        self.assertLess(b1, 0)
        p_inv = recession_probability_from_coef(b0, b1, -1.0)
        p_steep = recession_probability_from_coef(b0, b1, 2.0)
        self.assertGreater(p_inv, p_steep)

    def test_probability_is_bounded(self) -> None:
        p = recession_probability_from_coef(-0.5, -0.6, -3.0)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)


@unittest.skipUnless(np is not None, "scipy/numpy not installed")
class NoKeySafetyTests(unittest.TestCase):
    def test_fetchers_return_none_without_key(self) -> None:
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"FRED_API_KEY": ""}, clear=False):
            self.assertIsNone(fetch_yield_curve())
            self.assertIsNone(recession_probability())


if __name__ == "__main__":
    unittest.main()
