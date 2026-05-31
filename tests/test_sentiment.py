"""Accuracy tests for services.sentiment.score_headline.

Lexicon-based scorer (no model). These pin the direction on clear headlines and
document its known limitations (no negation / sarcasm handling) so future changes
don't regress the easy cases.
"""
from __future__ import annotations
import unittest

try:
    from services.sentiment import score_headline
except ModuleNotFoundError:  # pragma: no cover
    score_headline = None


@unittest.skipUnless(score_headline is not None, "sentiment module missing")
class SentimentTests(unittest.TestCase):
    def test_clearly_bullish_scores_high(self) -> None:
        for h in ("Apple shares surge after earnings beat and record revenue",
                  "Nvidia rallies to all-time high on strong AI demand",
                  "Analyst upgrades stock to buy, sees outperform and growth"):
            self.assertGreater(score_headline(h), 0.6, h)

    def test_clearly_bearish_scores_low(self) -> None:
        for h in ("Tesla plunges on profit miss and analyst downgrade",
                  "Bank crashes amid fraud probe and mounting losses",
                  "Shares tumble on weak outlook, layoffs and debt concerns"):
            self.assertLess(score_headline(h), 0.4, h)

    def test_neutral_headline_is_mid(self) -> None:
        for h in ("Company announces annual shareholder meeting date",
                  "CEO to speak at industry conference next week"):
            self.assertAlmostEqual(score_headline(h), 0.5, delta=0.01, msg=h)

    def test_mixed_headline_is_between(self) -> None:
        # "beats but warns" — one positive, one negative -> near neutral.
        s = score_headline("Company beats earnings but warns on weak guidance")
        self.assertTrue(0.3 <= s <= 0.7)

    def test_output_always_bounded(self) -> None:
        for h in ("surge rally beat gain profit growth strong record win",
                  "crash plunge fraud loss default lawsuit fear selloff"):
            s = score_headline(h)
            self.assertTrue(0.0 <= s <= 1.0)

    def test_known_limitation_no_negation_handling(self) -> None:
        # DOCUMENTED: the lexicon ignores negation, so "not strong" still reads
        # the positive token. This is a known gap, asserted so it's explicit.
        self.assertGreater(score_headline("shares do not surge, no growth at all"), 0.5)


if __name__ == "__main__":
    unittest.main()
