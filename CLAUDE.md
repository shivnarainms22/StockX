# StockX — CLAUDE.md

Developer guide for working on this codebase. Read this before making changes.

---

## Project Overview

StockX is a local AI agent for Windows with a fintech-style PyQt6 GUI. It performs stock analysis, portfolio tracking, watchlist monitoring, and web search via a ReAct reasoning loop backed by a multi-provider LLM fallover chain.

---

## Running the App

```bash
# GUI (primary entry point)
python run_gui.py

# Legacy non-GUI modes (unused in current form — main.py now mirrors run_gui.py)
python main.py
```

**Package manager**: `uv` (lock file: `uv.lock`). Install deps:
```bash
uv sync
# or
pip install -e .
```

---

## Architecture Map

```
run_gui.py              ← GUI launcher (qasync event loop setup)
gui/app.py              ← MainWindow, NavSidebar, NavButton; Ctrl+1-7 shortcuts; apply_theme()
gui/views/
  analysis.py           ← AnalysisView + AnalysisWorker(QThread); score card; PDF export; session resume
  watchlist.py          ← Watchlist with price/RSI alerts; sparklines; drag-to-reorder; target prices; alert history panel
  portfolio.py          ← Holdings tracker; chart mode toggle (Value/Returns%/Benchmark); dividend tracking
  news.py               ← Financial news aggregator; sentiment dots
  earnings.py           ← Earnings calendar grid
  heatmap.py            ← Sector heatmap (18 ETFs, 3-column grid); click-to-analyse
  settings.py           ← API keys, provider detection, data export
gui/theme.py            ← Color constants + dark QSS + light QSS; get_stylesheet(dark)
gui/state.py            ← AppState dataclass, Message, JSON persistence; session & alert history

agent/core.py           ← ReAct loop (12 steps max, streaming)
llm/router.py           ← NVIDIA NIM → Anthropic → OpenAI fallover
memory/store.py         ← ChromaDB (primary) + JSONL (fallback) memory
tools/stock.py          ← Full-spectrum stock analysis; TTL cache; SCORE_CARD sentinel; parallel multi-ticker
tools/search.py         ← Brave/Tavily/DuckDuckGo web search; TTL cache
tools/base.py           ← Abstract BaseTool

services/monitor.py     ← Background watchlist price/RSI/target/earnings monitor; saves alert history
services/charting.py    ← matplotlib PNG: portfolio chart, sparkline, P&L %, benchmark overlay
services/sentiment.py   ← Lexicon-based headline sentiment scorer (0.0–1.0)
services/notifications.py ← Desktop toast via plyer

data/                   ← Runtime JSON/JSONL data files (gitignore these)
data/session.json       ← Persisted conversation session (auto-written on each message)
data/alert_history.json ← Alert log, capped at 200 entries
memory/chroma_db/       ← ChromaDB vector store (gitignore this)
```

---

## Threading Model — Critical

This is the most error-prone area. Get this right before touching async/threading code.

### LLM Analysis (AnalysisWorker)
- `AnalysisWorker` extends `QThread` — it **must** be stored as `self._worker` on `AnalysisView`, never as a local variable. Local variables get garbage-collected, killing the thread mid-run.
- The worker creates its own `asyncio.new_event_loop()` — it does NOT use the main thread's qasync loop.
- Cleanup mirrors `asyncio.run()`: call `loop.shutdown_asyncgens()` **before** `loop.close()`. Skipping `shutdown_asyncgens()` causes segfaults on Python 3.13 from GC'd async generators.
- Cancel flow: `worker.cancel()` → `loop.call_soon_threadsafe(task.cancel)` — this is the thread-safe path. Do not call asyncio directly from the main thread into the worker's loop.
- Disconnect all signals in `_cleanup()` after each analysis to prevent double-delivery on the next run.

