"""
StockX — FRED and EIA research data feeds.
TTL-cached API clients for macroeconomic indicators.
Returns empty dicts gracefully when API keys are not configured.
"""
from __future__ import annotations

import os
import threading
import time


# ── Cache state ──────────────────────────────────────────────────────────────
_fred_cache: dict | None = None
_fred_cache_ts: float = 0.0
_fred_lock = threading.Lock()

_eia_cache: dict | None = None
_eia_cache_ts: float = 0.0
_eia_lock = threading.Lock()

_CACHE_TTL = 3600  # 1 hour


# ── FRED series we fetch ─────────────────────────────────────────────────────
_FRED_SERIES: dict[str, str] = {
    # ── US ──
    "UNRATE":    "US Unemployment",
    "FEDFUNDS":  "Fed Funds Rate",
    "T10Y2Y":    "US Yield Spread",
    "DTWEXBGS":  "USD Index",
    # ── Europe ──
    "ECBDFR":    "ECB Rate",
    "LRHUTTTTEZM156S":    "EU Unemployment",
    # ── China ──
    "MPMIEM3338M086S":    "China PMI",
    # ── India ──
    "IRSTCI01INM156N":    "RBI Rate",
}


def fetch_fred_indicators() -> dict[str, dict]:
    """Fetch latest FRED macro indicators. Returns {} if no API key or on error.

    Result format: {series_id: {name, value, previous, date, unit}}
    """
    global _fred_cache, _fred_cache_ts

    with _fred_lock:
        if _fred_cache is not None and (time.time() - _fred_cache_ts) < _CACHE_TTL:
            return _fred_cache

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        return {}

    try:
        import httpx

        results: dict[str, dict] = {}
        for series_id, name in _FRED_SERIES.items():
            try:
                resp = httpx.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key": api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 2,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                obs = data.get("observations", [])
                if not obs:
                    continue
                latest = obs[0]
                value = latest.get("value", ".")
                if value == ".":
                    continue
                previous = obs[1].get("value", ".") if len(obs) > 1 else None
                results[series_id] = {
                    "name": name,
                    "value": float(value),
                    "previous": float(previous) if previous and previous != "." else None,
                    "date": latest.get("date", ""),
                    "unit": "%",  # all remaining series are in % or index points
                }
            except Exception:
                continue

        with _fred_lock:
            _fred_cache = results
            _fred_cache_ts = time.time()
        return results

    except Exception:
        return {}


def fetch_eia_petroleum() -> dict:
    """Fetch crude oil weekly inventory from EIA. Returns {} if no key or on error.

    Result format: {"crude_inventory": {value, date, unit, previous}}
    """
    global _eia_cache, _eia_cache_ts

    with _eia_lock:
        if _eia_cache is not None and (time.time() - _eia_cache_ts) < _CACHE_TTL:
            return _eia_cache

    api_key = os.environ.get("EIA_API_KEY", "").strip()
    if not api_key:
        return {}

    try:
        import httpx

        resp = httpx.get(
            "https://api.eia.gov/v2/petroleum/stoc/wstk/data/",
            params={
                "api_key": api_key,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[product][]": "EPC0",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 2,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return {}

        data = resp.json()
        entries = data.get("response", {}).get("data", [])
        if not entries:
            return {}

        latest = entries[0]
        previous = entries[1] if len(entries) > 1 else None

        result = {
            "crude_inventory": {
                "value": float(latest.get("value", 0)),
                "date": latest.get("period", ""),
                "unit": "thousand barrels",
                "previous": float(previous.get("value", 0)) if previous else None,
            }
        }

        with _eia_lock:
            _eia_cache = result
            _eia_cache_ts = time.time()
        return result

    except Exception:
        return {}


def build_research_context() -> str:
    """Fetch FRED + EIA data and format for prompt injection."""
    sections: list[str] = []

    fred = fetch_fred_indicators()
    if fred:
        # Group by region for readability
        _REGION_MAP = {
            "UNRATE": "US", "FEDFUNDS": "US", "T10Y2Y": "US",
            "DTWEXBGS": "US",
            "ECBDFR": "Europe", "LRHUTTTTEZM156S": "Europe",
            "MPMIEM3338M086S": "China",
            "IRSTCI01INM156N": "India",
        }
        by_region: dict[str, list[str]] = {}
        for sid, info in fred.items():
            val = info["value"]
            prev = info.get("previous")
            unit = info.get("unit", "")
            date = info.get("date", "")

            if prev is not None:
                delta = val - prev
                sign = "+" if delta >= 0 else ""
                change = f" ({sign}{delta:.2f} from previous)"
            else:
                change = ""

            if unit == "%":
                line = f"  {info['name']}: {val:.2f}%{change} (as of {date})"
            else:
                line = f"  {info['name']}: {val:,.2f}{change} (as of {date})"

            region = _REGION_MAP.get(sid, "Other")
            by_region.setdefault(region, []).append(line)

        lines = ["LIVE GLOBAL MACRO INDICATORS (FRED):"]
        for region in ["US", "Europe", "China", "India"]:
            if region in by_region:
                lines.append(f"  [{region}]")
                lines.extend(by_region[region])
        sections.append("\n".join(lines))

    eia = fetch_eia_petroleum()
    if eia and "crude_inventory" in eia:
        inv = eia["crude_inventory"]
        val = inv["value"]
        prev = inv.get("previous")
        date = inv.get("date", "")

        change = ""
        if prev is not None:
            delta = val - prev
            sign = "+" if delta >= 0 else ""
            change = f" ({sign}{delta:,.0f} from previous week)"

        sections.append(
            f"EIA PETROLEUM DATA:\n"
            f"  US Crude Oil Inventory: {val:,.0f} thousand barrels{change} (week of {date})"
        )

    return "\n\n".join(sections) if sections else ""
