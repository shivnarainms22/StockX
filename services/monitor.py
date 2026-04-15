"""
StockX — Background alert monitor.
Polls watchlist tickers on a configurable interval and fires alerts via callback.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable

from gui.state import AppState
from services.notifications import notify


_EARNINGS_CHECK_INTERVAL = 3600  # 1 hour between earnings checks per ticker
_MIN_HISTORY_ROWS = 20
_PRICE_FOLLOWTHROUGH_WINDOW_SECS = 45 * 60
_MEANINGFUL_MOVE_PCT = 1.2

# Commodity futures tracked by the commodity monitor (flat list to avoid circular imports)
_COMMODITY_SYMBOLS: list[tuple[str, str]] = [
    ("WTI Crude",   "CL=F"),  ("Brent Crude", "BZ=F"),
    ("Natural Gas", "NG=F"),  ("Heating Oil", "HO=F"),
    ("Gold",        "GC=F"),  ("Silver",      "SI=F"),
    ("Platinum",    "PL=F"),  ("Palladium",   "PA=F"),
    ("Copper",      "HG=F"),  ("Aluminum",    "ALI=F"),
    ("Wheat",       "ZW=F"),  ("Corn",        "ZC=F"),
    ("Soybeans",    "ZS=F"),  ("Coffee",      "KC=F"),
    ("Sugar",       "SB=F"),  ("Cotton",      "CT=F"),
]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _price_cross_confidence(price: float, threshold: float) -> float:
    if threshold <= 0:
        return 0.5
    distance = abs(price - threshold) / threshold
    return _clamp(0.55 + min(distance * 4.0, 0.35), 0.0, 0.95)


def _rsi_confidence(rsi: float, threshold: float) -> float:
    distance = abs(rsi - threshold) / 100.0
    return _clamp(0.55 + min(distance * 2.0, 0.35), 0.0, 0.95)


def _target_confidence(price: float, target: float) -> float:
    if target <= 0:
        return 0.5
    distance = abs(price - target) / target
    closeness = _clamp((0.02 - distance) / 0.02, 0.0, 1.0)
    return _clamp(0.55 + closeness * 0.35, 0.0, 0.95)


async def run_monitor(state: AppState, show_alert: Callable[[str, str], None]) -> None:
    """Background loop: poll watchlist tickers and fire alerts on threshold breach."""
    import yfinance as yf
    from datetime import date

    # Tracks last time each condition fired: key = "TICKER|condition" -> epoch seconds
    _last_alerted: dict[str, float] = {}
    # Track whether alerts led to meaningful follow-through moves.
    # key -> (ticker, alert_type, trigger_price, trigger_ts)
    _pending_precision: dict[str, tuple[str, str, float, float]] = {}
    # Earnings cache: {ticker: (check_ts, earnings_date_str)}
    _earnings_cache: dict[str, tuple[float, str]] = {}

    while True:
        # Guard: minimum 1-minute interval to prevent CPU spin on misconfigured value
        interval_secs = max(state.alert_interval_minutes, 1) * 60
        await asyncio.sleep(interval_secs)

        now = time.time()

        for item in state.watchlist:
            ticker = item["ticker"]
            try:
                hist = yf.Ticker(ticker).history(period="1mo")
                if hist.empty:
                    continue
                price = float(hist["Close"].iloc[-1])
                # Compute RSI-14
                delta  = hist["Close"].diff()
                gains  = delta.clip(lower=0).rolling(14).mean()
                losses = (-delta.clip(upper=0)).rolling(14).mean()
                rsi    = float((100 - 100 / (1 + gains / losses)).iloc[-1])
                history_ready = len(hist) >= _MIN_HISTORY_ROWS
                base_confidence = 0.55 if history_ready else 0.45
                min_confidence = float(item.get("min_confidence", state.default_alert_confidence))
                cooldown_secs = max(
                    int(item.get("alert_cooldown_minutes", state.default_alert_cooldown_minutes)),
                    1,
                ) * 60

                # Evaluate old alerts for precision tracking once the window has elapsed.
                for pending_key, pending in list(_pending_precision.items()):
                    p_ticker, p_type, p_price, p_ts = pending
                    if p_ticker != ticker or (now - p_ts) < _PRICE_FOLLOWTHROUGH_WINDOW_SECS:
                        continue
                    move_pct = abs((price - p_price) / p_price * 100) if p_price else 0.0
                    state.record_alert_precision(p_type, move_pct >= _MEANINGFUL_MOVE_PCT)
                    _pending_precision.pop(pending_key, None)

                def _should_fire(condition_key: str) -> bool:
                    """Return True only if this condition hasn't fired within the current interval."""
                    last = _last_alerted.get(condition_key, 0.0)
                    return (now - last) >= max(interval_secs, cooldown_secs)

                def _fire(
                    condition_key: str,
                    msg: str,
                    alert_type: str = "price",
                    *,
                    confidence: float,
                ) -> None:
                    _last_alerted[condition_key] = now
                    show_alert(ticker, msg)
                    notify(f"StockX \u2014 {ticker}", msg)
                    _pending_precision[condition_key] = (ticker, alert_type, price, now)
                    try:
                        state.save_alert(
                            ticker,
                            alert_type,
                            msg,
                            confidence=round(confidence, 2),
                            price=price,
                        )
                    except Exception:
                        pass

                if item.get("price_above") and price >= item["price_above"]:
                    confidence = _clamp(
                        base_confidence + (_price_cross_confidence(price, item["price_above"]) - 0.55),
                        0.0,
                        0.95,
                    )
                    key = f"{ticker}|price_above"
                    if _should_fire(key) and confidence >= min_confidence:
                        _fire(
                            key,
                            f"{ticker} price ${price:.2f} \u2265 alert ${item['price_above']}",
                            "price_above",
                            confidence=confidence,
                        )

                if item.get("price_below") and price <= item["price_below"]:
                    confidence = _clamp(
                        base_confidence + (_price_cross_confidence(price, item["price_below"]) - 0.55),
                        0.0,
                        0.95,
                    )
                    key = f"{ticker}|price_below"
                    if _should_fire(key) and confidence >= min_confidence:
                        _fire(
                            key,
                            f"{ticker} price ${price:.2f} \u2264 alert ${item['price_below']}",
                            "price_below",
                            confidence=confidence,
                        )

                if item.get("rsi_above") and rsi >= item["rsi_above"]:
                    confidence = _clamp(
                        base_confidence + (_rsi_confidence(rsi, item["rsi_above"]) - 0.55),
                        0.0,
                        0.95,
                    )
                    key = f"{ticker}|rsi_above"
                    if _should_fire(key) and confidence >= min_confidence:
                        _fire(
                            key,
                            f"{ticker} RSI {rsi:.1f} \u2265 alert {item['rsi_above']}",
                            "rsi_above",
                            confidence=confidence,
                        )

                if item.get("rsi_below") and rsi <= item["rsi_below"]:
                    confidence = _clamp(
                        base_confidence + (_rsi_confidence(rsi, item["rsi_below"]) - 0.55),
                        0.0,
                        0.95,
                    )
                    key = f"{ticker}|rsi_below"
                    if _should_fire(key) and confidence >= min_confidence:
                        _fire(
                            key,
                            f"{ticker} RSI {rsi:.1f} \u2264 alert {item['rsi_below']}",
                            "rsi_below",
                            confidence=confidence,
                        )

                # ── Price target proximity alerts (item 13) ────────────────
                buy_target  = item.get("buy_target")
                sell_target = item.get("sell_target")
                if buy_target and price > 0:
                    if abs(price - buy_target) / buy_target <= 0.02:
                        confidence = _clamp(
                            base_confidence + (_target_confidence(price, buy_target) - 0.55),
                            0.0,
                            0.95,
                        )
                        key = f"{ticker}|buy_target"
                        if _should_fire(key) and confidence >= min_confidence:
                            _fire(
                                key,
                                f"{ticker} near buy target ${buy_target:.2f} (current ${price:.2f})",
                                "buy_target",
                                confidence=confidence,
                            )
                if sell_target and price > 0:
                    if abs(price - sell_target) / sell_target <= 0.02:
                        confidence = _clamp(
                            base_confidence + (_target_confidence(price, sell_target) - 0.55),
                            0.0,
                            0.95,
                        )
                        key = f"{ticker}|sell_target"
                        if _should_fire(key) and confidence >= min_confidence:
                            _fire(
                                key,
                                f"{ticker} near sell target ${sell_target:.2f} (current ${price:.2f})",
                                "sell_target",
                                confidence=confidence,
                            )

                # ── Earnings proximity alerts (item 14) ───────────────────
                cached_ts, cached_ed = _earnings_cache.get(ticker, (0.0, ""))
                if now - cached_ts >= _EARNINGS_CHECK_INTERVAL:
                    try:
                        cal = yf.Ticker(ticker).calendar
                        earnings_date_str = ""
                        if cal is not None and isinstance(cal, dict):
                            ed = cal.get("Earnings Date") or cal.get("earningsDate")
                            if ed and hasattr(ed, "__getitem__"):
                                earnings_date_str = str(ed[0])[:10]
                            elif ed:
                                earnings_date_str = str(ed)[:10]
                        _earnings_cache[ticker] = (now, earnings_date_str)
                    except Exception:
                        _earnings_cache[ticker] = (now, "")
                        earnings_date_str = ""
                else:
                    earnings_date_str = cached_ed

                if earnings_date_str and earnings_date_str != "N/A":
                    try:
                        from datetime import datetime as _dt
                        ed_date = _dt.strptime(earnings_date_str, "%Y-%m-%d").date()
                        days_until = (ed_date - date.today()).days
                        if 0 <= days_until <= 3:
                            key = f"{ticker}|earnings|{earnings_date_str}"
                            if key not in _last_alerted:
                                msg = f"{ticker} earnings in {days_until} day(s): {earnings_date_str}"
                                _last_alerted[key] = now
                                show_alert(ticker, msg)
                                notify(f"StockX \u2014 {ticker}", msg)
                                try:
                                    state.save_alert(
                                        ticker,
                                        "earnings",
                                        msg,
                                        confidence=_clamp(base_confidence, 0.0, 0.95),
                                        price=price,
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass

            except Exception:
                continue


async def run_commodity_monitor(state: AppState, show_alert: Callable[[str, str], None]) -> None:
    """Background loop: poll commodity futures and fire alerts on significant daily moves."""
    import yfinance as yf
    from datetime import date

    _last_alerted: dict[str, float] = {}

    while True:
        interval_secs = max(state.alert_interval_minutes, 1) * 60
        await asyncio.sleep(interval_secs)

        if not state.commodity_alert_enabled:
            continue

        now = time.time()
        threshold = state.commodity_alert_threshold

        for name, symbol in _COMMODITY_SYMBOLS:
            try:
                hist = yf.Ticker(symbol).history(period="2d")
                if hist is None or len(hist) < 2:
                    continue
                prev = float(hist["Close"].iloc[-2])
                curr = float(hist["Close"].iloc[-1])
                if prev == 0:
                    continue
                pct = (curr - prev) / prev * 100

                if abs(pct) >= threshold:
                    key = f"{symbol}|commodity|{date.today().isoformat()}"
                    if key in _last_alerted:
                        continue
                    _last_alerted[key] = now

                    sign = "+" if pct >= 0 else ""
                    msg = f"{name} ({symbol}) moved {sign}{pct:.1f}% today"

                    # Check if any portfolio holdings are affected
                    portfolio_tickers = {h["ticker"] for h in state.portfolio}
                    # Inline sector map for monitor (avoids importing from gui)
                    _AFFECTED: dict[str, list[str]] = {
                        "CL=F": ["XLE", "CVX", "XOM", "COP", "OXY", "JETS", "DAL"],
                        "BZ=F": ["XLE", "CVX", "XOM", "BP", "SHEL"],
                        "NG=F": ["UNG", "LNG", "AR", "EQT", "MOS", "NTR"],
                        "GC=F": ["GLD", "GDX", "NEM", "GOLD"],
                        "HG=F": ["FCX", "SCCO", "TECK"],
                        "ZW=F": ["ADM", "BG", "DE"],
                    }
                    affected = _AFFECTED.get(symbol, [])
                    matches = [t for t in affected if t in portfolio_tickers]
                    if matches:
                        msg += f" -- your holdings: {', '.join(matches)}"

                    show_alert(symbol, msg)
                    notify(f"StockX \u2014 {name}", msg)
                    try:
                        state.save_alert(symbol, "commodity_move", msg)
                    except Exception:
                        pass

            except Exception:
                continue
