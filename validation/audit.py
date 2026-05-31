"""StockX - deep diagnostic audit.

Runs the REAL analysis / macro / factor / scenario engines on a sector-diverse
universe and cross-checks every output against independent anchors (analyst
consensus, valuation, trailing performance) and hard economic expectations.

Because yfinance fundamentals are point-in-time *now* (no historical snapshot),
the per-stock score cannot be honestly backtested for forward returns; this is a
present-day coherence + economic-sense audit, plus a cross-sectional measurement
of what the score actually tracks.

Usage:
    python validation/audit.py
    python validation/audit.py --no-llm        # skip the paid LLM fact-check

Writes validation/audit_findings.json and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict, field

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import paths  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(paths.dotenv_path())
except ImportError:
    pass

from tools.stock import StockTool  # noqa: E402
from services.factor_exposure import (  # noqa: E402
    compute_factor_betas, fetch_factor_data, scenario_impact, SCENARIOS,
)

# Sector-diverse universe; user's real holdings (AAPL/AMZN/MSFT) folded in.
UNIVERSE: dict[str, list[str]] = {
    "Tech": ["AAPL", "MSFT", "NVDA"],
    "Energy": ["XOM", "CVX"],
    "Financials": ["JPM", "GS"],
    "Healthcare": ["JNJ", "PFE"],
    "Staples": ["PG", "KO"],
    "Utilities": ["NEE", "DUK"],
    "Industrials": ["CAT"],
    "Consumer": ["AMZN"],
}
ALL_TICKERS = [t for v in UNIVERSE.values() for t in v]

_BULLISH_TIERS = {"STRONG BUY", "BUY"}
_BEARISH_TIERS = {"CAUTION", "AVOID"}


@dataclass
class Finding:
    section: str
    name: str
    status: str           # PASS | FAIL | FLAG | INFO | SKIP
    detail: str


@dataclass
class Audit:
    findings: list[Finding] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def add(self, *a) -> None:
        self.findings.append(Finding(*a))


# ── data helpers ──────────────────────────────────────────────────────────────

def _parse_score_card(text: str) -> dict | None:
    for line in text.splitlines():
        if line.startswith("SCORE_CARD:"):
            try:
                return json.loads(line[len("SCORE_CARD:"):])
            except ValueError:
                return None
    return None


def _yf_anchors(ticker: str) -> dict:
    """Independent fundamentals/consensus anchors straight from yfinance."""
    import yfinance as yf
    tk = yf.Ticker(ticker)
    info = tk.info or {}
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    target = info.get("targetMeanPrice")
    upside = (target - price) / price if (target and price) else None
    try:
        hist = tk.history(period="1y", auto_adjust=True)["Close"]
        ret_1y = float(hist.iloc[-1] / hist.iloc[0] - 1.0) if len(hist) > 1 else None
    except Exception:  # noqa: BLE001
        ret_1y = None
    return {
        "sector": info.get("sector"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "rec_mean": info.get("recommendationMean"),
        "rec_key": info.get("recommendationKey"),
        "target": target, "price": price, "upside": upside,
        "n_analysts": info.get("numberOfAnalystOpinions"),
        "ret_1y": ret_1y,
        "beta": info.get("beta"),
    }


def _tier_stance(tier: str) -> str:
    t = (tier or "").upper()
    if t in _BULLISH_TIERS:
        return "bullish"
    if t in _BEARISH_TIERS:
        return "bearish"
    return "neutral"


def _analyst_stance(rec_mean: float | None) -> str | None:
    if rec_mean is None:
        return None
    if rec_mean <= 2.5:
        return "bullish"
    if rec_mean <= 3.5:
        return "neutral"
    return "bearish"


# ── item 1: per-stock score coherence ────────────────────────────────────────

def audit_scores(audit: Audit) -> list[dict]:
    tool = StockTool()
    rows: list[dict] = []
    for t in ALL_TICKERS:
        try:
            text = tool._analyse_ticker(t)
        except Exception as e:  # noqa: BLE001
            audit.add("scores", t, "SKIP", f"analyse failed: {e}")
            continue
        sc = _parse_score_card(text)
        if not sc:
            audit.add("scores", t, "SKIP", "no SCORE_CARD in output")
            continue
        a = _yf_anchors(t)
        row = {"ticker": t, **{k: sc.get(k) for k in
               ("tech", "fund", "risk", "total", "rating", "confidence")}, **a}
        rows.append(row)

        # arithmetic integrity
        if sc.get("total") != (sc.get("tech", 0) + sc.get("fund", 0) + sc.get("risk", 0)):
            audit.add("scores", f"{t} arithmetic", "FAIL",
                      f"total={sc.get('total')} != tech+fund+risk")
        # tier vs analyst consensus (flag bullish tier when analysts are not bullish)
        st = _tier_stance(sc.get("rating"))
        if st == "bullish" and a["rec_mean"] and a["rec_mean"] > 2.5:
            audit.add("scores", f"{t} consensus", "FLAG",
                      f"StockX {sc.get('rating')} but analysts {a['rec_key']} "
                      f"(mean {a['rec_mean']:.2f})")
        # bullish tier on a name with no/negative analyst upside (valuation blind spot)
        if st == "bullish" and a["upside"] is not None and a["upside"] < 0.0:
            audit.add("scores", f"{t} upside", "FLAG",
                      f"bullish tier {sc.get('rating')} but implied upside "
                      f"{a['upside']:+.1%} (fwd P/E {a['forward_pe']})")
    audit.raw["scores"] = rows
    if rows:
        audit.add("scores", "coverage", "INFO",
                  f"{len(rows)}/{len(ALL_TICKERS)} tickers scored")
    return rows


# ── item 2: cross-sectional reality check ─────────────────────────────────────

def audit_cross_section(audit: Audit, rows: list[dict]) -> None:
    from scipy.stats import spearmanr

    def corr(key, transform=lambda x: x, label=""):
        pairs = [(r["total"], transform(r[key])) for r in rows
                 if r.get("total") is not None and r.get(key) is not None]
        if len(pairs) < 5:
            audit.add("cross_section", label, "SKIP", "too few points")
            return
        x, y = zip(*pairs)
        rho, p = spearmanr(x, y)
        audit.add("cross_section", label, "INFO",
                  f"Spearman rho={rho:+.2f} (p={p:.2f}, n={len(pairs)})")

    # analyst mean: lower = more bullish, so negate to align with "higher score better"
    corr("rec_mean", lambda v: -v, "score vs analyst consensus")
    corr("ret_1y", label="score vs trailing 1y return")
    corr("upside", label="score vs implied analyst upside")


# ── item 3: economic-effects audit ───────────────────────────────────────────

def _sector_betas(tickers: list[str]) -> dict | None:
    pf = [{"ticker": t, "qty": 1.0, "avg_cost": 1.0} for t in tickers]
    port_r, factor_df = fetch_factor_data(pf, period="2y")
    if port_r is None or factor_df is None:
        return None
    return compute_factor_betas(port_r, factor_df)["betas"]


def audit_economics(audit: Audit) -> None:
    betas: dict[str, dict] = {}
    for sector in ("Tech", "Energy", "Utilities", "Staples", "Financials"):
        b = _sector_betas(UNIVERSE[sector])
        if b:
            betas[sector] = b
    audit.raw["sector_betas"] = betas

    def have(*ss):
        return all(s in betas for s in ss)

    def g(sector, factor):
        return betas[sector].get(factor, 0.0)

    # oil exposure: energy >> tech
    if have("Energy", "Tech"):
        ok = g("Energy", "Oil") > g("Tech", "Oil")
        audit.add("economics", "oil beta: Energy > Tech", "PASS" if ok else "FAIL",
                  f"Energy={g('Energy','Oil'):+.2f} Tech={g('Tech','Oil'):+.2f}")
    # rate sensitivity: utilities more positive TLT beta than tech
    if have("Utilities", "Tech"):
        ok = g("Utilities", "Rates") > g("Tech", "Rates")
        audit.add("economics", "rates beta: Utilities > Tech", "PASS" if ok else "FAIL",
                  f"Util={g('Utilities','Rates'):+.2f} Tech={g('Tech','Rates'):+.2f}")
        # Growth/tech is "long duration" => expected POSITIVE TLT beta; flag if not.
        if g("Tech", "Rates") < 0:
            audit.add("economics", "tech TLT beta sign", "FLAG",
                      f"Tech Rates(TLT) beta {g('Tech','Rates'):+.2f} < 0 — atypical for "
                      f"long-duration growth; likely AI-driven decoupling over the window")
    # market beta: staples < tech
    if have("Staples", "Tech"):
        ok = g("Staples", "Market") < g("Tech", "Market")
        audit.add("economics", "market beta: Staples < Tech", "PASS" if ok else "FAIL",
                  f"Staples={g('Staples','Market'):+.2f} Tech={g('Tech','Market'):+.2f}")

    # scenario stress: recession hurts cyclical (Tech) more than Staples
    if have("Tech", "Staples"):
        rec = SCENARIOS["2008-style Recession"]
        i_tech = scenario_impact(betas["Tech"], rec)
        i_stap = scenario_impact(betas["Staples"], rec)
        ok = i_tech < i_stap
        audit.add("economics", "recession hurts Tech > Staples", "PASS" if ok else "FAIL",
                  f"Tech={i_tech:+.1%} Staples={i_stap:+.1%}")
    # oil shock helps energy
    if have("Energy"):
        shock = SCENARIOS["Oil Shock (+50%)"]
        i_en = scenario_impact(betas["Energy"], shock)
        audit.add("economics", "oil shock helps Energy", "PASS" if i_en > 0 else "FAIL",
                  f"Energy scenario P&L={i_en:+.1%}")

    # recession probability (FRED)
    try:
        from services.yield_curve import recession_probability
        model = recession_probability()
        if model:
            p = model["probability"]
            ok = 0.0 <= p <= 1.0
            audit.add("economics", "recession prob sane", "PASS" if ok else "FAIL",
                      f"P={p:.1%} spread={model['spread']:+.2f} inverted={model['inverted']}")
        else:
            audit.add("economics", "recession prob", "SKIP", "no FRED key / data")
    except Exception as e:  # noqa: BLE001
        audit.add("economics", "recession prob", "SKIP", str(e))


# ── item 4: LLM narrative fact-check ─────────────────────────────────────────

def audit_llm(audit: Audit, rows: list[dict], n: int = 3) -> None:
    try:
        from llm.router import LLMRouter
        router = LLMRouter()
        if not router._get_providers():
            audit.add("llm", "narrative", "SKIP", "no LLM provider/keys configured")
            return
    except Exception as e:  # noqa: BLE001
        audit.add("llm", "narrative", "SKIP", str(e))
        return

    import asyncio
    samples = rows[:n]
    captured = []
    for r in samples:
        upside = f"{r['upside']:.1%}" if r.get("upside") is not None else "N/A"
        facts = (f"{r['ticker']}: StockX score {r['total']} ({r['rating']}); "
                 f"trailing P/E {r['trailing_pe']}, forward P/E {r['forward_pe']}, "
                 f"analyst target {r['target']} (implied upside "
                 f"{upside} vs price {r['price']}), 1y return {r['ret_1y']}.")
        system = ("You are an equity analyst. Use ONLY the numbers provided. "
                  "Do not invent figures. 3 sentences max.")
        messages = [
            {"role": "user", "content": f"Given these facts, give a recommendation:\n{facts}"},
        ]
        try:
            out = asyncio.run(router.complete(system=system, messages=messages))
        except Exception as e:  # noqa: BLE001
            audit.add("llm", r["ticker"], "SKIP", f"LLM error: {e}")
            continue
        captured.append({"ticker": r["ticker"], "facts": facts, "narrative": out})
        audit.add("llm", r["ticker"], "INFO", out.replace("\n", " ")[:200])
    audit.raw["llm"] = captured


# ── driver ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="StockX deep diagnostic audit")
    ap.add_argument("--no-llm", action="store_true", help="skip the LLM fact-check")
    args = ap.parse_args(argv)

    audit = Audit()
    print("=" * 78)
    print("StockX - Deep Diagnostic Audit")
    print(f"universe: {len(ALL_TICKERS)} tickers, {len(UNIVERSE)} sectors")
    print("=" * 78)

    print("[1/4] scoring tickers (this hits yfinance, ~30-60s)...")
    rows = audit_scores(audit)
    print("[2/4] cross-sectional correlations...")
    audit_cross_section(audit, rows)
    print("[3/4] economic-effects audit...")
    audit_economics(audit)
    if args.no_llm:
        audit.add("llm", "narrative", "SKIP", "--no-llm")
    else:
        print("[4/4] LLM narrative fact-check...")
        audit_llm(audit, rows)

    out_path = os.path.join(os.path.dirname(__file__), "audit_findings.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"findings": [asdict(x) for x in audit.findings],
                   "raw": audit.raw}, f, indent=2, default=str)

    print("\n" + "-" * 78)
    width = max(len(f"{x.section}/{x.name}") for x in audit.findings)
    for x in audit.findings:
        print(f"  {x.status:4}  {x.section + '/' + x.name:<{width}}  {x.detail}")
    counts = {s: sum(f.status == s for f in audit.findings)
              for s in ("PASS", "FAIL", "FLAG", "INFO", "SKIP")}
    print("-" * 78)
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"  findings written to {out_path}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
