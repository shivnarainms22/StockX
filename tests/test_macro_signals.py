from __future__ import annotations

import unittest

from services.macro_signals import get_commodity_move_signal, get_fred_signal


class MacroSignalTests(unittest.TestCase):
    def test_unemployment_rising_is_negative(self) -> None:
        signal = get_fred_signal("UNRATE", 5.2, 4.9)
        self.assertEqual(signal["color"], "negative")
        self.assertIn("elevated", signal["zone_label"])

    def test_pmi_contraction_is_negative(self) -> None:
        signal = get_fred_signal("MPMIEM3338M086S", 48.5, 49.6)
        self.assertEqual(signal["color"], "negative")
        self.assertEqual(signal["zone_label"], "contraction")

    def test_extreme_commodity_move_marks_caution(self) -> None:
        signal = get_commodity_move_signal("CL=F", pct_1d=11.0, pct_1w=22.0)
        self.assertEqual(signal["severity"], "extreme")
        self.assertEqual(signal["card_signal"], "caution")
        self.assertTrue(bool(signal["warning"]))


if __name__ == "__main__":
    unittest.main()
