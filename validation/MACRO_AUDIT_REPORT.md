# StockX — Macro-Completion Audit

**Date:** 2026-05-31
**Scope:** the Macro-view pieces the first audit left unverified — commodity
technical indicators, the Risk Metrics panel, the correlation matrix, the
knowledge base (facts + injection), and the LLM geopolitical scenario engine.
**Reproduce:** `python validation/audit_macro.py` (+ `pytest tests/validation/`).

---

## Executive verdict

| Component | Verdict | One-line |
|---|---|---|
| **Commodity indicators — RSI / ADX** | **⚠️ Real issue** | Non-Wilder smoothing makes values differ enough to **flip signals**; shared module, so it also affects the stock score. |
| Commodity indicators — MACD / Bollinger / Stochastic / EMA / SMA | ✅ Correct | Match the reference exactly (MACD) or within ddof (Bollinger). |
| Risk Metrics — VaR, max drawdown | ✅ Correct | Historical VaR and drawdown math verified. |
| Risk Metrics — commodity betas | ⚠️ Minor | Mixed ddof (`cov` ddof=1 / `var` ddof=0) → ~1–2% high. |
| Correlation matrix | ✅ Correct | Diagonal=1, symmetric, in [−1,1]. |
| Knowledge base — facts | ✅ Accurate | Headline numbers fact-check out (see below). |
| Knowledge base — injection | ⚠️ Minor | Keyword-literal; a chokepoint doesn't chain to its own commodities. |
| **LLM scenario engine** | ✅ **Strong** | Precisely grounded in the KB, no hallucination, coherent 4-tier global cascade. |

**Bottom line:** the macro *reasoning* layer (scenario engine + knowledge base) is genuinely good — accurate facts, faithful LLM grounding, no slop. The one substantive defect is in the **commodity technical indicators**: RSI and especially ADX use non-standard smoothing and produce values that disagree with every charting platform, sometimes enough to flip the buy/sell signal — and because `services/indicators.py` is shared, this reaches the stock score too.

---

## 1. Commodity technical indicators — the main finding

StockX computes RSI, ATR, and ADX with `ewm(span=period)` / simple `rolling().mean()`
smoothing instead of **Wilder's smoothing** (`alpha = 1/period`), which is the
definition every charting platform (TradingView, StockCharts) and textbook uses.
Measured live against the `ta` reference library:

| Commodity | RSI StockX | RSI Wilder | ADX StockX | ADX Wilder |
|---|---|---|---|---|
| WTI Crude (CL=F) | **26.1** (oversold) | 37.9 (neutral) | **33.9** (strong trend) | 18.0 (no trend) |
| Gold (GC=F) | 55.7 | 49.1 | **35.9** (strong trend) | 22.3 (no trend) |
| Nat Gas (NG=F) | **75.3** (overbought) | 68.1 (neutral) | 42.4 | 26.5 |
| Copper (HG=F) | 58.6 | 58.6 | 15.5 | 12.4 |

- **RSI** deviates by up to ~12 points and **flipped the overbought/oversold call on 2 of 4** commodities (CL=F oversold, NG=F overbought — neither true under standard RSI).
- **ADX** is **systematically ~1.5–2× overstated** and **flipped the trend/no-trend call on 2 of 4** (CL=F and GC=F read "strong trend" at >25 when canonical ADX says no trend). This is the worst offender.
- **MACD matched exactly** on all four (it is EMA-based by definition — StockX is correct). Bollinger/Stochastic/EMA/SMA also match the reference.

**Why it matters:** the commodity detail panel and the signal engine color-code these
against standard thresholds (RSI 70/30, ADX 25). With miscalibrated inputs, the
"overbought / oversold / strong-trend" labels can be wrong. And `indicators.py` is
explicitly *"used by both tools/stock.py and gui/views/macro.py"* — so the RSI used in
the stock score's momentum checks inherits the same deviation.

