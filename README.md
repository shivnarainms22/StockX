# StockX

A local AI agent for Windows with a fintech-style dark GUI. Performs stock analysis, portfolio tracking, watchlist monitoring, global commodity monitoring with geopolitical scenario analysis, and web search — all driven by a ReAct reasoning loop backed by a multi-provider LLM fallover chain.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)

## Features

- **AI Stock Analysis** — full-spectrum technical, fundamental, and macro analysis with scored recommendations (STRONG BUY → AVOID), confidence indicators, and data freshness metadata
- **Sector Screening** — scan 30+ sectors for top-ranked candidates
- **Portfolio Tracker** — holdings, P&L, dividends, benchmark comparison charts
- **Watchlist** — price/RSI alerts, sparklines, buy/sell targets, drag-to-reorder, per-ticker alert cooldowns and confidence thresholds
- **Global Macro** — 16-commodity dashboard across energy, metals, and agriculture with sparklines, technical indicators, and contextual signal coloring
- **Geopolitical Scenario Analysis** — type a scenario (e.g., "Iran closes Strait of Hormuz") and get AI-driven multi-tier global impact analysis enriched with curated economic knowledge, FRED/EIA data, and crisis parallels
- **Consumer Inflation Engine** — commodity-to-consumer pass-through model covering 14 mappings with sensitivity-weighted thresholds
- **Risk Metrics** — VaR (95%/99%), max drawdown, commodity betas, stress tests, and 90-day rolling correlation matrix
- **Backtesting** — vectorized, lookahead-safe engine for technical strategies (SMA/EMA/MACD crossover, RSI & Bollinger reversion) with an equity-curve-vs-buy-and-hold chart and a full metrics tearsheet (Sharpe, Sortino, CAGR, max drawdown, win rate)
- **Portfolio Optimization** — Markowitz mean-variance (scipy) efficient frontier with max-Sharpe and min-variance portfolios and a current → suggested rebalancing table
- **Yield Curve & Recession Risk** — US Treasury yield curve with inversion detection and a NY-Fed-style recession-probability model (probit fit on live FRED data)
- **Factor Exposure & Scenario Stress** — multivariate regression of your portfolio against macro factors (market, oil, gold, rates, USD) with named multi-factor stress scenarios (recession, oil shock, rate hike, risk-off, soft landing)
- **Earnings Calendar** — upcoming earnings dates in a grid view
- **Sector Heatmap** — 18 sector ETFs with colour-coded daily performance
- **Financial News** — aggregated headlines with sentiment scoring
- **Multi-Provider LLM** — automatic fallover: NVIDIA NIM → Anthropic Claude → OpenAI GPT
- **Memory** — ChromaDB vector store with JSONL fallback for conversation context
- **Desktop Alerts** — toast notifications for price targets, earnings proximity, and commodity moves with confidence scoring and precision tracking
- **Resilient Persistence** — atomic JSON writes with backup recovery, schema versioning, and data migration

## Installation

### Prerequisites

- Python 3.11 or higher
- At least one LLM API key (NVIDIA NIM, Anthropic, or OpenAI)

### Setup

```bash
# Clone the repository
git clone https://github.com/shivnarainms22/StockX.git
cd StockX

# Install dependencies (using uv — recommended)
uv sync

# Or with pip
pip install -e .

# Copy the example env and add your API keys
cp .env.example .env
# Edit .env with your API keys
```

### API Keys

StockX needs at least one LLM provider key to function. It tries them in this order:

| Provider | Key Variable | Notes |
|----------|-------------|-------|
| NVIDIA NIM | `NVIDIA_API_KEY` | Tried first |
| Anthropic | `ANTHROPIC_API_KEY` | Claude Sonnet |
| OpenAI | `OPENAI_API_KEY` | GPT-4o-mini |

Optional keys for enhanced functionality:

