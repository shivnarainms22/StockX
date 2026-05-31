# StockX — Remaining-Surface Audit (monitor, screen, portfolio, views)

**Date:** 2026-05-31
**Branch:** `audit/remaining-surface`

Closes the last unaudited areas: watchlist/commodity **monitor** alerts, the stock
**screen/report** ranking, **portfolio** returns/dividend math, and the
**heatmap/earnings/news** views. Two real bugs found and fixed.

## Bugs found & fixed

### 1. Inline non-Wilder RSI in 3 more places (was firing wrong alerts)
The Wilder-smoothing fix had only reached `services/indicators.py` and `tools/stock.py`.
A repo-wide sweep found the same SMA-smoothed inline RSI duplicated in **three** more
hot paths:
- `services/monitor.py` — **watchlist RSI alerts fired on the wrong RSI** (an "RSI ≥ 70"
  alert used a non-standard value). User-facing correctness bug.
- `gui/views/analysis.py` — the analysis quick-stats RSI column.
- `gui/views/watchlist.py` — the watchlist RSI display.

All three now call the shared Wilder `calc_rsi`. A repo-wide grep confirms **zero**
remaining inline RSI computations (6 original sites → all consolidated on one
Wilder-correct implementation).

### 2. Portfolio dividend income silently always 0
`PortfolioView` computed TTM dividends with `divs.index >= pd.Timestamp.now()`, but
yfinance's dividend index is **timezone-aware** while `Timestamp.now()` is tz-naive —
the comparison raises `TypeError`, which the surrounding `except` swallowed, zeroing
**all** dividend income. Verified the raise on a tz-aware index. Fixed by a shared
`ttm_dividend()` helper that derives a tz-matched cutoff (handles both aware and naive
indices) and is dedup'd across the two call sites.

## Verified correct (no change needed)

- **Portfolio P&L** — value = price×qty, cost = avg_cost×qty, P&L% = pnl/cost; holdings
  in different currencies are correctly kept separate (never cross-summed). Extracted to
  a pure `aggregate_by_currency()` and unit-tested.
- **Monitor alert conditions** — price ≥/≤ threshold, target within ±2%, RSI ≥/≤
  threshold, earnings 0–3 days out, commodity |Δ| ≥ threshold once/day; cooldown +
  confidence gating all sound. (Confidence helpers already had tests.)
- **Screen scorer** (`_score_one`) — momentum/quality composite, ranked by score; computes
  and orders correctly (it's a deliberately momentum-led *screen*, distinct from the
  analysis score).
- **Heatmap** — 1-day % change `(close−prev)/prev×100` from 2-day history. Correct.
- **Earnings** — robust earnings-date parsing (datetime/date/str) + `days_until` + sort
  by date. Correct.
- **News** — sentiment dots use the audited lexicon scorer; rest is display.

## New durable tests
`tests/test_portfolio_math.py` (aggregation + tz-aware/naive TTM dividend). Suite → 185.