### Main Thread Async (everything else)
- Watchlist refresh, portfolio updates, earnings/news fetches: plain `async def` coroutines driven by the qasync `QEventLoop` on the main thread. Use `asyncio.ensure_future()` to schedule them, **not** `get_event_loop().create_task()`.
- `services/monitor.py` takes a `show_alert: Callable[[str, str], None]` callback injected at startup. It must not touch Qt widgets directly — only call the callback, which dispatches on the main thread.

### Dialogs
- Always use `dialog.show()` (non-blocking). Never `dialog.exec()` — this creates a nested event loop and deadlocks with qasync.

---

## ReAct Loop (agent/core.py)

`AgentCore.run(task, history=[], on_chunk=None)`:
- `history`: list of prior `{"role": ..., "content": ...}` messages for multi-turn sessions
- `on_chunk`: streaming callback `(str) -> None`; if `None`, accumulates and returns final string
- Max steps: 12 (`AGENT_MAX_STEPS` env var)
- Max context tokens: 102,400 (`AGENT_MAX_CONTEXT_TOKENS` env var)
- `_trim_messages()` drops the oldest Observation messages when the token budget is exceeded. Thought/Action/Final Answer messages are preserved longer.
- `_run_tool_with_retry()` retries exactly once (1 s delay) if the tool raises or returns a string starting with `"Error:"`.

Format the LLM must follow:
```
Thought: ...
Action: tool_name
Action Input: ...
Observation: [injected by agent]
...
Final Answer: ...
```

---

## LLM Router (llm/router.py)

Fallover priority: **NVIDIA NIM → Anthropic Claude Sonnet → OpenAI GPT-4o-mini**

- A provider is skipped if its API key is absent or is a placeholder string.
- `_MAX_OUTPUT` dict maps provider name → max output tokens (NVIDIA: 4096, Anthropic: 8192, OpenAI: 16384).
- `complete(messages)` → `str` (non-streaming)
- `complete_stream(messages)` → `AsyncGenerator[str, None]` (streaming)

When adding a new provider:
1. Add key detection logic in `_detect_providers()`
2. Add entry to `_MAX_OUTPUT`
3. Implement `_complete_<provider>()` and `_stream_<provider>()` methods
4. Insert at correct priority position

---

## Memory (memory/store.py)

Dual-backend with automatic fallback:
- **ChromaDB** (primary): cosine similarity search, dedup threshold `distance < 0.03`, async init via `asyncio.Lock`
- **JSONL** (fallback): `memory/memory.jsonl`, line-by-line keyword search, `asyncio.Lock` for writes

Key methods:
- `add(text, metadata={})` — stores with ISO timestamp
- `search(query, top_k=3)` — returns list of strings
- `cleanup()` — called at startup; prunes oldest entries if count > `MEMORY_JSONL_MAX_ENTRIES` (default 500)

Do not write directly to memory files. Always go through `MemoryStore`.

---

## Stock Tool (tools/stock.py)

Three actions exposed to the agent:
- `analyse` — full technical + fundamental + macro analysis on a single ticker
- `screen` — sector screening (30+ sectors) returning ranked candidates
- `report` — structured report generation

**Company name → ticker resolution**: dictionary lookup first, then yfinance fallback. If a user says "Apple" the tool resolves to "AAPL" before any API call.

**Rate-limit safety**: yfinance calls use 4-attempt retry with `2^n` second backoff.

**Multi-currency**: suffix inference (`.NS` → INR, `.L` → GBP, etc.) plus 40+ explicit currency codes. Currency helpers live in `gui/theme.py::fmt_price()` and `currency_symbol()`.

**Scoring** (out of ~45 pts):
- Technical component: up to 20 pts (trend, momentum, volume)
- Fundamental component: up to 25 pts (valuation, growth, quality)
- Risk adjustment: ±5 pts
- Tiers: STRONG BUY (≥30), BUY (≥22), WATCH/HOLD (≥14), CAUTION (≥7), AVOID (<7)

**Result cache**: `_ticker_cache` dict, TTL = 300 s. Cache key is the ticker symbol. Cleared automatically on TTL expiry; call `clear_ticker_cache(ticker)` to invalidate manually.

