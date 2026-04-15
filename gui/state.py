"""
StockX GUI — Shared application state.
Passed to every view so they share agent instance, conversation, and history.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
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
_MAX_ALERT_HISTORY = 200
_STATE_SCHEMA_VERSION = 2

_DATA_DIR = Path(__file__).parent.parent / "data"


def _backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".bak")


def _wrap_payload(data) -> dict:
    return {
        "_schema_version": _STATE_SCHEMA_VERSION,
        "data": data,
    }


def _unwrap_payload(raw):
    if isinstance(raw, dict) and "data" in raw and "_schema_version" in raw:
        try:
            version = int(raw.get("_schema_version", 1))
        except Exception:
            version = 1
        return version, raw.get("data")
    return 1, raw


def _atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    backup = _backup_path(path)

    if path.exists():
        try:
            shutil.copy2(path, backup)
        except Exception:
            pass

    text = json.dumps(data, indent=2, ensure_ascii=False)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def _load_json_with_backup(path: Path):
    primary = path
    backup = _backup_path(path)
    parse_errors = 0

    for candidate in (primary, backup):
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if candidate == backup:
                try:
                    _atomic_write_json(primary, data)
                except Exception:
                    pass
            return data
        except Exception:
            parse_errors += 1
            continue

    if parse_errors > 0:
        return None
    return None


def _coerce_float(value, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _migrate_watchlist(
    data,
    *,
    default_cooldown: int,
    default_confidence: float,
) -> list[dict]:
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    numeric_fields = (
        "price_above",
        "price_below",
        "rsi_above",
        "rsi_below",
        "buy_target",
        "sell_target",
        "min_confidence",
    )
    for row in data:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        migrated = {"ticker": ticker}
        for key in numeric_fields:
            if key in row:
                val = _coerce_float(row.get(key))
                if val is not None:
                    migrated[key] = val
        migrated["alert_cooldown_minutes"] = max(
            _coerce_int(row.get("alert_cooldown_minutes"), default_cooldown),
            1,
        )
        migrated["min_confidence"] = min(
            max(_coerce_float(row.get("min_confidence"), default_confidence) or default_confidence, 0.0),
            1.0,
        )
        out.append(migrated)
    return out


def _migrate_alert_history(data) -> list[dict]:
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for row in data[:_MAX_ALERT_HISTORY]:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": str(row.get("id") or uuid.uuid4()),
                "ts": str(row.get("ts") or ""),
                "ticker": str(row.get("ticker") or ""),
                "type": str(row.get("type") or "price"),
                "message": str(row.get("message") or ""),
                "confidence": _coerce_float(row.get("confidence")),
                "price": _coerce_float(row.get("price")),
            }
        )
    return out


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
    agent_init_in_progress: bool = False
    agent_init_error: str = ""
    agent_init_attempts: int = 0

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
    default_alert_cooldown_minutes: int = 30
    default_alert_confidence: float = 0.55
    alert_precision_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def _load_json_payload(self, filename: str):
        path = _DATA_DIR / filename
        raw = _load_json_with_backup(path)
        if raw is None:
            return None
        _version, data = _unwrap_payload(raw)
        return data

    def _save_json_payload(self, filename: str, data) -> None:
        path = _DATA_DIR / filename
        _atomic_write_json(path, _wrap_payload(data))

    def load_portfolio(self) -> None:
        data = self._load_json_payload("portfolio.json")
        if isinstance(data, list):
            self.portfolio = data
        else:
            self.portfolio = []

    def save_portfolio(self) -> None:
        self._save_json_payload("portfolio.json", self.portfolio)

    def load_watchlist(self) -> None:
        data = self._load_json_payload("watchlist.json")
        self.watchlist = _migrate_watchlist(
            data,
            default_cooldown=self.default_alert_cooldown_minutes,
            default_confidence=self.default_alert_confidence,
        )

    def save_watchlist(self) -> None:
        self.watchlist = _migrate_watchlist(
            self.watchlist,
            default_cooldown=self.default_alert_cooldown_minutes,
            default_confidence=self.default_alert_confidence,
        )
        self._save_json_payload("watchlist.json", self.watchlist)

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
        session = {
            "history": self.history,
            "conversation": [
                {"id": m.id, "role": m.role, "content": m.content, "is_streaming": False}
                for m in self.conversation
                if not m.is_streaming
            ],
        }
        self._save_json_payload("session.json", session)

    def load_session(self) -> bool:
        """Load conversation + history from data/session.json. Returns True if found."""
        data = self._load_json_payload("session.json")
        if not isinstance(data, dict):
            return False
        try:
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
        data = self._load_json_payload("alert_history.json")
        self.alert_history = _migrate_alert_history(data)

    def save_alert(
        self,
        ticker: str,
        alert_type: str,
        message: str,
        *,
        confidence: float | None = None,
        price: float | None = None,
    ) -> None:
        """Prepend an alert entry, cap at 200, and persist."""
        import datetime as _dt
        entry = {
            "id":      str(uuid.uuid4()),
            "ts":      _dt.datetime.now().isoformat(timespec="seconds"),
            "ticker":  ticker,
            "type":    alert_type,
            "message": message,
            "confidence": confidence,
            "price": price,
        }
        self.alert_history.insert(0, entry)
        if len(self.alert_history) > _MAX_ALERT_HISTORY:
            self.alert_history = self.alert_history[:_MAX_ALERT_HISTORY]
        self._save_json_payload("alert_history.json", self.alert_history)

    def load_alert_metrics(self) -> None:
        data = self._load_json_payload("alert_metrics.json")
        if not isinstance(data, dict):
            self.alert_precision_stats = {}
            return
        stats: dict[str, dict[str, int]] = {}
        for key, row in data.items():
            if not isinstance(row, dict):
                continue
            total = _coerce_int(row.get("total"), 0)
            hits = _coerce_int(row.get("hits"), 0)
            stats[str(key)] = {"total": max(total, 0), "hits": max(min(hits, total), 0)}
        self.alert_precision_stats = stats

    def record_alert_precision(self, alert_type: str, hit: bool) -> None:
        row = self.alert_precision_stats.setdefault(alert_type, {"total": 0, "hits": 0})
        row["total"] = int(row.get("total", 0)) + 1
        if hit:
            row["hits"] = int(row.get("hits", 0)) + 1
        self._save_json_payload("alert_metrics.json", self.alert_precision_stats)

    # ── Analysis history ──────────────────────────────────────────────────

    def load_analysis_history(self) -> None:
        data = self._load_json_payload("analysis_history.json")
        self.analysis_history = data if isinstance(data, list) else []

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
        self._save_json_payload("analysis_history.json", self.analysis_history)

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
        data = self._load_json_payload("commodity_state.json")
        if not isinstance(data, dict):
            return
        self.last_commodity_prices = data.get("last_prices", {}) or {}
        self.commodity_alert_enabled = bool(data.get("alert_enabled", True))
        self.commodity_alert_threshold = float(data.get("alert_threshold", 3.0) or 3.0)

    def save_commodity_state(self) -> None:
        self._save_json_payload(
            "commodity_state.json",
            {
                "last_prices": self.last_commodity_prices,
                "alert_enabled": self.commodity_alert_enabled,
                "alert_threshold": self.commodity_alert_threshold,
            },
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
