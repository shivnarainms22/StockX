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


async def run_monitor(state: AppState, show_alert: Callable[[str, str], None]) -> None:
    """Background loop: poll watchlist tickers and fire alerts on threshold breach."""
    import yfinance as yf
    from datetime import date

    # Tracks last time each condition fired: key = "TICKER|condition" -> epoch seconds
    _last_alerted: dict[str, float] = {}
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

                def _should_fire(condition_key: str) -> bool:
                    """Return True only if this condition hasn't fired within the current interval."""
                    last = _last_alerted.get(condition_key, 0.0)
                    return (now - last) >= interval_secs

                def _fire(condition_key: str, msg: str, alert_type: str = "price") -> None:
                    _last_alerted[condition_key] = now
                    show_alert(ticker, msg)
                    notify(f"StockX \u2014 {ticker}", msg)
                    try:
                        state.save_alert(ticker, alert_type, msg)
                    except Exception:
                        pass

                if item.get("price_above") and price >= item["price_above"]:
                    key = f"{ticker}|price_above"
                    if _should_fire(key):
                        _fire(key, f"{ticker} price ${price:.2f} \u2265 alert ${item['price_above']}", "price_above")

                if item.get("price_below") and price <= item["price_below"]:
                    key = f"{ticker}|price_below"
                    if _should_fire(key):
                        _fire(key, f"{ticker} price ${price:.2f} \u2264 alert ${item['price_below']}", "price_below")

                if item.get("rsi_above") and rsi >= item["rsi_above"]:
                    key = f"{ticker}|rsi_above"
                    if _should_fire(key):
                        _fire(key, f"{ticker} RSI {rsi:.1f} \u2265 alert {item['rsi_above']}", "rsi_above")

                if item.get("rsi_below") and rsi <= item["rsi_below"]:
                    key = f"{ticker}|rsi_below"
                    if _should_fire(key):
                        _fire(key, f"{ticker} RSI {rsi:.1f} \u2264 alert {item['rsi_below']}", "rsi_below")

                # ── Price target proximity alerts (item 13) ────────────────
                buy_target  = item.get("buy_target")
                sell_target = item.get("sell_target")
                if buy_target and price > 0:
                    if abs(price - buy_target) / buy_target <= 0.02:
                        key = f"{ticker}|buy_target"
                        if _should_fire(key):
                            _fire(key, f"{ticker} near buy target ${buy_target:.2f} (current ${price:.2f})", "buy_target")
                if sell_target and price > 0:
                    if abs(price - sell_target) / sell_target <= 0.02:
                        key = f"{ticker}|sell_target"
                        if _should_fire(key):
                            _fire(key, f"{ticker} near sell target ${sell_target:.2f} (current ${price:.2f})", "sell_target")

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
                                    state.save_alert(ticker, "earnings", msg)
                                except Exception:
                                    pass
                    except Exception:
                        pass

            except Exception:
                continue
