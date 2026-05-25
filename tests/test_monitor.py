"""Tests for the alert-monitor confidence math.

These pure helpers drive the confidence-gating that decides whether a watchlist
alert is allowed to fire, so their boundary behaviour is worth pinning down.
"""
from __future__ import annotations

import unittest

try:
    from services.monitor import (
        _clamp,
        _price_cross_confidence,
        _rsi_confidence,
        _target_confidence,
    )
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    _clamp = _price_cross_confidence = _rsi_confidence = _target_confidence = None


@unittest.skipUnless(_clamp is not None, "monitor dependencies not installed")
class ClampTests(unittest.TestCase):
    def test_within_range_unchanged(self) -> None:
        self.assertEqual(_clamp(5.0, 0.0, 10.0), 5.0)

    def test_below_floor_clamped_up(self) -> None:
        self.assertEqual(_clamp(-1.0, 0.0, 10.0), 0.0)

    def test_above_ceiling_clamped_down(self) -> None:
        self.assertEqual(_clamp(11.0, 0.0, 10.0), 10.0)


@unittest.skipUnless(_price_cross_confidence is not None, "monitor dependencies not installed")
class PriceCrossConfidenceTests(unittest.TestCase):
    def test_nonpositive_threshold_is_neutral(self) -> None:
        self.assertEqual(_price_cross_confidence(50.0, 0.0), 0.5)
        self.assertEqual(_price_cross_confidence(50.0, -5.0), 0.5)

    def test_at_threshold_is_base(self) -> None:
        self.assertAlmostEqual(_price_cross_confidence(100.0, 100.0), 0.55)

    def test_far_from_threshold_caps_at_ceiling(self) -> None:
        # distance 1.0 -> 0.55 + min(4.0, 0.35) = 0.90
        self.assertAlmostEqual(_price_cross_confidence(200.0, 100.0), 0.90)

    def test_small_distance_scales_linearly(self) -> None:
        # distance 0.01 -> 0.55 + 0.04 = 0.59
        self.assertAlmostEqual(_price_cross_confidence(101.0, 100.0), 0.59)


@unittest.skipUnless(_rsi_confidence is not None, "monitor dependencies not installed")
class RsiConfidenceTests(unittest.TestCase):
    def test_at_threshold_is_base(self) -> None:
        self.assertAlmostEqual(_rsi_confidence(70.0, 70.0), 0.55)

    def test_max_distance_caps_at_ceiling(self) -> None:
        # distance 1.0 -> 0.55 + min(2.0, 0.35) = 0.90
        self.assertAlmostEqual(_rsi_confidence(100.0, 0.0), 0.90)

    def test_small_distance_scales(self) -> None:
        # distance 0.05 -> 0.55 + 0.10 = 0.65
        self.assertAlmostEqual(_rsi_confidence(75.0, 70.0), 0.65)


@unittest.skipUnless(_target_confidence is not None, "monitor dependencies not installed")
class TargetConfidenceTests(unittest.TestCase):
    def test_nonpositive_target_is_neutral(self) -> None:
        self.assertEqual(_target_confidence(100.0, 0.0), 0.5)

    def test_exactly_on_target_is_highest(self) -> None:
        self.assertAlmostEqual(_target_confidence(100.0, 100.0), 0.90)

    def test_at_two_percent_boundary_drops_to_base(self) -> None:
        self.assertAlmostEqual(_target_confidence(102.0, 100.0), 0.55)

    def test_halfway_into_band_is_midpoint(self) -> None:
        # distance 0.01 -> closeness 0.5 -> 0.55 + 0.175 = 0.725
        self.assertAlmostEqual(_target_confidence(101.0, 100.0), 0.725)

    def test_far_outside_band_stays_at_base(self) -> None:
        self.assertAlmostEqual(_target_confidence(110.0, 100.0), 0.55)


if __name__ == "__main__":
    unittest.main()
