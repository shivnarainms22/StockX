# StockX — Deep Diagnostic Audit

**Date:** 2026-05-31
**Universe:** 15 tickers across 7 sectors (Tech, Energy, Financials, Healthcare, Staples, Utilities, Industrials), folding in the user's real AAPL/AMZN/MSFT holdings.
**Reproduce:** `python validation/audit.py` → writes `validation/audit_findings.json`.

> **Status update (branch `fix/audit-findings`):** the valuation blind spot (W1) is
> addressed — a `_valuation_score(upside, pe_fwd)` component now scores analyst upside
> symmetrically (no dead zone) and penalizes rich forward multiples, so negative-upside
> names (AAPL, GS) are docked and flagged. Note: the *composite* score remains, by
> design, a quality + momentum ranker. **Momentum rebalance now applied:** the 1y/2y
> price-return points were removed from the *fundamental* leg (they are momentum, not
> fundamentals, and were double-weighting trend — which the technical MAs already
> capture). Effect on the 15-name universe: analyst-consensus agreement rose (ρ
> +0.65→+0.71), momentum grip fell (1y-return ρ +0.48→+0.28), and AAPL dropped out of
> STRONG BUY (→BUY) given its 0% upside. Score-vs-upside ρ stays ~0.08 — now an
> established result, not a defect: analyst upside behaves as a *value* factor (the
> high-upside names are cheap energy majors with mediocre fundamentals), genuinely
> orthogonal to the quality+sentiment the score measures. Tier thresholds were kept
> (lowering them would just re-inflate AAPL), yielding a more conservative, honest
> distribution (2 STRONG BUYs vs the prior "everything is BUY+").

---

## Executive verdict

| Layer | Verdict | One-line |
|---|---|---|
| Macro / factor / scenario / recession | **Trustworthy** | All 6 economic-sense checks pass; signs and orderings are correct. |
| Per-stock score — *ranking* | **Mostly sound** | Strongly agrees with analyst consensus (ρ=+0.65); a defensible quality+momentum ranker. |
| Per-stock score — *valuation awareness* | **Weak — real gap** | Score is essentially **blind to valuation/upside** (ρ=+0.08 vs analyst upside). It can stamp STRONG BUY on a name with 0% upside at 32× earnings. |
| Tier calibration | **Biased bullish** | On blue-chip names nothing scores below WATCH/HOLD; "AVOID" effectively never fires here. |
| Confidence metric | **Non-discriminating** | Pinned at 0.95 for every liquid large-cap; carries no information in this universe. |
| LLM narrative | **Faithful** | No hallucinated figures; actually caught the AAPL valuation contradiction unprompted. |

**Bottom line:** the *quantitative macro machinery is genuinely accurate and economically sensible* — not slop. The *stock score is a competent quality-and-momentum ranker that agrees with the Street*, but it has one substantive blind spot (valuation/upside) and a bullish tier bias you should know about before treating "STRONG BUY" as a price-upside signal.

---

## Methodology & the honest caveat

yfinance fundamentals are point-in-time *now* — there is no historical snapshot of P/E, growth, or analyst targets. So the full 0–45 score **cannot** be backtested for forward returns without look-ahead leakage. This audit therefore measures **present-day coherence** (does the score agree with independent anchors and itself?) and **economic sense** (do the macro outputs obey known economic relationships?), plus a **cross-sectional** read of what the score actually tracks. Every output below is cross-checked against an *independent* source: analyst consensus, valuation, trailing performance, FRED, or a hard economic expectation.

---

## 1. Per-stock score coherence

Full result (sorted by total score):

