"""
StockX GUI — Watchlist view (PyQt6).
Track tickers with optional price/RSI alert thresholds. Persists to data/watchlist.json.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, APP_BG, BORDER_CARD, BORDER_INPUT, BORDER_SUBTLE,
    NEGATIVE, POSITIVE, SURFACE_1, SURFACE_2, SURFACE_3, TEXT_1, TEXT_2, TEXT_MUTED, fmt_price,
)

if TYPE_CHECKING:
    from gui.app import MainWindow


# ── WatchlistView ─────────────────────────────────────────────────────────────

class WatchlistView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw    = main_window
        self._live: dict[str, dict] = {}
        self._sparklines: dict[str, bytes] = {}   # item 7
        self._alert_panel_visible = False
        self._setup_ui()
        self._build_rows()

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        # Main content area: rows + optional alert panel side-by-side
        content = QWidget()
        content_h = QHBoxLayout(content)
        content_h.setContentsMargins(0, 0, 0, 0)
        content_h.setSpacing(0)

        # Scroll area for list rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._rows_layout.setContentsMargins(32, 8, 32, 16)
        self._rows_layout.setSpacing(2)

        scroll.setWidget(self._rows_widget)
        content_h.addWidget(scroll, stretch=1)

        # Alert history panel — hidden by default
        self._alert_panel = self._build_alert_panel()
        content_h.addWidget(self._alert_panel)

        root.addWidget(content, stretch=1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h = QHBoxLayout(header)
        h.setContentsMargins(32, 20, 32, 8)
        h.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Watchlist")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Track tickers with price and RSI alerts")
        subtitle.setStyleSheet(f"color: {TEXT_2}; font-size: 13px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        h.addLayout(title_col)
        h.addStretch()

        self._alerts_hist_btn = QPushButton(f"Alerts ({len(self._state.alert_history)})")
        self._alerts_hist_btn.setObjectName("Chip")
        self._alerts_hist_btn.setFixedHeight(30)
        self._alerts_hist_btn.clicked.connect(self._toggle_alert_panel)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none; border-radius: 10px; padding: 6px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
        )
        self._refresh_btn.clicked.connect(
            lambda: asyncio.ensure_future(self.refresh())
        )

        add_btn = QPushButton("+ Add")
        add_btn.setObjectName("AccentBtn")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self._open_add_dialog)

        for w in [self._alerts_hist_btn, self._refresh_btn, add_btn]:
            h.addWidget(w)
        return header

    def _build_alert_panel(self) -> QFrame:
        """Side panel showing alert history (item 15)."""
        panel = QFrame()
        panel.setFixedWidth(300)
        panel.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_1}; border-left: 1px solid {BORDER_SUBTLE}; }}"
        )
        panel.setVisible(False)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE};")
        hdr.setFixedHeight(40)
        hdr_h = QHBoxLayout(hdr)
        hdr_h.setContentsMargins(10, 0, 10, 0)
        title_lbl = QLabel("Alert History")
        title_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 13px; font-weight: 600;")
        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("IconBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self._toggle_alert_panel)
        hdr_h.addWidget(title_lbl)
        hdr_h.addStretch()
        hdr_h.addWidget(close_btn)
        layout.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {SURFACE_1}; border: none; }}")

        self._alert_inner = QWidget()
        self._alert_inner.setStyleSheet(f"background-color: {SURFACE_1};")
        self._alert_layout = QVBoxLayout(self._alert_inner)
        self._alert_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._alert_layout.setContentsMargins(8, 8, 8, 8)
        self._alert_layout.setSpacing(4)

        scroll.setWidget(self._alert_inner)
        layout.addWidget(scroll, stretch=1)
        return panel

    # ── Row building ──────────────────────────────────────────────────────

    def _build_rows(self) -> None:
        # Clear existing rows
        while self._rows_layout.count():
            child = self._rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._state.watchlist:
            empty = QLabel("No tickers in watchlist. Click '+ Add' to get started.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px;")
            self._rows_layout.addWidget(empty)
            return

        for idx, item in enumerate(self._state.watchlist):
            row = self._make_row(item, idx)
            self._rows_layout.addWidget(row)

    def _make_row(self, item: dict, idx: int) -> QFrame:
        ticker = item["ticker"]
        live = self._live.get(ticker, {})
        price_str = fmt_price(live["price"], live.get("currency")) if "price" in live else "\u2014"
        rsi_val = live.get("rsi")
        rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "\u2014"
        rsi_color = NEGATIVE if (rsi_val or 50) >= 70 else (POSITIVE if (rsi_val or 50) <= 30 else TEXT_1)

        bg = SURFACE_2 if idx % 2 == 0 else SURFACE_1
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: 14px; }}"
            f"QFrame:hover {{ background-color: {SURFACE_3}; }}"
        )
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.mousePressEvent = lambda ev, t=ticker: self._mw.switch_to_analysis(f"Analyse {t}")

        h = QHBoxLayout(row)
        h.setContentsMargins(16, 14, 16, 14)
        h.setSpacing(16)

        # Avatar badge
        avatar = QLabel(ticker[:2])
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: rgba(212,168,67,0.08); border-radius: 10px;"
            f"font-size: 14px; font-weight: 700; color: {ACCENT};"
        )

        # Ticker + company
        info = QVBoxLayout()
        info.setSpacing(1)
        ticker_lbl = QLabel(ticker)
        ticker_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 14px; font-weight: 600; background: transparent;")
        info.addWidget(ticker_lbl)

        # Sparkline
        spark_lbl = QLabel()
        spark_lbl.setFixedSize(80, 32)
        spark_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spark_bytes = self._sparklines.get(ticker, b"")
        if spark_bytes:
            img = QImage.fromData(bytes(spark_bytes))
            spark_lbl.setPixmap(QPixmap.fromImage(img))
        spark_lbl.setStyleSheet("background: transparent;")

        # Price
        price_col = QVBoxLayout()
        price_col.setSpacing(1)
        price_lbl = QLabel(price_str)
        price_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 15px; font-weight: 600; background: transparent;")
        price_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        price_col.addWidget(price_lbl)

        # RSI
        rsi_frame = QVBoxLayout()
        rsi_frame.setSpacing(0)
        rsi_label_top = QLabel("RSI")
        rsi_label_top.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
        rsi_label_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rsi_val_lbl = QLabel(rsi_str)
        rsi_val_lbl.setStyleSheet(f"color: {rsi_color}; font-size: 13px; font-weight: 600; background: transparent;")
        rsi_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rsi_frame.addWidget(rsi_label_top)
        rsi_frame.addWidget(rsi_val_lbl)

        rsi_widget = QWidget()
        rsi_widget.setFixedWidth(50)
        rsi_widget.setLayout(rsi_frame)
        rsi_widget.setStyleSheet("background: transparent;")

        # Action buttons (edit/delete)
        edit_btn = QPushButton("\u270e")
        edit_btn.setObjectName("IconBtn")
        edit_btn.setFixedSize(28, 28)
        edit_btn.setToolTip("Edit alerts & targets")
        edit_btn.clicked.connect(lambda _=False, t=ticker: self._open_edit_alerts_dialog(t))

        del_btn = QPushButton("\u2715")
        del_btn.setObjectName("IconBtn")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip("Remove")
        del_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_MUTED}; background: transparent; border: none; font-size: 14px; border-radius: 6px; }}"
            f"QPushButton:hover {{ color: {NEGATIVE}; background: rgba(251,113,133,0.08); }}"
        )
        del_btn.clicked.connect(lambda _=False, t=ticker: self._remove_ticker(t))

        h.addWidget(avatar)
        h.addLayout(info, stretch=1)
        h.addWidget(spark_lbl)
        h.addLayout(price_col)
        h.addWidget(rsi_widget)
        h.addWidget(edit_btn)
        h.addWidget(del_btn)

        return row

    def _remove_ticker(self, ticker: str) -> None:
        self._state.watchlist = [x for x in self._state.watchlist if x["ticker"] != ticker]
        self._state.save_watchlist()
        self._build_rows()

    def _toggle_alert_panel(self) -> None:
        """Show/hide the alert history panel (item 15)."""
        self._alert_panel_visible = not self._alert_panel_visible
        self._alert_panel.setVisible(self._alert_panel_visible)
        if self._alert_panel_visible:
            self._refresh_alert_panel()
        count = len(self._state.alert_history)
        self._alerts_hist_btn.setText(f"Alerts ({count})")

    def _refresh_alert_panel(self) -> None:
        """Populate alert history cards."""
        while self._alert_layout.count():
            child = self._alert_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        from gui.theme import ACCENT_CYAN, NEGATIVE, POSITIVE, TEXT_MUTED
        type_colors = {
            "price_above": POSITIVE, "price_below": NEGATIVE,
            "buy_target": POSITIVE, "sell_target": NEGATIVE,
            "rsi_above": NEGATIVE, "rsi_below": POSITIVE,
            "earnings": ACCENT_CYAN,
        }
        for entry in self._state.alert_history[:50]:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {SURFACE_2}; border-radius: 8px; }}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.setSpacing(2)

            atype = entry.get("type", "price")
            dot_color = type_colors.get(atype, TEXT_MUTED)
            msg_lbl = QLabel(f"\u25cf {entry.get('message', '')}")
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet(
                f"color: {dot_color}; font-size: 11px; background: transparent; border: none;"
            )
            ts_lbl = QLabel(entry.get("ts", "")[:16].replace("T", " "))
            ts_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")

            cl.addWidget(msg_lbl)
            cl.addWidget(ts_lbl)
            self._alert_layout.addWidget(card)

        if not self._state.alert_history:
            empty = QLabel("No alerts fired yet.")
            empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; padding: 12px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._alert_layout.addWidget(empty)

    def _open_edit_alerts_dialog(self, ticker: str) -> None:
        entry = next((x for x in self._state.watchlist if x["ticker"] == ticker), None)
        if entry is None:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Alerts \u2014 {ticker}")
        dlg.setMinimumWidth(340)
        dlg.setStyleSheet("QDialog { background-color: #161618; }")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = QLabel(f"Alert Conditions for {ticker}")
        title_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 15px; font-weight: 600;")

        def _field(placeholder: str, key: str) -> QLineEdit:
            f = QLineEdit()
            f.setPlaceholderText(placeholder)
            val = entry.get(key)
            if val is not None:
                f.setText(str(val))
            return f

        f_p_above   = _field("Price Alert Above (optional)",  "price_above")
        f_p_below   = _field("Price Alert Below (optional)",  "price_below")
        f_rsi_above = _field("RSI Alert Above (optional)",    "rsi_above")
        f_rsi_below = _field("RSI Alert Below (optional)",    "rsi_below")
        f_buy_tgt   = _field("Buy Target Price (optional)",   "buy_target")
        f_sell_tgt  = _field("Sell Target Price (optional)",  "sell_target")

        error_lbl = QLabel("")
        error_lbl.setStyleSheet(f"color: {NEGATIVE}; font-size: 12px;")

        def _parse_float(label: str, raw: str) -> tuple[float | None, str]:
            s = raw.strip()
            if not s:
                return None, ""
            try:
                return float(s), ""
            except ValueError:
                return None, f"{label} must be a number, got \"{s}\""

        def _confirm() -> None:
            fields = [
                ("price_above", "Price Alert Above", f_p_above),
                ("price_below", "Price Alert Below", f_p_below),
                ("rsi_above",   "RSI Alert Above",   f_rsi_above),
                ("rsi_below",   "RSI Alert Below",   f_rsi_below),
                ("buy_target",  "Buy Target",         f_buy_tgt),
                ("sell_target", "Sell Target",        f_sell_tgt),
            ]
            for key, label, field in fields:
                val, err = _parse_float(label, field.text())
                if err:
                    error_lbl.setText(err)
                    return
                if val is not None:
                    entry[key] = val
                else:
                    entry.pop(key, None)
            self._state.save_watchlist()
            dlg.close()
            self._build_rows()

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.close)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("AccentBtn")
        save_btn.clicked.connect(_confirm)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        layout.addWidget(title_lbl)
        for w in [f_p_above, f_p_below, f_rsi_above, f_rsi_below, f_buy_tgt, f_sell_tgt, error_lbl]:
            layout.addWidget(w)
        layout.addLayout(btn_row)
        dlg.show()

    # ── Refresh ───────────────────────────────────────────────────────────

    async def refresh(self, _e=None) -> None:
        import yfinance as yf
        from services.charting import render_sparkline
        self._refresh_btn.setEnabled(False)
        tickers = [item["ticker"] for item in self._state.watchlist]

        for ticker in tickers:
            try:
                def _fetch(t: str):
                    obj  = yf.Ticker(t)
                    hist = obj.history(period="1mo")
                    try:
                        currency = obj.fast_info.currency or "USD"
                    except Exception:
                        currency = "USD"
                    return hist, currency

                hist, currency = await asyncio.get_event_loop().run_in_executor(
                    None, lambda t=ticker: _fetch(t)
                )
                if hist.empty:
                    continue
                price  = float(hist["Close"].iloc[-1])
                delta  = hist["Close"].diff()
                gains  = delta.clip(lower=0).rolling(14).mean()
                losses = (-delta.clip(upper=0)).rolling(14).mean()
                rsi    = float((100 - 100 / (1 + gains / losses)).iloc[-1])
                self._live[ticker] = {"price": price, "rsi": rsi, "currency": currency}

                # Generate 7-day sparkline (item 7)
                prices_7d = list(hist["Close"].tail(7))
                if len(prices_7d) >= 2:
                    up = prices_7d[-1] >= prices_7d[0]
                    spark = await asyncio.get_event_loop().run_in_executor(
                        None, render_sparkline, prices_7d, up
                    )
                    self._sparklines[ticker] = spark
            except Exception:
                pass

        self._build_rows()
        self._refresh_btn.setEnabled(True)

    # ── Add dialog ────────────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add to Watchlist")
        dlg.setMinimumWidth(340)
        dlg.setStyleSheet(f"QDialog {{ background-color: #161618; }}")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        def _field(placeholder: str, autofocus: bool = False) -> QLineEdit:
            f = QLineEdit()
            f.setPlaceholderText(placeholder)
            if autofocus:
                f.setFocus()
            return f

        title_lbl = QLabel("Add to Watchlist")
        title_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 15px; font-weight: 600;")

        f_ticker    = _field("Ticker (e.g. TSLA)", autofocus=True)
        f_p_above   = _field("Price Alert Above (optional)")
        f_p_below   = _field("Price Alert Below (optional)")
        f_rsi_above = _field("RSI Alert Above (optional)")
        f_rsi_below = _field("RSI Alert Below (optional)")

        error_lbl = QLabel("")
        error_lbl.setStyleSheet(f"color: {NEGATIVE}; font-size: 12px;")

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.close)
        add_btn = QPushButton("Add")
        add_btn.setObjectName("AccentBtn")

        def _parse_float(label: str, raw: str) -> tuple[float | None, str]:
            """Return (value, error_msg). value is None if field is empty (ok) or invalid (error)."""
            s = raw.strip()
            if not s:
                return None, ""
            try:
                return float(s), ""
            except ValueError:
                return None, f"{label} must be a number, got \"{s}\""

        def _confirm() -> None:
            ticker = f_ticker.text().strip().upper()
            if not ticker:
                error_lbl.setText("Ticker is required.")
                return
            if any(x["ticker"] == ticker for x in self._state.watchlist):
                error_lbl.setText(f"{ticker} is already in watchlist.")
                return
            entry: dict = {"ticker": ticker}
            fields = [
                ("price_above", "Price Alert Above", f_p_above),
                ("price_below", "Price Alert Below", f_p_below),
                ("rsi_above",   "RSI Alert Above",   f_rsi_above),
                ("rsi_below",   "RSI Alert Below",   f_rsi_below),
            ]
            for key, label, field in fields:
                val, err = _parse_float(label, field.text())
                if err:
                    error_lbl.setText(err)
                    return
                if val is not None:
                    entry[key] = val
            self._state.watchlist.append(entry)
            self._state.save_watchlist()
            dlg.close()
            self._build_rows()

        add_btn.clicked.connect(_confirm)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)

        layout.addWidget(title_lbl)
        for w in [f_ticker, f_p_above, f_p_below, f_rsi_above, f_rsi_below, error_lbl]:
            layout.addWidget(w)
        layout.addLayout(btn_row)

        dlg.show()