**Recommended fix (well-scoped):** switch RSI, ATR, and ADX to Wilder smoothing —
`ewm(alpha=1/period, adjust=False)` (equivalently `com=period-1`) and Wilder-smoothed
ATR. MACD/Bollinger/Stochastic stay as-is. Small change in `services/indicators.py`,
covered by `tests/validation/test_indicators_vs_reference.py` (which currently pins the
*correct* indicators and only range-checks the deviating ones, precisely so this fix
won't be blocked).

---

## 2. Risk Metrics panel

`_compute_risk_metrics` (computed inline in `gui/views/macro.py`) verified against an
independent recomputation on identical data (hermetic test mocks only the yfinance call):

- **VaR 95% / 99%** — correct historical VaR (5th / 1st percentile of daily returns). Live: −2.38% / −3.29%, correctly ordered. ✅
- **Max drawdown** — correct (cumprod / running-peak). Live: −12.0% (90d). ✅
- **Commodity betas** — formula is `np.cov(port, c)[0,1] / np.var(c)`, which mixes
  `cov` ddof=1 with `var` ddof=0, so every commodity beta is biased high by exactly
  `n/(n-1)` (~1.6% on a 90-day window). Directionally fine, slightly overstated. ⚠️
  *Fix:* `np.var(c, ddof=1)` for a consistent estimator.
- **Stress tests** — `beta × move%` first-order linear; reasonable. ✅

---

## 3. Correlation matrix

`_compute_correlation_matrix` (16 commodities, 90-day): diagonal = 1, symmetric, all
values in [−1, 1] (live min −0.53, max 1.00). Mathematically sound. ✅

---

## 4. Knowledge base

### Factual accuracy — checked, holds up
Spot-checked the headline numbers the engine injects against reality:
- **Chokepoints:** Hormuz ~21% of global oil, Suez ~9% / 5.5 Mbpd, Bab-el-Mandeb Houthi
  reroute +150% freight, Malacca ~25% — all accurate. Panama 2023–24 drought −36%
  transits ✓. Turkish Straits 2022 grain blockade wheat +60% ✓.
- **Demand-destruction thresholds:** oil $120 / 2008 $147 ✓; nat gas $8 ✓; wheat $12 /
  2022 $13.60 ✓; corn $8 / 2012 $8.40 ✓; copper $5.50 / 2024 ~$5.20 ✓; cotton $1.20 /
  2011 $2.20 ✓.
- **Input-output shares:** crude ≈55% of gasoline ✓, jet fuel 25–35% of airline opex ✓,
  nat gas ~80% of nitrogen-fertilizer cost ✓, 40% of US corn → ethanol ✓.
- **Import dependence:** India 85% oil ✓, China 72% oil / 50% copper / 60% soy ✓,
  Egypt largest wheat importer ✓.
- **Crisis parallels:** 1973 (+300% oil, −48% S&P) ✓, 2008 ($147→−77%) ✓, 2020 (negative
  WTI) ✓, 2022 (wheat +60%, EU TTF +140%) ✓.

The curated data is genuinely expert-grade. One **minor internal inconsistency:** Hormuz
is listed as `21% of global oil` but `17.0 Mbpd` — at ~100 Mbpd global, 21% ≈ 21 Mbpd, so
the two fields disagree slightly (EIA's figure is ~21 Mbpd). Cosmetic.

### Injection logic — works, with one gap
`build_knowledge_context` correctly assembles chokepoint / pass-through / crisis / EM /
currency / seasonal / demand-destruction blocks for matched scenarios (verified for
Hormuz, Russia-Ukraine wheat, Houthi Red Sea). **Limitation:** matching is purely
keyword-literal, so *"Iran closes the Strait of Hormuz"* (no word "oil") injects the
chokepoint block but **not** the oil pass-through / EM-vulnerability data — the
chokepoint's own `primary_commodities` are not chained in. The LLM still infers oil, but
the precise injected grounding is thinner than it could be. *Suggested fix:* when a
chokepoint matches, also pull in its `primary_commodities`' pass-through/EM blocks.

---

## 5. LLM geopolitical scenario engine — strong

Ran the real scenario *"Iran closes the Strait of Hormuz; oil spikes 20%"* through the
actual `LLMRouter` with the real KB-injected prompt. The output:

- **All 4 tiers present** (Primary / Secondary / Tertiary / Consumer). ✅
- **Used the injected KB facts precisely and correctly** — cited the 21% Hormuz share,
  the $0.25/gallon + 0.3% CPI pass-through, airlines' 65% fuel cost share, India's 85%
  import dependence and ~$15B import-bill increase, Japan ~100% dependence, and the $120
  demand-destruction threshold. **No invented figures.** ✅
- **Economic directions all correct** (oil ↑, INR/yen pressure, airlines hit, recession
  risk above the threshold). ✅
- **Global coverage** — US, EU, India, Japan addressed (harness counts 4 regions via
  word-boundary matching). ✅

The grounding mechanism does exactly its job: by injecting verified numbers, it keeps the
LLM factual. This is the opposite of slop.

---

## Recommended fixes, ranked
1. **Wilder-smooth RSI / ATR / ADX** in `services/indicators.py` (fixes commodity panel
   *and* the stock score's RSI). Highest value — it currently mislabels signals.
2. **Consistent ddof** in the commodity-beta calc (`np.var(..., ddof=1)`).
3. **Chain chokepoint → its commodities** in `build_knowledge_context` for richer
   grounding when the user names only the chokepoint.
4. Reconcile the Hormuz `17.0 Mbpd` vs `21%` fields (cosmetic).

## What to trust today
- ✅ **LLM scenario analysis, knowledge-base facts, correlation matrix, VaR/drawdown** — sound.
- ⚠️ **Commodity RSI/ADX "overbought / oversold / strong-trend" labels** — can be wrong vs standard definitions; treat as directional until Wilder-smoothed.
- ⚠️ **Commodity betas** — directionally right, ~1–2% overstated.
