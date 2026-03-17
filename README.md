# StockX

A local AI-powered stock analysis agent for Windows with a fintech-style dark GUI. Performs technical + fundamental analysis, portfolio tracking, watchlist monitoring, and web search — all driven by a ReAct reasoning loop backed by a multi-provider LLM fallover chain.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)

## Features

- **AI Stock Analysis** — full-spectrum technical, fundamental, and macro analysis with scored recommendations (STRONG BUY → AVOID)
- **Sector Screening** — scan 30+ sectors for top-ranked candidates
- **Portfolio Tracker** — holdings, P&L, dividends, benchmark comparison charts
- **Watchlist** — price/RSI alerts, sparklines, buy/sell targets, drag-to-reorder
- **Earnings Calendar** — upcoming earnings dates in a grid view
- **Sector Heatmap** — 18 sector ETFs with colour-coded daily performance
- **Financial News** — aggregated headlines with sentiment scoring
- **Multi-Provider LLM** — automatic fallover: NVIDIA NIM → Anthropic Claude → OpenAI GPT
- **Memory** — ChromaDB vector store with JSONL fallback for conversation context
- **Desktop Alerts** — toast notifications for price targets and earnings proximity

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

Optional: set `SEARCH_API_KEY` with `SEARCH_PROVIDER=brave` or `tavily` for web search. Falls back to DuckDuckGo scraping if not set.

## Usage

```bash
python run_gui.py
```

Navigate between views with the sidebar or keyboard shortcuts `Ctrl+1` through `Ctrl+7`:

| Shortcut | View |
|----------|------|
| Ctrl+1 | Analysis |
| Ctrl+2 | Watchlist |
| Ctrl+3 | Portfolio |
| Ctrl+4 | News |
| Ctrl+5 | Earnings |
| Ctrl+6 | Markets (Heatmap) |
| Ctrl+7 | Settings |

## Architecture

```
run_gui.py              ← GUI launcher (qasync event loop)
gui/app.py              ← MainWindow, navigation sidebar
gui/views/              ← Analysis, Watchlist, Portfolio, News, Earnings, Heatmap, Settings
agent/core.py           ← ReAct reasoning loop (12 steps max, streaming)
llm/router.py           ← Multi-provider LLM fallover chain
tools/stock.py          ← Stock analysis with yfinance + scoring engine
tools/search.py         ← Web search (Brave/Tavily/DuckDuckGo)
memory/store.py         ← ChromaDB + JSONL memory backend
services/monitor.py     ← Background watchlist price/RSI/earnings monitor
services/charting.py    ← matplotlib chart rendering
services/sentiment.py   ← Lexicon-based headline sentiment scorer
```

## Configuration

See [`.env.example`](.env.example) for all available environment variables.

## License

Copyright (c) 2026 shivnarainms22. All rights reserved.

This source code is provided for viewing purposes only. No permission is granted to copy, modify, distribute, or use this software without explicit written consent from the author.
