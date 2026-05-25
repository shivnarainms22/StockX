from __future__ import annotations
import unittest

from services.knowledge import CHOKEPOINTS, CRISIS_PARALLELS, build_knowledge_context


class KnowledgeAdditionsTests(unittest.TestCase):
    def test_bab_el_mandeb_present_and_complete(self) -> None:
        self.assertIn("bab_el_mandeb", CHOKEPOINTS)
        cp = CHOKEPOINTS["bab_el_mandeb"]
        for key in ("name", "global_oil_pct", "daily_flow_mbpd", "connects",
                    "countries_dependent", "historical_disruption"):
            self.assertIn(key, cp)

    def test_bab_el_mandeb_retrievable_by_keyword(self) -> None:
        ctx = build_knowledge_context(
            "Houthi attacks disrupt the Bab-el-Mandeb / Red Sea", 1)
        self.assertIn("Bab-el-Mandeb", ctx)

    def test_new_crises_present(self) -> None:
        names = {c["name"] for c in CRISIS_PARALLELS}
        self.assertTrue(any("Red Sea" in n for n in names))
        self.assertTrue(any("Asian" in n for n in names))
        self.assertTrue(any("Eurozone" in n for n in names))

    def test_crisis_entries_have_required_keys(self) -> None:
        for c in CRISIS_PARALLELS:
            for key in ("name", "year", "trigger", "duration_months", "impacts", "resolution"):
                self.assertIn(key, c)

    def test_new_crisis_retrievable_by_keyword(self) -> None:
        ctx = build_knowledge_context("Eurozone sovereign debt crisis fears return", 1)
        self.assertIn("Eurozone", ctx)


if __name__ == "__main__":
    unittest.main()
