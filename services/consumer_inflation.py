"""
StockX - Consumer inflation analytics engine.
Builds region-level CPI pressure estimates from commodity shocks using lagged
pass-through coefficients, forecast-vs-actual calibration, and portfolio-aware
exposure analytics.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from typing import Any

from services.knowledge import INFLATION_PASSTHROUGH


_REGIONS = ("US", "EU", "India", "China")

_REGION_SYMBOL_WEIGHTS: dict[str, dict[str, float]] = {
    # Relative exposure of consumer baskets by region.
    "US": {
        "CL=F": 1.00, "BZ=F": 0.60, "NG=F": 1.00, "HO=F": 0.85,
        "ZW=F": 0.75, "ZC=F": 0.85, "ZS=F": 0.75, "KC=F": 0.55, "SB=F": 0.60,
        "CT=F": 0.35, "HG=F": 0.30, "SI=F": 0.20,
    },
    "EU": {
        "CL=F": 1.10, "BZ=F": 1.20, "NG=F": 1.15, "HO=F": 0.95,
        "ZW=F": 0.85, "ZC=F": 0.75, "ZS=F": 0.70, "KC=F": 0.55, "SB=F": 0.60,
        "CT=F": 0.30, "HG=F": 0.40, "SI=F": 0.20,
    },
    "India": {
        "CL=F": 1.25, "BZ=F": 1.25, "NG=F": 0.85, "HO=F": 0.90,
        "ZW=F": 1.25, "ZC=F": 1.10, "ZS=F": 1.05, "KC=F": 0.75, "SB=F": 0.75,
        "CT=F": 0.70, "HG=F": 0.45, "SI=F": 0.20,
    },
    "China": {
        "CL=F": 0.90, "BZ=F": 1.00, "NG=F": 0.80, "HO=F": 0.60,
        "ZW=F": 0.65, "ZC=F": 0.70, "ZS=F": 0.85, "KC=F": 0.35, "SB=F": 0.45,
        "CT=F": 0.55, "HG=F": 0.90, "SI=F": 0.20,
    },
}

_SYMBOL_LABELS = {
    "CL=F": "WTI Oil",
    "BZ=F": "Brent Oil",
    "NG=F": "Natural Gas",
    "HO=F": "Heating Oil",
    "ZW=F": "Wheat",
    "ZC=F": "Corn",
    "ZS=F": "Soybeans",
    "KC=F": "Coffee",
    "SB=F": "Sugar",
    "CT=F": "Cotton",
    "HG=F": "Copper",
    "GC=F": "Gold",
    "SI=F": "Silver",
}

_CPI_SERIES = {
    "US": "CPIAUCSL",
    "EU": "CP0000EZ19M086NEST",
    "India": "INDCPIALLMINMEI",
    "China": "CHNCPIALLMINMEI",
}

_HEDGE_UNIVERSE: dict[str, str] = {
    "TIP": "US TIPS ETF",
    "XLP": "Consumer Staples ETF",
    "XLU": "Utilities ETF",
    "GLD": "Gold ETF",
    "UUP": "USD Bull ETF",
    "DBA": "Agriculture ETF",
    "USO": "US Oil ETF",
}

_CALIBRATION_TTL = 21600  # 6h
_calibration_cache: dict[str, Any] = {}
_calibration_ts: float = 0.0
_calibration_lock = threading.Lock()

_MARKET_CACHE_TTL = 21600  # 6h
_market_cache: dict[str, Any] = {}
_market_cache_ts: float = 0.0
_market_cache_lock = threading.Lock()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _month_key(date_like: Any) -> str:
    """Normalize datetime/date strings to YYYY-MM keys for alignment."""
    s = str(date_like)
    if len(s) >= 7:
        return s[:7]
    return s


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _regress_scale(x_vals: list[float], y_vals: list[float]) -> tuple[float, float | None]:
    import numpy as np

    if len(x_vals) < 12:
        return 1.0, None

    x = np.asarray(x_vals, dtype=float)
    y = np.asarray(y_vals, dtype=float)
    var = float(np.var(x))
    if var < 1e-12:
        return 1.0, None
    cov = float(np.cov(x, y)[0, 1])
    beta = cov / var
    alpha = float(np.mean(y) - beta * np.mean(x))
    pred = alpha + beta * x
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = None if ss_tot < 1e-12 else max(0.0, 1.0 - ss_res / ss_tot)
    return _clamp(beta, 0.5, 1.6), r2


def _fetch_cpi_monthly_changes() -> dict[str, list[tuple[str, float]]]:
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        return {}

    import httpx

    out: dict[str, list[tuple[str, float]]] = {}
    for region, series_id in _CPI_SERIES.items():
        try:
            resp = httpx.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "sort_order": "asc",
                    "limit": 180,
                },
                timeout=12,
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            points: list[tuple[str, float]] = []
            for row in obs:
                raw = row.get("value", ".")
                if raw == ".":
                    continue
                points.append((_month_key(row.get("date", "")), float(raw)))
            if len(points) < 20:
                continue
            changes: list[tuple[str, float]] = []
            for i in range(1, len(points)):
                prev = points[i - 1][1]
                curr = points[i][1]
                if prev == 0:
                    continue
                mm = (curr / prev - 1.0) * 100.0
                changes.append((points[i][0], mm))
            out[region] = changes
        except Exception:
            continue
    return out


def _fetch_monthly_commodity_deltas(symbols: list[str]) -> dict[str, list[tuple[str, float]]]:
    import yfinance as yf

    if not symbols:
        return {}
    try:
        df = yf.download(
            symbols,
            period="10y",
            interval="1mo",
            progress=False,
            auto_adjust=False,
            threads=True,
        )
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    out: dict[str, list[tuple[str, float]]] = {}
    try:
        closes = df["Close"]
    except Exception:
        return {}

    for sym in symbols:
        try:
            if sym not in closes:
                continue
            series = closes[sym].dropna()
            if len(series) < 20:
                continue
            points: list[tuple[str, float]] = []
            idx = list(series.index)
            vals = [float(v) for v in series.values]
            for i in range(1, len(vals)):
                delta = vals[i] - vals[i - 1]
                points.append((_month_key(idx[i]), delta))
            out[sym] = points
        except Exception:
            continue
    return out


def _build_lagged_pressure_series(
    region: str,
    commodity_deltas: dict[str, list[tuple[str, float]]],
) -> dict[str, float]:
    monthly_pressure: dict[str, float] = {}
    weights = _REGION_SYMBOL_WEIGHTS.get(region, {})

    for sym, points in commodity_deltas.items():
        pt = INFLATION_PASSTHROUGH.get(sym)
        if not pt:
            continue
        coef = float(pt.get("cpi_impact_per_dollar", 0.0) or 0.0)
        lag = max(int(pt.get("lag_months", 1) or 1), 1)
        if coef == 0.0:
            continue
        weight = float(weights.get(sym, 0.0))
        if weight == 0.0:
            continue
        for i in range(lag, len(points)):
            target_month = points[i][0]
            source_delta = points[i - lag][1]
            monthly_pressure[target_month] = monthly_pressure.get(target_month, 0.0) + (
                coef * weight * source_delta
            )
    return monthly_pressure


def _tracker_metrics(months: list[str], x_vals: list[float], y_vals: list[float], scale: float) -> dict[str, Any]:
    if not x_vals or not y_vals or len(x_vals) != len(y_vals):
        return {
            "samples": 0,
            "mae_pp": None,
            "bias_pp": None,
            "hit_rate": None,
            "latest_month": None,
            "latest_forecast_mm": None,
            "latest_actual_mm": None,
        }

    errors = []
    hits = 0
    for x, y in zip(x_vals, y_vals):
        pred = scale * x
        errors.append(pred - y)
        if abs(y) < 0.02:
            hits += int(abs(pred) < 0.08)
        else:
            hits += int((pred >= 0) == (y >= 0))

    mae = sum(abs(e) for e in errors) / len(errors)
    bias = sum(errors) / len(errors)

    latest_m = months[-1] if months else None
    latest_pred = scale * x_vals[-1]
    latest_actual = y_vals[-1]
    return {
        "samples": len(errors),
        "mae_pp": round(mae, 3),
        "bias_pp": round(bias, 3),
        "hit_rate": round(hits / len(errors), 3),
        "latest_month": latest_m,
        "latest_forecast_mm": round(latest_pred, 3),
        "latest_actual_mm": round(latest_actual, 3),
    }


def _compute_calibration() -> dict[str, dict[str, Any]]:
    symbols = sorted(
        {
            sym
            for weights in _REGION_SYMBOL_WEIGHTS.values()
            for sym in weights.keys()
            if sym in INFLATION_PASSTHROUGH
        }
    )
    cpi = _fetch_cpi_monthly_changes()
    deltas = _fetch_monthly_commodity_deltas(symbols)
    if not cpi or not deltas:
        return {
            r: {
                "scale": 1.0,
                "r2": None,
                "auto_factor": 1.0,
                "tracker": _tracker_metrics([], [], [], 1.0),
            }
            for r in _REGIONS
        }

    out: dict[str, dict[str, Any]] = {}
    for region in _REGIONS:
        cpi_points = cpi.get(region, [])
        if not cpi_points:
            out[region] = {
                "scale": 1.0,
                "r2": None,
                "auto_factor": 1.0,
                "tracker": _tracker_metrics([], [], [], 1.0),
            }
            continue

        pressure = _build_lagged_pressure_series(region, deltas)
        x_vals: list[float] = []
        y_vals: list[float] = []
        months: list[str] = []
        for month_s, mm in cpi_points:
            if month_s in pressure:
                months.append(month_s)
                x_vals.append(pressure[month_s])
                y_vals.append(mm)

        scale, r2 = _regress_scale(x_vals, y_vals)
        tracker = _tracker_metrics(months, x_vals, y_vals, scale)

        # Auto-calibration factor based on persistent forecast bias.
        bias = tracker.get("bias_pp")
        if bias is None:
            auto_factor = 1.0
        else:
            # Positive bias means model tends to over-forecast CPI pressure.
            auto_factor = _clamp(1.0 - (float(bias) / 2.0), 0.8, 1.2)

        out[region] = {
            "scale": scale,
            "r2": r2,
            "auto_factor": auto_factor,
            "tracker": tracker,
        }
    return out


def _get_calibration() -> dict[str, dict[str, Any]]:
    global _calibration_ts, _calibration_cache
    with _calibration_lock:
        if _calibration_cache and (time.time() - _calibration_ts) < _CALIBRATION_TTL:
            return _calibration_cache

    calibration = _compute_calibration()
    with _calibration_lock:
        _calibration_cache = calibration
        _calibration_ts = time.time()
    return calibration


def _driver_text(sym: str, delta_1m: float, contribution_pp: float) -> str:
    label = _SYMBOL_LABELS.get(sym, sym)
    sign = "+" if delta_1m >= 0 else ""
    return f"{label} {sign}{delta_1m:.2f} -> {contribution_pp:+.3f}pp"


def _pressure_index(h3_pp: float) -> tuple[int, str]:
    score = int(round(_clamp(50.0 + (h3_pp * 80.0), 5.0, 95.0)))
    if score >= 72:
        label = "high"
    elif score >= 58:
        label = "elevated"
    elif score >= 42:
        label = "balanced"
    else:
        label = "cooling"
    return score, label


def _quality_badge(coverage: float, freshness_ratio: float) -> tuple[str, str]:
    # Returns (badge, reason)
    if coverage >= 0.8 and freshness_ratio >= 0.8:
        return "good", "high coverage"
    if coverage >= 0.55 and freshness_ratio >= 0.5:
        return "caution", "partial coverage"
    return "poor", "sparse or stale data"


def _load_event_overrides() -> list[dict[str, Any]]:
    path = os.path.join("data", "macro_event_overrides.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        events = payload.get("events", [])
        if isinstance(events, list):
            return [e for e in events if isinstance(e, dict)]
    except Exception:
        return []
    return []


def _event_context(commodity_data: dict[str, dict]) -> dict[str, Any]:
    month = datetime.now().month
    multipliers: dict[str, float] = {}
    active: list[str] = []

    def _bump(symbols: list[str], mult: float, label: str) -> None:
        for s in symbols:
            multipliers[s] = multipliers.get(s, 1.0) * mult
        active.append(label)

    # Seasonal demand sensitivity.
    if month in (5, 6, 7, 8):
        _bump(["CL=F", "BZ=F", "HO=F"], 1.08, "US driving season (energy pass-through +8%)")
    if month in (11, 12, 1, 2):
        _bump(["NG=F", "HO=F"], 1.10, "winter heating season (gas/heating +10%)")

    # Shock-based adjustments from current tape.
    oil_shock = max(
        abs(_safe_float((commodity_data.get("CL=F") or {}).get("pct_1d"), 0.0)),
        abs(_safe_float((commodity_data.get("BZ=F") or {}).get("pct_1d"), 0.0)),
    )
    if oil_shock >= 3.0:
        _bump(["CL=F", "BZ=F", "HO=F", "NG=F"], 1.07, "shipping/energy shock state (+7%)")

    agri_shock = max(
        abs(_safe_float((commodity_data.get("ZW=F") or {}).get("pct_1d"), 0.0)),
        abs(_safe_float((commodity_data.get("ZC=F") or {}).get("pct_1d"), 0.0)),
        abs(_safe_float((commodity_data.get("ZS=F") or {}).get("pct_1d"), 0.0)),
    )
    if agri_shock >= 2.0 and month in (3, 4, 5, 8, 9, 10):
        _bump(["ZW=F", "ZC=F", "ZS=F"], 1.09, "weather/crop stress state (+9%)")

    copper_shock = abs(_safe_float((commodity_data.get("HG=F") or {}).get("pct_1d"), 0.0))
    if copper_shock >= 2.5:
        _bump(["HG=F", "ALI=F"], 1.05, "industrial cycle acceleration (+5%)")

    # Manual event overrides allow precise real-world events (OPEC, Fed, strikes, etc.).
    for evt in _load_event_overrides():
        try:
            name = str(evt.get("name", "manual event")).strip() or "manual event"
            sym_list = evt.get("symbols", [])
            if not isinstance(sym_list, list):
                continue
            mult = _safe_float(evt.get("multiplier"), 1.0)
            if mult <= 0:
                continue
            note = str(evt.get("note", "")).strip()
            label = f"{name} ({note})" if note else name
            _bump([str(s) for s in sym_list], mult, label)
        except Exception:
            continue

    for sym in list(multipliers.keys()):
        multipliers[sym] = _clamp(multipliers[sym], 0.85, 1.25)

    return {
        "active": active,
        "multipliers": multipliers,
    }


def _download_monthly_returns(symbols: list[str]) -> dict[str, dict[str, float]]:
    import yfinance as yf

    cleaned = [s for s in symbols if s]
    if not cleaned:
        return {}
    try:
        df = yf.download(
            cleaned,
            period="5y",
            interval="1mo",
            progress=False,
            auto_adjust=True,
            threads=True,
        )
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    try:
        closes = df["Close"]
    except Exception:
        return {}

    out: dict[str, dict[str, float]] = {}
    for sym in cleaned:
        try:
            if sym not in closes:
                continue
            series = closes[sym].dropna()
            if len(series) < 14:
                continue
            ret_map: dict[str, float] = {}
            vals = [float(v) for v in series.values]
            idx = list(series.index)
            for i in range(1, len(vals)):
                prev = vals[i - 1]
                if prev == 0:
                    continue
                r = (vals[i] / prev - 1.0) * 100.0
                ret_map[_month_key(idx[i])] = r
            if ret_map:
                out[sym] = ret_map
        except Exception:
            continue
    return out


def _get_market_returns(symbols: list[str]) -> dict[str, dict[str, float]]:
    global _market_cache, _market_cache_ts
    key = tuple(sorted(set(symbols)))
    with _market_cache_lock:
        if (
            _market_cache
            and _market_cache.get("key") == key
            and (time.time() - _market_cache_ts) < _MARKET_CACHE_TTL
        ):
            return _market_cache.get("data", {})

    data = _download_monthly_returns(list(key))
    with _market_cache_lock:
        _market_cache = {"key": key, "data": data}
        _market_cache_ts = time.time()
    return data


def _cov_beta(x_vals: list[float], y_vals: list[float]) -> float | None:
    import numpy as np

    if len(x_vals) < 12 or len(y_vals) != len(x_vals):
        return None
    x = np.asarray(x_vals, dtype=float)
    y = np.asarray(y_vals, dtype=float)
    var = float(np.var(y))
    if var < 1e-12:
        return None
    cov = float(np.cov(x, y)[0, 1])
    return cov / var


def _portfolio_weights(portfolio: list[dict]) -> tuple[dict[str, float], float]:
    values: dict[str, float] = {}
    total = 0.0
    for row in portfolio:
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        qty = _safe_float(row.get("qty"), 0.0)
        avg_cost = _safe_float(row.get("avg_cost"), 0.0)
        if qty <= 0 or avg_cost <= 0:
            continue
        value = qty * avg_cost
        values[ticker] = values.get(ticker, 0.0) + value
        total += value
    if total <= 0:
        return {}, 0.0
    return {t: v / total for t, v in values.items()}, total


def _factor_weights() -> dict[str, float]:
    # Use average regional exposure * pass-through coefficient.
    avg_w: dict[str, float] = {}
    for region in _REGIONS:
        for sym, w in _REGION_SYMBOL_WEIGHTS.get(region, {}).items():
            avg_w[sym] = avg_w.get(sym, 0.0) + float(w)
    for sym in list(avg_w.keys()):
        avg_w[sym] = avg_w[sym] / len(_REGIONS)
        coef = _safe_float((INFLATION_PASSTHROUGH.get(sym) or {}).get("cpi_impact_per_dollar"), 0.0)
        avg_w[sym] *= coef
    return {k: v for k, v in avg_w.items() if abs(v) > 0}


def _build_inflation_factor_series(ret_map: dict[str, dict[str, float]]) -> dict[str, float]:
    fw = _factor_weights()
    factor: dict[str, float] = {}
    for sym, w in fw.items():
        series = ret_map.get(sym, {})
        for month_s, r in series.items():
            factor[month_s] = factor.get(month_s, 0.0) + (w * r)
    return factor


def _compute_portfolio_exposure(portfolio: list[dict]) -> dict[str, Any] | None:
    if not portfolio:
        return None

    w_map, total_value = _portfolio_weights(portfolio)
    if not w_map or total_value <= 0:
        return None

    symbols = list(w_map.keys()) + list(_factor_weights().keys()) + list(_HEDGE_UNIVERSE.keys())
    ret_map = _get_market_returns(symbols)
    factor = _build_inflation_factor_series(ret_map)
    if not factor:
        return None

    # Per-holding inflation beta.
    holding_betas: dict[str, float] = {}
    for ticker in w_map:
        series = ret_map.get(ticker, {})
        common = sorted(set(series.keys()) & set(factor.keys()))
        x_vals = [series[m] for m in common]
        y_vals = [factor[m] for m in common]
        beta = _cov_beta(x_vals, y_vals)
        if beta is not None:
            holding_betas[ticker] = beta

    if not holding_betas:
        return None

    weighted_beta = 0.0
    contrib_rows: list[tuple[str, float, float, float]] = []
    for ticker, beta in holding_betas.items():
        wt = w_map.get(ticker, 0.0)
        c = wt * beta
        weighted_beta += c
        contrib_rows.append((ticker, wt, beta, c))

    contrib_rows.sort(key=lambda x: abs(x[3]), reverse=True)
    top = [
        f"{t}: weight {w * 100:.1f}% x beta {b:+.2f} = {c:+.3f}"
        for t, w, b, c in contrib_rows[:4]
    ]

    score = int(round(_clamp(50.0 + weighted_beta * 28.0, 0.0, 100.0)))
    if score >= 68:
        regime = "inflation-sensitive"
    elif score >= 55:
        regime = "moderately inflation-sensitive"
    elif score >= 45:
        regime = "balanced"
    else:
        regime = "inflation-defensive"

    # Build synthetic portfolio return series for hedge optimization.
    common_months = sorted(set.intersection(*[
        set(ret_map.get(t, {}).keys()) for t in holding_betas.keys()
    ])) if holding_betas else []
    if not common_months:
        # fall back to factor overlap
        common_months = sorted(set(factor.keys()))
    port_series: dict[str, float] = {}
    for m in common_months:
        val = 0.0
        used = 0
        for ticker, wt in w_map.items():
            rs = ret_map.get(ticker, {})
            if m in rs:
                val += wt * rs[m]
                used += 1
        if used >= 1:
            port_series[m] = val

    hedges: list[dict[str, Any]] = []
    p_months = set(port_series.keys())
    for sym, name in _HEDGE_UNIVERSE.items():
        hs = ret_map.get(sym, {})
        common = sorted(p_months & set(hs.keys()))
        if len(common) < 12:
            continue
        p = [port_series[m] for m in common]
        h = [hs[m] for m in common]
        beta = _cov_beta(p, h)
        if beta is None:
            continue
        try:
            import numpy as np

            p_arr = np.asarray(p, dtype=float)
            h_arr = np.asarray(h, dtype=float)
            # Minimum variance hedge with linear exposure.
            hedged = p_arr - (beta * h_arr)
            var_p = float(np.var(p_arr))
            var_h = float(np.var(hedged))
            if var_p < 1e-12:
                continue
            reduction = (1.0 - (var_h / var_p)) * 100.0
            if reduction <= 0.5:
                continue
            hedges.append(
                {
                    "symbol": sym,
                    "name": name,
                    "direction": "short/underweight" if beta > 0 else "long",
                    "hedge_ratio": round(abs(beta), 2),
                    "estimated_risk_reduction_pct": round(min(reduction, 80.0), 1),
                }
            )
        except Exception:
            continue

    hedges.sort(key=lambda x: x["estimated_risk_reduction_pct"], reverse=True)

    return {
        "score": score,
        "regime": regime,
        "beta": round(weighted_beta, 3),
        "top_contributors": top,
        "sample_months": len(common_months),
        "hedge_candidates": hedges[:4],
    }


def estimate_consumer_inflation_nowcast(
    commodity_data: dict[str, dict],
    portfolio: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Return region-level CPI pressure nowcasts with extended analytics.

    Backward compatibility:
      direct keys "US"/"EU"/"India"/"China" are still present.
    New keys:
      regions, aggregate, portfolio_exposure, hedge_assistant, event_context, data_quality
    """
    calibration = _get_calibration()
    event_ctx = _event_context(commodity_data)
    event_mult = event_ctx.get("multipliers", {})
    region_results: dict[str, dict[str, Any]] = {}

    expected_union = {
        s for r in _REGIONS for s in _REGION_SYMBOL_WEIGHTS.get(r, {}).keys()
        if s in INFLATION_PASSTHROUGH
    }
    avail_union = {
        s for s in expected_union
        if (commodity_data.get(s) or {}).get("delta_1m") is not None
    }
    global_cov = len(avail_union) / max(1, len(expected_union))
    stale_union = 0
    fresh_union = 0
    now_ts = time.time()
    for s in avail_union:
        ts = _safe_float((commodity_data.get(s) or {}).get("fetched_ts"), 0.0)
        if ts > 0:
            age_h = (now_ts - ts) / 3600.0
            if age_h > 4:
                stale_union += 1
            else:
                fresh_union += 1
        else:
            # If no timestamp provided, treat as fresh because fetch just occurred.
            fresh_union += 1
    global_freshness = fresh_union / max(1, fresh_union + stale_union)
    global_badge, global_reason = _quality_badge(global_cov, global_freshness)

    for region in _REGIONS:
        weights = _REGION_SYMBOL_WEIGHTS.get(region, {})
        cal = calibration.get(region) or {}
        base_scale = _safe_float(cal.get("scale"), 1.0)
        auto_factor = _safe_float(cal.get("auto_factor"), 1.0)
        applied_scale = base_scale * auto_factor
        r2_val = cal.get("r2")
        tracker = cal.get("tracker") or {}

        h1 = 0.0
        h3 = 0.0
        h6 = 0.0
        drivers: list[tuple[str, float, float]] = []
        vol_samples: list[float] = []

        expected = 0
        available = 0
        missing_symbols: list[str] = []
        stale_count = 0
        fresh_count = 0

        for sym, weight in weights.items():
            pt = INFLATION_PASSTHROUGH.get(sym)
            if not pt:
                continue
            expected += 1
            info = commodity_data.get(sym) or {}
            delta_1m = info.get("delta_1m")
            if delta_1m is None:
                missing_symbols.append(sym)
                continue
            available += 1

            coef = _safe_float(pt.get("cpi_impact_per_dollar"), 0.0)
            lag = max(int(pt.get("lag_months", 1) or 1), 1)
            evt = _safe_float(event_mult.get(sym), 1.0)
            total = coef * float(weight) * float(delta_1m) * applied_scale * evt
            h1 += total * min(1.0 / lag, 1.0)
            h3 += total * min(3.0 / lag, 1.0)
            h6 += total * min(6.0 / lag, 1.0)
            if abs(total) > 1e-8:
                drivers.append((sym, float(delta_1m), total))

            vol = info.get("vol_1m")
            if vol is not None:
                vol_samples.append(abs(float(vol)))

            ts = _safe_float(info.get("fetched_ts"), 0.0)
            if ts > 0 and (now_ts - ts) > (4 * 3600):
                stale_count += 1
            else:
                fresh_count += 1

        drivers.sort(key=lambda x: abs(x[2]), reverse=True)
        top_drivers = [_driver_text(sym, dlt, contr) for sym, dlt, contr in drivers[:3]]
        p_index, p_label = _pressure_index(h3)

        coverage = available / max(1, expected)
        freshness_ratio = fresh_count / max(1, fresh_count + stale_count)
        quality_badge, quality_reason = _quality_badge(coverage, freshness_ratio)

        # Confidence score combines model quality, stability, tracker accuracy, and data quality.
        confidence = 0.50
        if r2_val is not None:
            confidence += _clamp(float(r2_val), 0.0, 1.0) * 0.23
        if len(drivers) >= 4:
            confidence += 0.06
        if vol_samples:
            avg_vol = sum(vol_samples) / len(vol_samples)
            if avg_vol > 6.0:
                confidence -= 0.05
            elif avg_vol < 3.0:
                confidence += 0.03
        mae = tracker.get("mae_pp")
        if mae is not None:
            if float(mae) <= 0.18:
                confidence += 0.06
            elif float(mae) >= 0.40:
                confidence -= 0.06
        if quality_badge == "good":
            confidence += 0.04
        elif quality_badge == "poor":
            confidence -= 0.10
        confidence = _clamp(confidence, 0.20, 0.94)

        region_results[region] = {
            "h1_pp": round(h1, 3),
            "h3_pp": round(h3, 3),
            "h6_pp": round(h6, 3),
            "confidence": round(confidence, 2),
            "model_quality": "calibrated" if r2_val is not None else "coefficient-only",
            "top_drivers": top_drivers,
            "r2": None if r2_val is None else round(float(r2_val), 3),
            "as_of": time.strftime("%Y-%m-%d"),
            "consumer_pressure_index": p_index,
            "pressure_regime": p_label,
            "forecast_tracker": tracker,
            "calibration_scale": round(base_scale, 3),
            "auto_calibration_factor": round(auto_factor, 3),
            "applied_scale": round(applied_scale, 3),
            "data_quality": {
                "badge": quality_badge,
                "reason": quality_reason,
                "coverage": round(coverage, 2),
                "missing_count": max(0, expected - available),
                "missing_symbols": missing_symbols[:6],
                "freshness_ratio": round(freshness_ratio, 2),
            },
            "event_flags": event_ctx.get("active", []),
        }

    # Aggregate global pressure index.
    if region_results:
        h1_avg = sum(v["h1_pp"] for v in region_results.values()) / len(region_results)
        h3_avg = sum(v["h3_pp"] for v in region_results.values()) / len(region_results)
        h6_avg = sum(v["h6_pp"] for v in region_results.values()) / len(region_results)
        conf_avg = sum(v["confidence"] for v in region_results.values()) / len(region_results)
    else:
        h1_avg = h3_avg = h6_avg = conf_avg = 0.0
    g_idx, g_lbl = _pressure_index(h3_avg)

    # Portfolio inflation exposure and hedge assistant.
    p_exposure = _compute_portfolio_exposure(portfolio or [])
    hedge_payload = None
    if p_exposure:
        hedge_payload = {
            "summary": (
                f"Portfolio beta {p_exposure['beta']:+.3f} to inflation factor; "
                f"{p_exposure['regime']}"
            ),
            "candidates": p_exposure.get("hedge_candidates", []),
            "sample_months": p_exposure.get("sample_months"),
        }

    payload: dict[str, Any] = {
        "regions": region_results,
        "aggregate": {
            "h1_pp": round(h1_avg, 3),
            "h3_pp": round(h3_avg, 3),
            "h6_pp": round(h6_avg, 3),
            "consumer_pressure_index": g_idx,
            "pressure_regime": g_lbl,
            "confidence": round(conf_avg, 2),
            "as_of": time.strftime("%Y-%m-%d"),
        },
        "portfolio_exposure": p_exposure,
        "hedge_assistant": hedge_payload,
        "event_context": {
            "active": event_ctx.get("active", []),
        },
        "data_quality": {
            "badge": global_badge,
            "reason": global_reason,
            "coverage": round(global_cov, 2),
            "freshness_ratio": round(global_freshness, 2),
            "available_symbols": len(avail_union),
            "expected_symbols": len(expected_union),
        },
    }

    # Backward compatibility for old callers/tests.
    for region, block in region_results.items():
        payload[region] = block
    return payload