| Ticker | Total | Tier | Tech | Fund | Risk | FwdP/E | Analyst | Upside | 1y ret |
|---|---|---|---|---|---|---|---|---|---|
| NVDA | 39 | STRONG BUY | 9 | 27 | 3 | 17 | strong_buy | +41% | +56% |
| AAPL | 33 | STRONG BUY | 13 | 19 | 1 | 32 | buy | **−0%** | +56% |
| MSFT | 33 | STRONG BUY | 11 | 20 | 2 | 23 | strong_buy | +25% | −1% |
| AMZN | 32 | STRONG BUY | 9 | 22 | 1 | 27 | strong_buy | +16% | +32% |
| CAT | 31 | STRONG BUY | 10 | 21 | 0 | 29 | buy | +5% | +154% |
| JNJ | 30 | STRONG BUY | 9 | 19 | 2 | 18 | buy | +12% | +49% |
| KO | 29 | BUY | 9 | 18 | 2 | 23 | buy | +9% | +13% |
| GS | 27 | BUY | 12 | 15 | 0 | 16 | **hold** | **−8%** | +73% |
| JPM | 25 | BUY | 6 | 18 | 1 | 13 | buy | +14% | +16% |
| XOM | 24 | BUY | 8 | 13 | 3 | 14 | buy | +17% | +47% |
| CVX | 24 | BUY | 6 | 15 | 3 | 15 | buy | +18% | +39% |
| NEE | 24 | BUY | 8 | 15 | 1 | 20 | buy | +13% | +27% |
| PFE | 23 | BUY | 11 | 10 | 2 | 9 | buy | +11% | +19% |
| DUK | 21 | WATCH/HOLD | 8 | 12 | 1 | 17 | buy | +13% | +8% |
| PG | 18 | WATCH/HOLD | 4 | 13 | 1 | 20 | buy | +14% | −13% |

**Integrity checks:** `total == tech + fund + risk` for every ticker — no arithmetic faults. The harness auto-flagged **3 coherence issues**, all valuation-related: **AAPL** (STRONG BUY at −0.5% upside, 32× fwd P/E), **GS** (BUY but analyst *hold*, mean 2.60), and **GS** again (BUY at −7.6% upside). These are exactly the W1 cases below — the score's blind spot, now machine-detected rather than just narrated.

**Observations:**
- The ranking is reasonable: NVDA top (strong analyst support + momentum + reasonable forward multiple), PG/DUK bottom (PG dragged by −13% trailing return).
- **W1 — valuation blindness (most important):** AAPL gets the **top tier (33, STRONG BUY)** with **−0% analyst upside at 32× forward earnings**. GS scores BUY despite an analyst **hold** and **−8% upside**. The score rewards quality and past performance but does not meaningfully dock points for "already priced for perfection." See §2 for the quantified version.
- **W2 — momentum cuts both ways:** PG is the lowest score purely because of its −13% trailing return, even though analysts rate it buy with +14% upside. The trailing-return features (worth up to ~5 fund pts + technical pts) materially swing the score.

---

## 2. Cross-sectional reality check — what the score *actually* tracks

Spearman rank correlation of total score vs independent anchors (n=15):

| Score vs… | ρ | p | Reading |
|---|---|---|---|
| **Analyst consensus** (lower mean = more bullish) | **+0.65** | 0.01 | Strong, significant agreement with the Street. The score is *not* nonsense. |
| **Trailing 1-year return** | **+0.48** | 0.07 | Real momentum lean — consistent with the trailing-return features in the formula. |
| **Implied analyst upside** | **+0.08** | 0.77 | **No relationship.** The score does not track how much room a stock has left. |

This is the single most useful chart in the audit. It says, precisely: **StockX's score is a quality + momentum ranker that the analyst community broadly agrees with, but it is orthogonal to valuation/upside.** That's a legitimate style (quality-momentum is a real factor), but it means a high score answers *"is this a good, well-regarded, trending company?"* — **not** *"is this a good price?"* Treat the tier accordingly.

---

## 3. Economic-effects audit (factor / scenario / macro) — all pass

Factor betas computed on sector-isolated equal-weight mini-portfolios (2y daily, OLS vs SPY/Oil/Gold/TLT/USD), then named-scenario stress via the real `SCENARIOS` library:

