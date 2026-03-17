"""
StockX GUI — Watchlist view (PyQt6).
Track tickers with optional price/RSI alert thresholds. Persists to data/watchlist.json.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, APP_BG, BORDER_CARD, BORDER_INPUT, BORDER_SUBTLE,
    NEGATIVE, POSITIVE, SURFACE_1, SURFACE_2, TEXT_1, TEXT_MUTED, fmt_price,
)

if TYPE_CHECKING:
    from gui.app import MainWindow


# ── Drag-to-reorder table (item 8) ───────────────────────────────────────────

class _DraggableTable(QTableWidget):
    """QTableWidget subclass that emits row reorder signals on drag-drop."""
    rows_reordered = pyqtSignal(int, int)  # (from_row, to_row)

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    def dropEvent(self, event) -> None:
        from_row = self.currentRow()
        super().dropEvent(event)
        to_row = self.currentRow()
        if from_row != to_row and from_row >= 0 and to_row >= 0:
            self.rows_reordered.emit(from_row, to_row)


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

        # Main content area: table + optional alert panel side-by-side
        content = QWidget()
        content_h = QHBoxLayout(content)
        content_h.setContentsMargins(0, 0, 0, 0)
        content_h.setSpacing(0)

        # Columns: Ticker(0) Price(1) Spark(2) RSI(3) Targets(4) Alert(5) Del(6)
        self._table = _DraggableTable(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Ticker", "Price", "7D", "RSI", "Targets", "Alert Conditions", ""]
        )
        hh = self._table.horizontalHeader()
        col_widths = [90, 100, 100, 70, 110, 130, 50]
        for col, w in enumerate(col_widths):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(col, w)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(6, 50)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(52)
        self._table.rows_reordered.connect(self._on_rows_reordered)

        content_h.addWidget(self._table, stretch=1)

        # Alert history panel (item 15) — hidden by default
        self._alert_panel = self._build_alert_panel()
        content_h.addWidget(self._alert_panel)

        root.addWidget(content, stretch=1)

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(48)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        icon  = QLabel("⭐")
        icon.setStyleSheet("font-size: 18px;")
        title = QLabel("Watchlist")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_1};")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setObjectName("IconBtn")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(f"QPushButton {{ color: {ACCENT}; background: transparent; border: none; }} QPushButton:hover {{ background: #1F2A40; border-radius: 6px; }}")
        self._refresh_btn.clicked.connect(
            lambda: asyncio.ensure_future(self.refresh())
        )

        self._alerts_hist_btn = QPushButton(f"🔔 Alerts ({len(self._state.alert_history)})")
        self._alerts_hist_btn.setObjectName("IconBtn")
        self._alerts_hist_btn.setFixedHeight(30)
        self._alerts_hist_btn.setStyleSheet(f"QPushButton {{ color: {ACCENT_CYAN}; background: transparent; border: none; font-size: 12px; }} QPushButton:hover {{ background: #1F2A40; border-radius: 6px; }}")
        self._alerts_hist_btn.clicked.connect(self._toggle_alert_panel)

        add_btn = QPushButton("+ Add")
        add_btn.setObjectName("AccentBtn")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self._open_add_dialog)

        for w in [icon, title, spacer, self._alerts_hist_btn, self._refresh_btn, add_btn]:
            h.addWidget(w)
        return bar

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
        close_btn = QPushButton("✕")
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

    # ── Table building ────────────────────────────────────────────────────

    def _alert_label(self, item: dict) -> str:
        parts: list[str] = []
        if item.get("price_above"): parts.append(f"P\u2265{item['price_above']}")
        if item.get("price_below"): parts.append(f"P\u2264{item['price_below']}")
        if item.get("rsi_above"):   parts.append(f"RSI\u2265{item['rsi_above']}")
        if item.get("rsi_below"):   parts.append(f"RSI\u2264{item['rsi_below']}")
        return "  |  ".join(parts) if parts else "\u2014"

    def _build_rows(self) -> None:
        self._table.setRowCount(0)
        for row_idx, item in enumerate(self._state.watchlist):
            ticker = item["ticker"]
            live   = self._live.get(ticker, {})
            price_str = fmt_price(live["price"], live.get("currency")) if "price" in live else "\u2014"
            rsi_val   = live.get("rsi")
            rsi_str   = f"{rsi_val:.1f}" if rsi_val is not None else "\u2014"
            rsi_color = NEGATIVE if (rsi_val or 50) >= 70 else (POSITIVE if (rsi_val or 50) <= 30 else TEXT_1)

            self._table.insertRow(row_idx)
            self._table.setRowHeight(row_idx, 52)

            # Col 0: Ticker — clickable button
            ticker_btn = QPushButton(ticker)
            ticker_btn.setStyleSheet(
                f"QPushButton {{ color: {ACCENT}; background: transparent; border: none;"
                f"font-weight: 600; font-size: 13px; text-align: left; }}"
                f"QPushButton:hover {{ color: {ACCENT_CYAN}; }}"
            )
            ticker_btn.clicked.connect(lambda _=False, t=ticker: self._mw.switch_to_analysis(f"Analyse {t}"))
            self._table.setCellWidget(row_idx, 0, ticker_btn)

            # Col 1: Price
            price_item = QTableWidgetItem(price_str)
            price_item.setForeground(QColor(TEXT_1))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row_idx, 1, price_item)

            # Col 2: Sparkline (item 7)
            spark_bytes = self._sparklines.get(ticker, b"")
            if spark_bytes:
                lbl = QLabel()
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img = QImage.fromData(bytes(spark_bytes))
                lbl.setPixmap(QPixmap.fromImage(img))
                self._table.setCellWidget(row_idx, 2, lbl)
            else:
                self._table.setItem(row_idx, 2, QTableWidgetItem("—"))

            # Col 3: RSI
            rsi_item = QTableWidgetItem(rsi_str)
            rsi_item.setForeground(QColor(rsi_color))
            rsi_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row_idx, 3, rsi_item)

            # Col 4: Target prices (item 13)
            bt = item.get("buy_target")
            st = item.get("sell_target")
            target_parts = []
            if bt: target_parts.append(f"↑${bt:.2f}")
            if st: target_parts.append(f"↓${st:.2f}")
            target_text = "  ".join(target_parts) if target_parts else "—"
            target_btn = QPushButton(target_text)
            target_btn.setToolTip("Click to edit price targets & alerts")
            target_btn.setStyleSheet(
                f"QPushButton {{ color: {ACCENT_CYAN}; background: transparent; border: none;"
                f"font-size: 11px; text-align: center; }}"
                f"QPushButton:hover {{ color: {ACCENT}; }}"
            )
            target_btn.clicked.connect(lambda _=False, t=ticker: self._open_edit_alerts_dialog(t))
            self._table.setCellWidget(row_idx, 4, target_btn)

            # Col 5: Alert conditions — clickable to edit
            alert_label = self._alert_label(item)
            alert_btn = QPushButton(alert_label)
            alert_btn.setToolTip("Click to edit alert conditions")
            alert_btn.setStyleSheet(
                f"QPushButton {{ color: {TEXT_MUTED}; background: transparent; border: none;"
                f"font-size: 12px; text-align: left; padding-left: 4px; }}"
                f"QPushButton:hover {{ color: {ACCENT_CYAN}; }}"
            )
            alert_btn.clicked.connect(lambda _=False, t=ticker: self._open_edit_alerts_dialog(t))
            self._table.setCellWidget(row_idx, 5, alert_btn)

            # Col 6: Delete button
            del_btn = QPushButton("✕")
            del_btn.setToolTip("Remove")
            del_btn.setStyleSheet(
                f"QPushButton {{ color: {NEGATIVE}; background: transparent; border: none; font-size: 14px; font-weight: 600; }}"
                f"QPushButton:hover {{ color: #ff6b6b; background: rgba(255,80,80,0.12); border-radius: 4px; }}"
            )
            del_btn.clicked.connect(lambda _=False, t=ticker: self._remove_ticker(t))
            self._table.setCellWidget(row_idx, 6, del_btn)

    def _remove_ticker(self, ticker: str) -> None:
        self._state.watchlist = [x for x in self._state.watchlist if x["ticker"] != ticker]
        self._state.save_watchlist()
        self._build_rows()

    def _on_rows_reordered(self, from_row: int, to_row: int) -> None:
        """Persist watchlist reorder after drag-drop (item 8)."""
        wl = self._state.watchlist
        if 0 <= from_row < len(wl) and 0 <= to_row < len(wl):
            item = wl.pop(from_row)
            wl.insert(to_row, item)
            self._state.save_watchlist()

    def _toggle_alert_panel(self) -> None:
        """Show/hide the alert history panel (item 15)."""
        self._alert_panel_visible = not self._alert_panel_visible
        self._alert_panel.setVisible(self._alert_panel_visible)
        if self._alert_panel_visible:
            self._refresh_alert_panel()
        count = len(self._state.alert_history)
        self._alerts_hist_btn.setText(f"🔔 Alerts ({count})")

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
                f"QFrame {{ background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD};"
                f"border-radius: 6px; }}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.setSpacing(2)

            atype = entry.get("type", "price")
            dot_color = type_colors.get(atype, TEXT_MUTED)
            msg_lbl = QLabel(f"● {entry.get('message', '')}")
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
        dlg.setWindowTitle(f"Edit Alerts — {ticker}")
        dlg.setMinimumWidth(340)
        dlg.setStyleSheet("QDialog { background-color: #141E2E; }")

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
        dlg.setStyleSheet(f"QDialog {{ background-color: #141E2E; }}")

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