| Provider | Key Variable | Notes |
|----------|-------------|-------|
| Brave / Tavily | `SEARCH_API_KEY` | Set `SEARCH_PROVIDER=brave` or `tavily`. Falls back to DuckDuckGo if not set |
| FRED | `FRED_API_KEY` | Free — [fred.stlouisfed.org](https://fred.stlouisfed.org). Macro indicators (unemployment, fed rate, yield spread, etc.) |
| EIA | `EIA_API_KEY` | Free — [eia.gov](https://www.eia.gov). Petroleum inventory and production data |

## Usage

```bash
python run_gui.py
```

Navigate between views with the top nav bar or keyboard shortcuts `Ctrl+1` through `Ctrl+9`:

| Shortcut | View |
|----------|------|
| Ctrl+1 | Analysis |
| Ctrl+2 | Watchlist |
| Ctrl+3 | Portfolio |
| Ctrl+4 | News |
| Ctrl+5 | Earnings |
| Ctrl+6 | Markets (Heatmap) |
| Ctrl+7 | Macro |
| Ctrl+8 | Backtest |
| Ctrl+9 | Settings |

> Portfolio Optimization is launched from the **Optimize** button in the Portfolio view; Yield Curve / Recession Risk and Factor Exposure / Scenario Stress are sections within the **Macro** view.

## Desktop Build (Windows)

Build a portable, self-contained Windows app (no Python install needed to run it):

```bash
pip install -e ".[build]"
python build.py
```

This produces `dist/StockX/StockX.exe`. The build is **portable** — `data/`, `memory/`, and `.env` live next to the exe, so the bundle is self-contained and never touches your dev copy. Drop a `.env` (or set keys in the Settings tab) beside the exe to configure it.

## Architecture

```
run_gui.py                  ← GUI launcher (qasync event loop)
paths.py                    ← frozen-aware path resolution (dev = repo root; frozen = next to exe)
gui/app.py                  ← MainWindow, top nav bar, agent init retry
gui/views/                  ← Analysis, Watchlist, Portfolio, News, Earnings, Heatmap, Macro, Backtest, Settings
gui/state.py                ← AppState with atomic persistence, schema versioning, backup recovery
gui/theme.py                ← Dark/light stylesheets, color constants, currency formatting

agent/core.py               ← ReAct reasoning loop (12 steps max, streaming)
llm/router.py               ← Multi-provider LLM fallover chain
tools/stock.py              ← Stock analysis with yfinance + scoring engine
tools/search.py             ← Web search (Brave/Tavily/DuckDuckGo)
memory/store.py             ← ChromaDB + JSONL memory backend

services/monitor.py         ← Background watchlist + commodity price monitor
services/research.py        ← FRED + EIA API clients with TTL cache
services/knowledge.py       ← Curated economic knowledge (chokepoints, crises, trade flows)
services/indicators.py      ← Technical indicators (RSI, MACD, Bollinger, ATR, ADX, + vectorized series)
services/macro_signals.py   ← Contextual signal engine (good/bad coloring by economic meaning)
services/macro_charts.py    ← Correlation heatmap renderer
services/consumer_inflation.py ← Commodity-to-consumer pass-through model
services/backtest.py        ← Vectorized lookahead-safe backtest engine + strategies
services/perf_metrics.py    ← Pure performance/risk metrics (Sharpe, Sortino, drawdown, alpha/beta)
services/optimize.py        ← scipy mean-variance portfolio optimizer (efficient frontier)
services/yield_curve.py     ← Treasury yield curve + FRED-fitted recession probit
services/factor_exposure.py ← Multivariate factor betas + scenario stress library
services/charting.py        ← matplotlib chart rendering (portfolio, sparklines, P&L, equity curve, frontier)
services/sentiment.py       ← Lexicon-based headline sentiment scorer
services/notifications.py   ← Desktop toast notifications via plyer
services/diagnostics.py     ← Tool call timing and diagnostics
```

## Configuration

See [`.env.example`](.env.example) for all available environment variables.

## License

Copyright (c) 2026 shivnarainms22. All rights reserved.

This source code is provided for viewing purposes only. No permission is granted to copy, modify, distribute, or use this software without explicit written consent from the author.