**SCORE_CARD sentinel**: `_analyse_ticker()` appends `SCORE_CARD:{json}` as the last line of its output. `AnalysisView._on_done()` strips this line from the displayed text and renders it as a score card widget. Never remove this line or change its prefix.

**Parallel multi-ticker**: when `analyse` is called with multiple tickers, `_analyse_multiple()` runs them concurrently via `ThreadPoolExecutor(max_workers=4)`. The `_yf_lock` still serializes actual network calls; only post-fetch computation is parallelized.

---

## GUI Conventions

### Theme
All colors and spacing are defined in `gui/theme.py`. Do not hardcode hex values inline — import the constants:
```python
from gui.theme import ACCENT, TEXT_1, SURFACE_2, fmt_price, currency_symbol
```

Key palette: `APP_BG` (#0B0F1A), `SURFACE_1/2/3`, `ACCENT` (#00C896 green), `ACCENT_CYAN` (#3DD9EB), `POSITIVE` (#00D4AA), `NEGATIVE` (#FF6B6B), `NAV_BG` (#0D1422).

The stylesheet is applied via `app.setStyleSheet(get_stylesheet(dark=True))` in `run_gui.py`. `get_stylesheet(dark)` returns `STYLESHEET` (dark) or `LIGHT_STYLESHEET` (light). The theme is controlled by `APP_THEME` env var (`dark` | `light`). `MainWindow.apply_theme(dark)` re-applies it at runtime without restarting. Do not call `setStyleSheet()` on individual widgets unless you need to override a specific property — it breaks stylesheet inheritance.

### Navigation
Nav sidebar has 7 items (indices 0–6): Analysis, Watchlist, Portfolio, News, Earnings, Markets (Heatmap), Settings. Keyboard shortcuts `Ctrl+1` through `Ctrl+7` switch views. When adding a new view, append it and add a sidebar button — do not insert in the middle as it shifts all shortcut indices.

### Charts
Charts are rendered as matplotlib PNG bytes and displayed via:
```python
label.setPixmap(QPixmap.fromImage(QImage.fromData(png_bytes)))
```
Chart generation lives in `services/charting.py`. Keep matplotlib imports inside that module — it adds ~0.3 s to startup if imported at the top level. Available helpers: `render_portfolio_chart`, `render_sparkline`, `render_pnl_chart`, `render_comparison_chart`.

### Cross-view Navigation
To navigate from one view to another and prefill data, call `MainWindow.switch_to_analysis(prefill)`. Do not import views into each other; always go through `MainWindow`.

### AppState
`gui/state.py` holds `AppState` with conversation history, watchlist, portfolio, settings, alert history, and session. Persist changes immediately via the `save_*()` methods — the app does not autosave on exit (graceful shutdown is best-effort).

Key persistence methods:
- `save_watchlist()` / `load_watchlist()` — watchlist items; each item may have `buy_target` and `sell_target` float fields
- `save_session()` / `load_session()` / `clear_session()` — full conversation + history to `data/session.json`; `save_session()` is called automatically inside `commit_to_history()`
- `save_alert(ticker, type, message)` / `load_alert_history()` — alert log to `data/alert_history.json`, capped at 200

### Sentiment
`services/sentiment.score_headline(text) -> float` returns 0.0 (bearish) – 1.0 (bullish), 0.5 = neutral. Pure lexicon-based, no model required. Used by `NewsView` to colour sentiment dots on news cards.

---

## Environment Variables

All read via `python-dotenv` from `.env` at project root.

| Variable | Default | Purpose |
|---|---|---|
| `NVIDIA_API_KEY` | — | NVIDIA NIM access |
| `ANTHROPIC_API_KEY` | — | Anthropic Claude access |
| `OPENAI_API_KEY` | — | OpenAI GPT access |
| `SEARCH_PROVIDER` | `brave` | `brave` \| `tavily` \| `duckduckgo` |
| `SEARCH_API_KEY` | — | Key for Brave/Tavily |
| `AGENT_MAX_STEPS` | `12` | ReAct loop step limit |
| `AGENT_MAX_CONTEXT_TOKENS` | `102400` | Token budget for trimming |
| `MEMORY_JSONL_PATH` | `memory/memory.jsonl` | JSONL fallback path |
| `MEMORY_CHROMA_DIR` | `memory/chroma_db` | ChromaDB directory |
| `MEMORY_JSONL_MAX_ENTRIES` | `500` | Max entries before pruning |
| `WATCHLIST_REFRESH_INTERVAL` | `15` | Minutes between auto-refresh |
| `APP_THEME` | `dark` | `dark` \| `light` — controls stylesheet on startup |

---

## Known Issues and Solutions

### Python 3.13 — Async Generator Finalizer
**Problem**: Segfault when GC cleans up async generators that span threads.
**Fix** (in `run_gui.py`): install a finalizer shim before starting the event loop:
```python
import sys
if sys.version_info >= (3, 13):
    sys.set_asyncgen_hooks(finalizer=lambda gen: gen.aclose())
```

### Python 3.13 — httpcore Compatibility
**Problem**: `httpcore` versions < 1.x crash on Python 3.13 due to removed `threading` internals.
**Fix**: pin `httpcore>=1.0` in `pyproject.toml`.

### qasync + QThread: event loop conflict
**Problem**: `asyncio.get_event_loop()` inside a `QThread` returns `None` or the main thread's loop.
**Fix**: `AnalysisWorker.__init__` must call `asyncio.new_event_loop()` and set it with `asyncio.set_event_loop(loop)` at the start of `run()`, not in `__init__`.

### Worker GC'd mid-run
**Problem**: Analysis silently stops; no error, no signal.
**Cause**: worker stored as a local variable → Python GC deletes it.
**Fix**: always `self._worker = AnalysisWorker(...)`.

### Double signal delivery
**Problem**: After a second analysis, callbacks fire twice.
**Fix**: disconnect all worker signals in `_cleanup()` before creating a new worker.

### Qt dialog deadlock
**Problem**: `dialog.exec()` freezes the app indefinitely.
**Fix**: always `dialog.show()` for non-blocking dialogs.

### ChromaDB cold start
**Problem**: First `search()` call takes 2–4 s while ChromaDB loads embeddings.
**Fix**: call `await memory.init()` eagerly during `_init_agent()` in `MainWindow`, not on first query.

---

## What Is Not Implemented

These were considered but explicitly deferred:
- **JSON/structured output mode**: would require prompt redesign + response parser. The current ReAct format is plain text.
- **Vision/screenshot analysis**: would require multi-modal message format in the LLM router and `agent/core.py`.
- **Voice mode**: `faster-whisper` + `sounddevice` are optional deps but no GUI surface exists. `main.py` referenced a voice mode skeleton that was never wired up.
- **Starlette server**: `server/local.py` exists but is not started by `run_gui.py`. The GUI is self-contained.

---

## Monitor (services/monitor.py)

Background loop that checks price/RSI/target/earnings conditions for each watchlist ticker.

- **Price target alerts**: fires when price is within ±2% of `buy_target` or `sell_target` set on the watchlist item.
- **Earnings proximity alerts**: fires when earnings date is ≤ 3 days away. Checked once per hour per ticker (cached in `_earnings_cache`).
- **Alert saving**: every alert fired calls `state.save_alert(ticker, type, message)` to persist to `data/alert_history.json`.
- Alert history is viewable via the "Alert History" toggle panel in `WatchlistView`.

---

## Data Files (do not commit)

```
.env
data/*.json
data/*.jsonl
memory/memory.jsonl
memory/chroma_db/
```

Add these to `.gitignore` if you publish the repo. They contain API keys and personal financial data.

---

## Dependencies Summary

Core: `PyQt6`, `qasync`, `httpx`, `yfinance`, `chromadb`, `aiofiles`, `matplotlib`, `plyer`, `python-dotenv`, `pandas`
Optional voice: `faster-whisper`, `sounddevice`, `numpy`
Legacy server: `starlette`, `uvicorn`, `websockets`, `playwright`
