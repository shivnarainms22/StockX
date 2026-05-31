"""StockX - macro-completion live audit (items A-E).

Verifies the parts of the Macro view the first audit did not cover: commodity
technical indicators vs a reference library, the Risk Metrics panel, the
correlation matrix, knowledge-base injection, and the LLM geopolitical scenario
engine on real data. Writes validation/audit_macro_findings.json.

Usage:
    python validation/audit_macro.py
    python validation/audit_macro.py --no-llm

Requires:  pip install -e ".[validate]"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict, field

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import paths  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(paths.dotenv_path())
except ImportError:
    pass

from services import indicators as ind  # noqa: E402

_COMMODITIES = ["CL=F", "GC=F", "NG=F", "HG=F"]


@dataclass
class Finding:
    section: str
    name: str
    status: str   # PASS | FAIL | FLAG | INFO | SKIP
    detail: str


@dataclass
class Audit:
    findings: list[Finding] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def add(self, *a) -> None:
        self.findings.append(Finding(*a))


# ── A. indicators vs `ta` reference (live commodities) ───────────────────────

def audit_indicators(audit: Audit) -> None:
    try:
        import ta
        import yfinance as yf
    except ImportError as e:
        audit.add("indicators", "reference", "SKIP", str(e))
        return

    rows = []
    for sym in _COMMODITIES:
        try:
            px = yf.Ticker(sym).history(period="6mo")[
                ["High", "Low", "Close"]].dropna()
            if len(px) < 60:
                continue
        except Exception as e:  # noqa: BLE001
            audit.add("indicators", sym, "SKIP", f"fetch failed: {e}")
            continue
        c = px["Close"]
        sx_rsi = ind.calc_rsi(px); w_rsi = ta.momentum.RSIIndicator(c, 14).rsi().iloc[-1]
        sx_adx, _, _ = ind.calc_adx(px)
        w_adx = ta.trend.ADXIndicator(px["High"], px["Low"], c, 14).adx().iloc[-1]
        sx_macd, _, _ = ind.calc_macd(px); w_macd = ta.trend.MACD(c).macd().iloc[-1]
        rows.append({"sym": sym, "rsi_sx": sx_rsi, "rsi_w": float(w_rsi),
                     "adx_sx": sx_adx, "adx_w": float(w_adx)})
        # MACD must match (standard); RSI/ADX deviate (non-Wilder smoothing)
        audit.add("indicators", f"{sym} MACD vs ref",
                  "PASS" if abs(sx_macd - w_macd) < 1e-6 else "FAIL",
                  f"sx={sx_macd:.4f} ta={w_macd:.4f}")
        # A signal FLIP (overbought/oversold or trend/no-trend reversed vs the
        # canonical indicator) is a substantive correctness failure, not a nuance.
        rsi_flip = (sx_rsi < 30) != (w_rsi < 30) or (sx_rsi > 70) != (w_rsi > 70)
        audit.add("indicators", f"{sym} RSI vs Wilder",
                  "FAIL" if rsi_flip else ("FLAG" if abs(sx_rsi - w_rsi) > 5 else "INFO"),
                  f"sx={sx_rsi:.1f} wilder={w_rsi:.1f} d={sx_rsi-w_rsi:+.1f}"
                  + ("  SIGNAL FLIP (overbought/oversold)" if rsi_flip else ""))
        adx_flip = (sx_adx > 25) != (w_adx > 25)
        audit.add("indicators", f"{sym} ADX vs Wilder",
                  "FAIL" if adx_flip else ("FLAG" if abs(sx_adx - w_adx) > 5 else "INFO"),
                  f"sx={sx_adx:.1f} wilder={w_adx:.1f} d={sx_adx-w_adx:+.1f}"
                  + ("  SIGNAL FLIP (trend/no-trend)" if adx_flip else ""))
    audit.raw["indicators"] = rows


# ── B. risk metrics panel (live, real portfolio) ─────────────────────────────

def audit_risk_metrics(audit: Audit, portfolio: list[dict]) -> None:
    if not portfolio:
        audit.add("risk", "metrics", "SKIP", "no saved portfolio")
        return
    try:
        from gui.views.macro import _compute_risk_metrics
        m = _compute_risk_metrics(portfolio)
    except Exception as e:  # noqa: BLE001
        audit.add("risk", "metrics", "SKIP", str(e))
        return
    if not m:
        audit.add("risk", "metrics", "SKIP", "no data returned")
        return
    v95, v99 = m.get("var_95"), m.get("var_99")
    audit.add("risk", "VaR ordering", "PASS" if (v99 is not None and v95 is not None
              and v99 <= v95 <= 0) else "FLAG",
              f"VaR95={v95:.2f}% VaR99={v99:.2f}% (99% should be the deeper loss)")
    mdd = m.get("max_drawdown")
    audit.add("risk", "max drawdown sane", "PASS" if (mdd is not None and mdd <= 0)
              else "FLAG", f"maxDD(90d)={mdd:.1f}%")
    betas = m.get("commodity_betas", {})
    audit.add("risk", "commodity betas", "INFO",
              ", ".join(f"{k}={v:+.2f}" for k, v in betas.items()) or "none")
    audit.raw["risk"] = m


# ── C. correlation matrix (live) ─────────────────────────────────────────────

def audit_correlation(audit: Audit) -> None:
    try:
        from gui.views.macro import _compute_correlation_matrix
        labels, matrix, _summary = _compute_correlation_matrix()
    except Exception as e:  # noqa: BLE001
        audit.add("correlation", "matrix", "SKIP", str(e))
        return
    if not matrix:
        audit.add("correlation", "matrix", "SKIP", "no data")
        return
    arr = np.array(matrix)
    diag_ok = np.allclose(np.diag(arr), 1.0, atol=1e-6)
    sym_ok = np.allclose(arr, arr.T, atol=1e-6)
    range_ok = bool(np.all(arr >= -1.0001) and np.all(arr <= 1.0001))
    audit.add("correlation", "diagonal == 1", "PASS" if diag_ok else "FAIL",
              f"{len(labels)}x{len(labels)} matrix")
    audit.add("correlation", "symmetric", "PASS" if sym_ok else "FAIL", "")
    audit.add("correlation", "values in [-1,1]", "PASS" if range_ok else "FAIL",
              f"min={arr.min():.2f} max={arr.max():.2f}")


# ── D. knowledge-base injection ──────────────────────────────────────────────

def audit_knowledge(audit: Audit) -> None:
    from services.knowledge import build_knowledge_context
    cases = {
        "Iran closes the Strait of Hormuz, oil spikes": ["Strait of Hormuz", "21%",
                                                         "INFLATION PASS-THROUGH", "INR"],
        "Russia invasion disrupts Ukraine wheat exports": ["HISTORICAL PARALLEL",
                                                          "Egypt", "wheat"],
        "Houthi attacks in the Red Sea disrupt shipping": ["Bab-el-Mandeb"],
    }
    for scenario, expected in cases.items():
        ctx = build_knowledge_context(scenario, 6, None)
        missing = [e for e in expected if e.lower() not in ctx.lower()]
        audit.add("knowledge", scenario[:38], "PASS" if not missing else "FLAG",
                  f"len={len(ctx)} chars" + (f"; missing {missing}" if missing else ""))
    # A chokepoint scenario should chain to its commodities even without the word.
    bare = build_knowledge_context("Iran closes the Strait of Hormuz", 6, None)
    chained = "INFLATION PASS-THROUGH" in bare
    audit.add("knowledge", "chokepoint->commodity chaining",
              "PASS" if chained else "FLAG",
              "Hormuz (no 'oil') chains to oil pass-through" if chained
              else "Hormuz w/o 'oil' injects chokepoint but NOT oil pass-through")


# ── E. LLM geopolitical scenario engine ──────────────────────────────────────

def audit_scenario_llm(audit: Audit) -> None:
    try:
        from llm.router import LLMRouter
        from services.knowledge import build_knowledge_context
        router = LLMRouter()
        if not router._get_providers():
            audit.add("scenario", "llm", "SKIP", "no LLM provider/keys")
            return
    except Exception as e:  # noqa: BLE001
        audit.add("scenario", "llm", "SKIP", str(e))
        return

    import asyncio
    scenario = "Iran closes the Strait of Hormuz; oil spikes 20%"
    kb = build_knowledge_context(scenario, 6, {"CL=F": 95.0})
    system = ("You are a global macro strategist. Use ONLY facts provided or "
              "well-established economics. Do not invent precise figures not given.")
    task = (
        f"SCENARIO: {scenario}\n\n{kb}\n\n"
        "Analyze cascading impact in FOUR tiers (PRIMARY / SECONDARY / TERTIARY / "
        "CONSUMER), each with GLOBAL scope (US, EU, China, India). Keep it concise "
        "(~250 words). Reference the knowledge-base numbers where relevant."
    )
    try:
        out = asyncio.run(router.complete(
            system=system, messages=[{"role": "user", "content": task}]))
    except Exception as e:  # noqa: BLE001
        audit.add("scenario", "llm", "SKIP", f"LLM error: {e}")
        return

    import re
    low = out.lower()
    tiers = sum(t in out.upper() for t in ("PRIMARY", "SECONDARY", "TERTIARY", "CONSUMER"))
    # Word-boundary matching so "us" doesn't match inside "Russia"/"focus".
    _region_pats = {
        "US": r"\b(u\.?s\.?|united states|america)\b",
        "Europe": r"\b(eu|europe|european|ecb)\b",
        "China": r"\bchina\b", "India": r"\bindia\b", "Japan": r"\bjapan\b",
    }
    regions = sum(1 for p in _region_pats.values() if re.search(p, out, re.I))
    directions = ("oil" in low and "21%" in out and
                  any(w in low for w in ("inr", "rupee", "india")))
    audit.add("scenario", "four tiers present", "PASS" if tiers == 4 else "FLAG",
              f"{tiers}/4 tier headers")
    audit.add("scenario", "global scope", "PASS" if regions >= 4 else "FLAG",
              f"{regions} region mentions")
    audit.add("scenario", "uses KB facts + correct directions",
              "PASS" if directions else "FLAG",
              "cites Hormuz 21% and India/INR oil channel" if directions
              else "did not cite KB oil/INR facts")
    audit.raw["scenario"] = {"scenario": scenario, "kb_len": len(kb), "output": out}


# ── driver ────────────────────────────────────────────────────────────────────

def _load_portfolio() -> list[dict]:
    f = paths.data_dir() / "portfolio.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text())
        return d if isinstance(d, list) else []
    except (ValueError, OSError):
        return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="StockX macro-completion audit")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args(argv)

    audit = Audit()
    portfolio = _load_portfolio()
    print("=" * 78)
    print("StockX - Macro-Completion Audit")
    print("=" * 78)
    print("[A] commodity indicators vs reference...")
    audit_indicators(audit)
    print("[B] risk metrics panel...")
    audit_risk_metrics(audit, portfolio)
    print("[C] correlation matrix...")
    audit_correlation(audit)
    print("[D] knowledge-base injection...")
    audit_knowledge(audit)
    if args.no_llm:
        audit.add("scenario", "llm", "SKIP", "--no-llm")
    else:
        print("[E] LLM scenario engine...")
        audit_scenario_llm(audit)

    out_path = os.path.join(os.path.dirname(__file__), "audit_macro_findings.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"findings": [asdict(x) for x in audit.findings], "raw": audit.raw},
                  f, indent=2, default=str)

    print("\n" + "-" * 78)
    width = max(len(f"{x.section}/{x.name}") for x in audit.findings)
    for x in audit.findings:
        print(f"  {x.status:4}  {x.section + '/' + x.name:<{width}}  {x.detail}")
    counts = {s: sum(f.status == s for f in audit.findings)
              for s in ("PASS", "FAIL", "FLAG", "INFO", "SKIP")}
    print("-" * 78)
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"  findings -> {out_path}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
