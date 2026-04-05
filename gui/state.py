"""
StockX GUI — Shared application state.
Passed to every view so they share agent instance, conversation, and history.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core import AgentCore

# Mirror the sliding-window cap from main.py
_MAX_HISTORY_EXCHANGES = 10
_MAX_ANALYSIS_HISTORY  = 50

_DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class Message:
    id: str
    role: str          # "user" | "agent"
    content: str
    is_streaming: bool = False


@dataclass
class AppState:
    agent: "AgentCore | None" = None

    # Display-only list of Message objects for rendering bubbles
    conversation: list[Message] = field(default_factory=list)

    # LLM context — completed turns only (user+assistant pairs).
    history: list[dict[str, str]] = field(default_factory=list)

    is_busy: bool = False
    agent_task: "asyncio.Task | None" = None

    # Portfolio: list of {"ticker": str, "qty": float, "avg_cost": float}
    portfolio: list[dict] = field(default_factory=list)

    # Watchlist: list of {"ticker": str, "price_above": float|None, "price_below": float|None,
    #                      "rsi_above": float|None, "rsi_below": float|None}
    watchlist: list[dict] = field(default_factory=list)

    alert_interval_minutes: int = 15
    watchlist_refresh_interval: int = 0  # minutes; 0 = off

    # Analysis history: list of {"id", "ts", "preview", "query", "response"}
    analysis_history: list[dict] = field(default_factory=list)

    # Portfolio daily snapshots: list of {"date", "value", "currency"}
    portfolio_snapshots: list[dict] = field(default_factory=list)

    # Alert history: list of {"id", "ts", "ticker", "type", "message"}
    alert_history: list[dict] = field(default_factory=list)

    # Commodity monitoring
    commodity_alert_enabled: bool = True
    commodity_alert_threshold: float = 3.0   # % daily move to trigger alert
    last_commodity_prices: dict = field(default_factory=dict)  # {symbol: {price, ts}}

    def load_portfolio(self) -> None:
        path = _DATA_DIR / "portfolio.json"
        if path.exists():
            try:
                self.portfolio = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.portfolio = []

    def save_portfolio(self) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        (_DATA_DIR / "portfolio.json").write_text(
            json.dumps(self.portfolio, indent=2), encoding="utf-8"
        )

    def load_watchlist(self) -> None:
        path = _DATA_DIR / "watchlist.json"
        if path.exists():
            try:
                self.watchlist = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.watchlist = []

    def save_watchlist(self) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        (_DATA_DIR / "watchlist.json").write_text(
            json.dumps(self.watchlist, indent=2), encoding="utf-8"
        )

    def add_display_user(self, text: str) -> Message:
        """Add a user message to the display conversation (not history yet)."""
        msg = Message(id=str(uuid.uuid4()), role="user", content=text)
        self.conversation.append(msg)
        return msg

    def add_display_agent_placeholder(self) -> Message:
        """Add an empty streaming placeholder for the agent response."""
        msg = Message(id=str(uuid.uuid4()), role="agent", content="", is_streaming=True)
        self.conversation.append(msg)
        return msg

    def commit_to_history(self, user_text: str, agent_text: str) -> None:
        """Append completed turn to history and enforce the sliding-window cap."""
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": agent_text})
        max_messages = _MAX_HISTORY_EXCHANGES * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]
        self.save_session()

    def clear_conversation(self) -> None:
        self.conversation.clear()
        self.history.clear()
        self.clear_session()

    # ── Session persistence (item 1) ──────────────────────────────────────

    def save_session(self) -> None:
        """Persist current conversation + history to data/session.json."""
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        session = {
            "history": self.history,
            "conversation": [
                {"id": m.id, "role": m.role, "content": m.content, "is_streaming": False}
                for m in self.conversation
                if not m.is_streaming
            ],
        }
        (_DATA_DIR / "session.json").write_text(
            json.dumps(session, indent=2), encoding="utf-8"
        )

    def load_session(self) -> bool:
        """Load conversation + history from data/session.json. Returns True if found."""
        path = _DATA_DIR / "session.json"
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.history = data.get("history", [])
            self.conversation = [
                Message(
                    id=m.get("id", str(uuid.uuid4())),
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    is_streaming=m.get("is_streaming", False),
                )
                for m in data.get("conversation", [])
            ]
            return True
        except Exception:
            return False

    def clear_session(self) -> None:
        """Delete persisted session file."""
        path = _DATA_DIR / "session.json"
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    # ── Alert history (item 15) ───────────────────────────────────────────

    def load_alert_history(self) -> None:
        path = _DATA_DIR / "alert_history.json"
        if path.exists():
            try:
                self.alert_history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.alert_history = []

    def save_alert(self, ticker: str, alert_type: str, message: str) -> None:
        """Prepend an alert entry, cap at 200, and persist."""
        import datetime as _dt
        entry = {
            "id":      str(uuid.uuid4()),
            "ts":      _dt.datetime.now().isoformat(timespec="seconds"),
            "ticker":  ticker,
            "type":    alert_type,
            "message": message,
        }
        self.alert_history.insert(0, entry)
        if len(self.alert_history) > 200:
            self.alert_history = self.alert_history[:200]
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        (_DATA_DIR / "alert_history.json").write_text(
            json.dumps(self.alert_history, indent=2), encoding="utf-8"
        )

    # ── Analysis history ──────────────────────────────────────────────────

    def load_analysis_history(self) -> None:
        path = _DATA_DIR / "analysis_history.json"
        if path.exists():
            try:
                self.analysis_history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.analysis_history = []

    def save_history_entry(self, query: str, response: str) -> None:
        entry = {
            "id":       str(uuid.uuid4()),
            "ts":       __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "preview":  query[:60],
            "query":    query,
            "response": response,
        }
        self.analysis_history.insert(0, entry)
        if len(self.analysis_history) > _MAX_ANALYSIS_HISTORY:
            self.analysis_history = self.analysis_history[:_MAX_ANALYSIS_HISTORY]
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        (_DATA_DIR / "analysis_history.json").write_text(
            json.dumps(self.analysis_history, indent=2), encoding="utf-8"
        )

    # ── Portfolio snapshots ───────────────────────────────────────────────

    def load_portfolio_snapshots(self) -> None:
        path = _DATA_DIR / "portfolio_snapshots.jsonl"
        if path.exists():
            try:
                self.portfolio_snapshots = [
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except Exception:
                self.portfolio_snapshots = []

    def save_portfolio_snapshot(self, prices: dict[str, float], currencies: dict[str, str]) -> None:
        """Save today's total portfolio value; skips if today already recorded."""
        today = date.today().isoformat()
        if any(s["date"] == today for s in self.portfolio_snapshots):
            return
        # Only include holdings that have live prices; skip unavailable tickers
        tickers = [h["ticker"] for h in self.portfolio if h["ticker"] in prices]
        if not tickers:
            return
        total = 0.0
        dominant_currency = "USD"
        for h in self.portfolio:
            t = h["ticker"]
            if t not in prices:
                continue
            price = prices[t]
            total += price * h["qty"]
            if t in currencies:
                dominant_currency = currencies[t]
        if total <= 0:
            return
        snap = {"date": today, "value": round(total, 2), "currency": dominant_currency}
        self.portfolio_snapshots.append(snap)
        # Cap at 730 entries (~2 years of daily snapshots); rewrite file when trimming
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _DATA_DIR / "portfolio_snapshots.jsonl"
        if len(self.portfolio_snapshots) > 730:
            self.portfolio_snapshots = self.portfolio_snapshots[-730:]
            path.write_text(
                "\n".join(json.dumps(s) for s in self.portfolio_snapshots) + "\n",
                encoding="utf-8",
            )
        else:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(snap) + "\n")

    # ── Commodity state persistence ─────────────────────────────────────

    def load_commodity_state(self) -> None:
        path = _DATA_DIR / "commodity_state.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.last_commodity_prices = data.get("last_prices", {})
                self.commodity_alert_enabled = data.get("alert_enabled", True)
                self.commodity_alert_threshold = data.get("alert_threshold", 3.0)
            except Exception:
                pass

    def save_commodity_state(self) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        (_DATA_DIR / "commodity_state.json").write_text(
            json.dumps({
                "last_prices": self.last_commodity_prices,
                "alert_enabled": self.commodity_alert_enabled,
                "alert_threshold": self.commodity_alert_threshold,
            }, indent=2),
            encoding="utf-8",
        )

    def detect_provider(self) -> str:
        """Return the name of the active LLM provider by inspecting env vars."""
        placeholders = {
            "nvapi-your-key-here",
            "sk-ant-your-key-here",
            "sk-your-key-here",
            "sk-proj-your-key-here",
            "",
        }

        def valid(key: str) -> bool:
            return bool(key) and key.strip() not in placeholders

        if valid(os.getenv("NVIDIA_API_KEY", "")):
            return "NVIDIA NIM / llama-3.1-70b"
        if valid(os.getenv("ANTHROPIC_API_KEY", "")):
            return "Anthropic / claude-sonnet-4-6"
        if valid(os.getenv("OPENAI_API_KEY", "")):
            return "OpenAI / gpt-4o-mini"
        return "No provider configured"
