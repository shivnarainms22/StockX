"""
StockX diagnostics metrics.
Thread-safe in-memory counters for provider/tool/cache health.
"""
from __future__ import annotations

import threading
import time
from copy import deepcopy


_lock = threading.Lock()

_metrics: dict = {
    "llm": {
        "selected_provider": "",
        "attempts": {},
        "success": {},
        "failures": {},
        "fallback_count": 0,
        "last_latency_ms": {},
        "last_error": "",
        "degraded_mode": False,
    },
    "tools": {
        "latency_ms_total": {},
        "calls": {},
        "errors": {},
    },
    "cache": {
        "search": {"hits": 0, "misses": 0},
        "stock": {"hits": 0, "misses": 0},
    },
    "updated_ts": 0.0,
}


def _touch() -> None:
    _metrics["updated_ts"] = time.time()


def record_provider_attempt(name: str) -> None:
    with _lock:
        llm = _metrics["llm"]
        llm["attempts"][name] = int(llm["attempts"].get(name, 0)) + 1
        _touch()


def record_provider_success(name: str, latency_ms: float, fallback_depth: int = 0) -> None:
    with _lock:
        llm = _metrics["llm"]
        llm["selected_provider"] = name
        llm["success"][name] = int(llm["success"].get(name, 0)) + 1
        llm["last_latency_ms"][name] = round(float(latency_ms), 1)
        if fallback_depth > 0:
            llm["fallback_count"] = int(llm.get("fallback_count", 0)) + 1
            llm["degraded_mode"] = True
        else:
            llm["degraded_mode"] = False
        _touch()


def record_provider_failure(name: str, error: str) -> None:
    with _lock:
        llm = _metrics["llm"]
        llm["failures"][name] = int(llm["failures"].get(name, 0)) + 1
        llm["last_error"] = str(error)[:180]
        _touch()


def record_tool_call(tool_name: str, latency_ms: float, ok: bool) -> None:
    with _lock:
        tools = _metrics["tools"]
        tools["calls"][tool_name] = int(tools["calls"].get(tool_name, 0)) + 1
        tools["latency_ms_total"][tool_name] = float(
            tools["latency_ms_total"].get(tool_name, 0.0)
        ) + float(latency_ms)
        if not ok:
            tools["errors"][tool_name] = int(tools["errors"].get(tool_name, 0)) + 1
        _touch()


def record_cache(tool_name: str, hit: bool) -> None:
    with _lock:
        if tool_name not in _metrics["cache"]:
            _metrics["cache"][tool_name] = {"hits": 0, "misses": 0}
        row = _metrics["cache"][tool_name]
        key = "hits" if hit else "misses"
        row[key] = int(row.get(key, 0)) + 1
        _touch()


def snapshot() -> dict:
    with _lock:
        data = deepcopy(_metrics)

    tools = data.get("tools", {})
    calls = tools.get("calls", {})
    totals = tools.get("latency_ms_total", {})
    tool_avg_latency_ms: dict[str, float] = {}
    tool_error_rate: dict[str, float] = {}
    for tool_name, n_calls in calls.items():
        n = max(int(n_calls), 1)
        total_ms = float(totals.get(tool_name, 0.0))
        tool_avg_latency_ms[tool_name] = round(total_ms / n, 1)
        err = int(tools.get("errors", {}).get(tool_name, 0))
        tool_error_rate[tool_name] = round((err / n) * 100, 1)

    cache_rates: dict[str, float] = {}
    for name, row in data.get("cache", {}).items():
        hits = int(row.get("hits", 0))
        misses = int(row.get("misses", 0))
        total = hits + misses
        cache_rates[name] = round((hits / total) * 100, 1) if total else 0.0

    data["derived"] = {
        "tool_avg_latency_ms": tool_avg_latency_ms,
        "tool_error_rate_pct": tool_error_rate,
        "cache_hit_rate_pct": cache_rates,
    }
    return data
