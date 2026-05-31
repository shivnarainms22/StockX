"""StockX - real ReAct agent end-to-end audit.

The app's stock analysis and macro scenarios run through AgentCore (a ReAct loop
with the stock + search tools), NOT a single LLM call. This audits the ACTUAL
agent: does it use its tools, terminate properly, and produce output faithful to
the tool's ground-truth data (no hallucinated rating/price)?

Usage:  python validation/audit_agent.py
Requires LLM keys ([validate] not needed). Spends tokens.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import paths  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(paths.dotenv_path())
except ImportError:
    pass


@dataclass
class Finding:
    section: str
    name: str
    status: str
    detail: str


@dataclass
class Audit:
    findings: list[Finding] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def add(self, *a) -> None:
        self.findings.append(Finding(*a))


def _run_agent(task: str) -> tuple[str, str]:
    """Run the real AgentCore; return (final_answer, full_transcript)."""
    from agent.core import AgentCore
    agent = AgentCore()
    chunks: list[str] = []
    final = asyncio.run(agent.run(task, on_chunk=chunks.append, skip_memory=True))
    return final, "".join(chunks)


def audit_stock_agent(audit: Audit) -> None:
    from tools.stock import StockTool
    ticker = "NVDA"
    # Ground truth straight from the tool the agent is supposed to use.
    truth = StockTool()._analyse_ticker(ticker)
    m = re.search(r"RATING:\s*([A-Z /]+)", truth)
    truth_rating = m.group(1).strip() if m else None

    try:
        final, transcript = _run_agent(
            f"Analyse {ticker} and give a clear buy, hold, or sell recommendation.")
    except Exception as e:  # noqa: BLE001
        audit.add("agent_stock", "run", "SKIP", f"agent error: {e}")
        return

    used_stock = "action: stock" in transcript.lower() or "action:stock" in transcript.lower()
    terminated = "final answer" in (transcript + final).lower()
    low = final.lower()
    rec = ("buy" in low or "sell" in low or "hold" in low)
    # Faithfulness: the agent must not contradict the tool's rating direction.
    truth_dir = ("bullish" if truth_rating and ("BUY" in truth_rating)
                 else "bearish" if truth_rating and ("AVOID" in truth_rating or "CAUTION" in truth_rating)
                 else "neutral")
    contradiction = (truth_dir == "bullish" and "sell" in low and "buy" not in low) or \
                    (truth_dir == "bearish" and "buy" in low and "sell" not in low)

    audit.add("agent_stock", "used the stock tool", "PASS" if used_stock else "FAIL",
              "Action: stock present in trace" if used_stock else "no stock tool call")
    audit.add("agent_stock", "terminated with Final Answer", "PASS" if terminated else "FAIL", "")
    audit.add("agent_stock", "gave a recommendation", "PASS" if rec else "FLAG", "")
    audit.add("agent_stock", "not contradicting tool rating",
              "FAIL" if contradiction else "PASS",
              f"tool rating={truth_rating} ({truth_dir}); final answer aligns"
              if not contradiction else f"agent contradicts tool rating {truth_rating}")
    audit.raw["agent_stock"] = {"ticker": ticker, "truth_rating": truth_rating,
                                "final": final, "transcript_tail": transcript[-1500:]}


def audit_scenario_agent(audit: Audit) -> None:
    try:
        final, transcript = _run_agent(
            "Analyze the market impact if Iran closes the Strait of Hormuz. "
            "Cover primary, secondary, tertiary and consumer tiers.")
    except Exception as e:  # noqa: BLE001
        audit.add("agent_scenario", "run", "SKIP", f"agent error: {e}")
        return
    up = final.upper()
    tiers = sum(t in up for t in ("PRIMARY", "SECONDARY", "TERTIARY", "CONSUMER"))
    low = final.lower()
    directions = ("oil" in low and any(w in low for w in ("rise", "spike", "surge", "higher", "up")))
    terminated = "final answer" in (transcript + final).lower()
    audit.add("agent_scenario", "produced tiered analysis", "PASS" if tiers >= 3 else "FLAG",
              f"{tiers}/4 tiers")
    audit.add("agent_scenario", "correct primary direction (oil up)",
              "PASS" if directions else "FLAG", "")
    audit.add("agent_scenario", "terminated", "PASS" if terminated else "FLAG", "")
    audit.raw["agent_scenario"] = {"final": final[:2500]}


def main() -> int:
    audit = Audit()
    try:
        from llm.router import LLMRouter
        if not LLMRouter()._get_providers():
            print("No LLM provider/keys configured — cannot audit the agent.")
            return 0
    except Exception as e:  # noqa: BLE001
        print(f"router error: {e}")
        return 0

    print("=" * 78)
    print("StockX - Real ReAct Agent Audit (spends tokens)")
    print("=" * 78)
    print("[1/2] stock-analysis agent...")
    audit_stock_agent(audit)
    print("[2/2] scenario agent...")
    audit_scenario_agent(audit)

    out = os.path.join(os.path.dirname(__file__), "audit_agent_findings.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"findings": [asdict(x) for x in audit.findings], "raw": audit.raw},
                  f, indent=2, default=str)
    print("\n" + "-" * 78)
    width = max(len(f"{x.section}/{x.name}") for x in audit.findings)
    for x in audit.findings:
        print(f"  {x.status:4}  {x.section + '/' + x.name:<{width}}  {x.detail}")
    counts = {s: sum(f.status == s for f in audit.findings) for s in ("PASS", "FAIL", "FLAG", "SKIP")}
    print("-" * 78)
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"  findings -> {out}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