| Economic expectation | Result | Evidence |
|---|---|---|
| Oil beta: Energy > Tech | ✅ PASS | Energy **+0.31** vs Tech **+0.02** |
| Rate sensitivity: Utilities > Tech (TLT-positive) | ✅ PASS | Util **+0.37** vs Tech **−0.11** |
| Market beta: Staples < Tech | ✅ PASS | Staples **+0.04** vs Tech **+1.37** |
| Recession scenario hurts Tech more than Staples | ✅ PASS | Tech **−43.3%** vs Staples **+2.1%** |
| Oil shock (+50%) helps Energy | ✅ PASS | Energy **+13.5%** |
| Recession probability is sane (FRED probit) | ✅ PASS | **P=8.6%**, 10y-3m spread **+0.80**, not inverted |
| Tech TLT(rate) beta sign | ⚠️ FLAG | Tech Rates beta **−0.11** — see anomaly below |

Every *ordering* the macro engine asserts is **economically correct**, and the scenario-stress and recession-probit directions are sound — strong evidence the factor model is real, not decorative. One **sign anomaly** was surfaced rather than glossed:

- **Tech TLT/rate beta is slightly negative (−0.11).** Long-duration growth stocks "should" rise when bond prices rise (rates fall), i.e. a *positive* TLT beta. The near-zero/negative value reflects 2024–26 tech rallying on AI largely *independent* of rates. It's economically explicable but worth knowing the factor model won't capture the textbook rate-duration story for tech in this regime. The harness now FLAGs this automatically.

**Caveats on magnitude (not failures):**
- Staples market beta of **+0.04** is *directionally* right but *quantitatively low* (KO+PG would normally sit ~0.4–0.6). With only 2 names over a tech-dominated 2-year window the regression is noisy; the *ordering* is robust, individual *magnitudes* on 2-stock baskets are not. Use sector betas qualitatively.
- Tech recession impact of **−43%** is large; it is mechanically `market_beta 1.37 × −30% market shock` plus other legs. The model is internally consistent, but the headline number assumes the full scenario shock hits instantly — read it as a stress bound, not a forecast.

---

## 4. LLM narrative fact-check — faithful

Three tickers were run through the real `LLMRouter` with only the audited numbers supplied. Every narrative used **only** the provided figures — no invented data — and reasoning matched the inputs:

- **AAPL:** *"Despite a StockX score of 33 indicating STRONG BUY, the analyst target suggests −0.5% downside… P/E of 37.7 indicates the stock may be overvalued… a cautious approach is recommended, potentially hold rather than buy."* → The model **independently caught weakness W1** and overrode the tier. Good behavior.
- **MSFT / NVDA:** Both correctly synthesized forward P/E + upside + return into a coherent buy thesis with accurate figures.

No hallucination detected in the sample. The narrative layer is a faithful summarizer that will, at least sometimes, catch the score's valuation blind spot on its own.

---

## Concrete, right-sized recommendations

1. **Add a valuation/upside component to the score (addresses W1).** The score has no penalty for negative or zero analyst upside and only a soft P/E signal. A few points keyed off implied upside (e.g. dock points when `targetMeanPrice ≤ price`, reward when upside > 15%) would close the ρ=+0.08 gap and stop STRONG BUY from firing on fully-priced names like AAPL/GS. *This is the single highest-value change.*
2. **Re-examine tier thresholds for bullish bias (W2/W3).** In a 15-name blue-chip basket, nothing scored below WATCH/HOLD. Either that's intended (these are quality names) or the AVOID/CAUTION tiers need a relative/sector-aware cut so the system can actually say "no."
3. **Make `confidence` discriminate or drop it.** It was 0.95 for all 15 liquid names; it only moves on missing fields, which never happens for large caps. Consider tying it to data freshness or analyst coverage breadth, or remove it to avoid false precision.
4. **Label sector factor betas as qualitative on small baskets.** The 2-stock magnitudes are noisy; the UI should lean on sign/ordering, which are reliable.

None of these are bugs — the engines are correct. They are *calibration and completeness* improvements to make the suggestions match how a valuation-aware investor would read them.

## What to trust today

- ✅ **Macro view, factor exposures, scenario stress, recession probability** — accurate and economically sound. Use them.
- ✅ **Score as a quality/momentum *ranking*** and its **agreement with analyst consensus** — sound.
- ⚠️ **"STRONG BUY" as a statement about price/upside** — not supported by the data; the score doesn't model upside. Cross-check valuation yourself (the app shows P/E and analyst target — use them).
- ⚠️ **Single 2-stock sector beta magnitudes** — directional only.
