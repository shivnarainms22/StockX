# StockX — ReAct Agent + Sentiment Audit

**Date:** 2026-05-31
**Reproduce:** `python validation/audit_agent.py` (spends tokens); `pytest tests/test_sentiment.py`.

Closes two of the previously-unaudited gaps: the **real ReAct agent** (the app's
actual analysis/scenario path, not the single-shot LLM proxy used in earlier audits)
and the **news sentiment scorer**.

## ReAct agent — faithful, with a minor robustness nit

Ran the real `AgentCore` (stock + search tools) on a stock task and a scenario task.

- **Tool use:** the agent correctly issues `Action: stock` and consumes the tool output. ✅
- **Faithfulness (the key risk):** the stock final answer relayed the tool's numbers
  **exactly** — rating STRONG BUY, scores 9/22/+3/total 34 (matching the SCORE_CARD),
  price $211.14, P/E 32.38/16.68, analyst target $296.81 (+40.6%), RSI 49.4 (the
  Wilder-fixed value). **No hallucinated figures.** ✅
- **Recommendation aligns** with the tool's rating (no contradiction). ✅
- **Termination:** ends with a Final Answer; no runaway loop. ✅
- **Scenario task:** produced all 4 tiers with the correct primary direction (oil up). ✅

**Findings:**
- ⚠️ **Tool-name hallucination (minor):** mid-loop the agent invented non-existent tools
  (`fetch`, `summarise`). It recovered gracefully — the "tool not found" observation is
  fed back and it self-corrects — but this wastes ReAct steps. *Suggested:* list the
  available tool names explicitly in the system prompt / nudge on unknown-tool errors.
- ℹ️ **Grounding matters:** run bare (no knowledge-base injection), the agent cited the
  Strait of Hormuz at **27%** of global oil vs the KB's grounded **21%**. In the real
  macro path the KB is injected (earlier audit confirmed it then cites 21%) — this is
  evidence *for* keeping the KB injection, not an app defect.

## Sentiment scorer — correct on clear cases, one known gap

`services/sentiment.score_headline` (lexicon, 0–1). Pinned by `tests/test_sentiment.py`:
clearly-bullish headlines score >0.6, clearly-bearish <0.4, neutral ≈0.5, mixed lands
between. ✅

- ⚠️ **No negation handling (documented):** "shares do **not** surge" still reads the
  positive token. Acceptable for a lightweight lexicon; flagged so it's explicit.

## Still unaudited (offered, not yet done)
Stock `screen`/`report` ranking accuracy, watchlist/monitor alert firing, portfolio
returns/benchmark/dividend math, and the news/earnings/heatmap view rendering.
