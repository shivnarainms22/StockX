"""Validate services.knowledge.build_knowledge_context — the grounding layer for
the LLM scenario engine. If injection is wrong, the model is fed wrong facts.

Pure function, fully hermetic.
"""
from __future__ import annotations
import unittest

try:
    from services.knowledge import build_knowledge_context, DEMAND_DESTRUCTION
except ModuleNotFoundError:  # pragma: no cover
    build_knowledge_context = None


@unittest.skipUnless(build_knowledge_context is not None, "knowledge module missing")
class KnowledgeContext(unittest.TestCase):
    def test_hormuz_scenario_injects_chokepoint_data(self) -> None:
        ctx = build_knowledge_context("Iran closes the Strait of Hormuz", 6, None)
        self.assertIn("Strait of Hormuz", ctx)
        self.assertIn("21%", ctx)                 # global oil share fact

    def test_chokepoint_alone_does_not_chain_to_commodity_data(self) -> None:
        # DOCUMENTED LIMITATION: injection is keyword-literal. A Hormuz scenario
        # that never says "oil" gets the chokepoint block but NOT oil pass-through
        # or EM-vulnerability data, even though the chokepoint IS about oil.
        ctx = build_knowledge_context("Iran closes the Strait of Hormuz", 6, None)
        self.assertNotIn("INFLATION PASS-THROUGH", ctx)
        # Naming the commodity does pull it in (and EM data carries the INR fact):
        ctx2 = build_knowledge_context("Strait of Hormuz oil crisis", 6, None)
        self.assertIn("INFLATION PASS-THROUGH", ctx2)
        self.assertIn("INR", ctx2)

    def test_wheat_war_scenario_injects_wheat_crisis_and_egypt(self) -> None:
        ctx = build_knowledge_context(
            "Russia invasion disrupts Ukraine wheat exports", 3, None)
        self.assertIn("HISTORICAL PARALLEL", ctx)
        self.assertIn("Egypt", ctx)               # EM vulnerability for wheat
        self.assertIn("wheat", ctx.lower())

    def test_red_sea_scenario_injects_bab_el_mandeb(self) -> None:
        ctx = build_knowledge_context("Houthi attacks in the Red Sea", 1, None)
        self.assertIn("Bab-el-Mandeb", ctx)

    def test_seasonal_injected_for_current_month(self) -> None:
        # Nat gas in December should surface the winter-heating bullish pattern.
        ctx = build_knowledge_context("natural gas supply shock", 12, None)
        self.assertIn("SEASONAL", ctx)

    def test_demand_destruction_fires_only_above_threshold(self) -> None:
        thr = DEMAND_DESTRUCTION["CL=F"]["threshold_price"]
        below = build_knowledge_context("oil crisis", 6, {"CL=F": thr - 10})
        above = build_knowledge_context("oil crisis", 6, {"CL=F": thr + 10})
        self.assertNotIn("DEMAND DESTRUCTION WARNING", below)
        self.assertIn("DEMAND DESTRUCTION WARNING", above)

    def test_irrelevant_scenario_returns_empty(self) -> None:
        # No commodity/chokepoint keywords -> no fabricated context.
        self.assertEqual(build_knowledge_context("a quiet day with no news", 5, None), "")


if __name__ == "__main__":
    unittest.main()
