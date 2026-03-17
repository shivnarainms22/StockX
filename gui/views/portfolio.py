"""
StockX GUI — Portfolio view (PyQt6).
Track holdings with live P&L. Persists to data/portfolio.json.
Features: daily snapshot + performance chart above table.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, BORDER_CARD, BORDER_SUBTLE,
    NEGATIVE, POSITIVE, SURFACE_1, SURFACE_2, TEXT_1, TEXT_2, TEXT_MUTED,
    fmt_price, currency_symbol,
)

if TYPE_CHECKING:
    from gui.app import MainWindow


class PortfolioView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state     = state
        self._mw        = main_window
        self._prices:     dict[str, float] = {}
        self._currencies: dict[str, str]   = {}
        self._dividends:  dict[str, float] = {}   # item 12: ticker → annual div per share
        self._chart_mode: str = "value"            # item 10: "value" | "pnl" | "comparison"
        self._setup_ui()
        self._state.load_portfolio_snapshots()
        self._update_summary()
        self._build_rows()
        self._update_chart()

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_summary_bar())

        # Scrollable body: chart + table
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(16)

        # Chart controls row (items 10 & 11)
        chart_ctrl = QWidget()
        chart_ctrl.setStyleSheet("background: transparent;")
        ctrl_h = QHBoxLayout(chart_ctrl)
        ctrl_h.setContentsMargins(0, 0, 0, 4)
        ctrl_h.setSpacing(8)

        self._chart_value_btn = QPushButton("Value")
        self._chart_value_btn.setObjectName("Chip")
        self._chart_value_btn.setFixedHeight(26)
        self._chart_value_btn.clicked.connect(lambda: self._set_chart_mode("value"))

        self._chart_pnl_btn = QPushButton("Returns %")
        self._chart_pnl_btn.setObjectName("Chip")
        self._chart_pnl_btn.setFixedHeight(26)
        self._chart_pnl_btn.clicked.connect(lambda: self._set_chart_mode("pnl"))

        self._chart_cmp_btn = QPushButton("vs Benchmark")
        self._chart_cmp_btn.setObjectName("Chip")
        self._chart_cmp_btn.setFixedHeight(26)
        self._chart_cmp_btn.clicked.connect(lambda: self._set_chart_mode("comparison"))

        self._benchmark_dd = QComboBox()
        for label, sym in [("S&P 500", "SPY"), ("NASDAQ", "QQQ"), ("Nifty 50", "^NSEI"),
                            ("FTSE 100", "^FTSE"), ("DAX", "^GDAXI"), ("None", "")]:
            self._benchmark_dd.addItem(label, sym)
        self._benchmark_dd.currentIndexChanged.connect(lambda _: self._update_chart())
        self._benchmark_dd.setFixedHeight(28)
        self._benchmark_dd.setVisible(False)

        ctrl_h.addWidget(self._chart_value_btn)
        ctrl_h.addWidget(self._chart_pnl_btn)
        ctrl_h.addWidget(self._chart_cmp_btn)
        ctrl_h.addWidget(self._benchmark_dd)
        ctrl_h.addStretch()
        body_layout.addWidget(chart_ctrl)

        # Chart label
        self._chart_label = QLabel()
        self._chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chart_label.setScaledContents(False)
        self._chart_label.setFixedHeight(180)
        self._chart_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._chart_label.setStyleSheet(
            f"background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD}; border-radius: 12px;"
        )
        self._chart_label.setVisible(False)
        body_layout.addWidget(self._chart_label)

        # Table (item 12: added Ann. Income column)
        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            ["Ticker", "Qty", "Avg Cost", "Price", "Value", "P&L $", "P&L %", "Ann. Income", ""]
        )
        hh = self._table.horizontalHeader()
        for col, width in enumerate([90, 70, 90, 90, 90, 90, 80, 100]):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(col, width)
        hh.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(8, 40)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(50)
        body_layout.addWidget(self._table)
        body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(48)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        icon  = QLabel("💼")
        icon.setStyleSheet("font-size: 18px;")
        title = QLabel("Portfolio")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_1};")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._refresh_btn = QPushButton("↻ Refresh Prices")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: {SURFACE_2}; border: 1px solid {BORDER_CARD}; border-radius: 8px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; background: #1F2A40; }}"
        )
        self._refresh_btn.clicked.connect(
            lambda: asyncio.get_event_loop().create_task(self._refresh())
        )

        add_btn = QPushButton("+ Add Holding")
        add_btn.setObjectName("AccentBtn")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self._open_add_dialog)

        for w in [icon, title, spacer, self._refresh_btn, add_btn]:
            h.addWidget(w)
        return bar

    def _build_summary_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE}; }}"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(12)

        # Total Value card
        val_card = QFrame()
        val_card.setObjectName("SummaryCard")
        val_card.setFixedHeight(60)
        val_layout = QVBoxLayout(val_card)
        val_layout.setContentsMargins(16, 8, 16, 8)
        val_layout.setSpacing(2)
        val_lbl = QLabel("TOTAL VALUE")
        val_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; letter-spacing: 1px; background: transparent;")
        self._total_value_txt = QLabel("—")
        self._total_value_txt.setStyleSheet(f"color: {TEXT_1}; font-size: 18px; font-weight: 700; background: transparent;")
        val_layout.addWidget(val_lbl)
        val_layout.addWidget(self._total_value_txt)

        # P&L card
        pnl_card = QFrame()
        pnl_card.setObjectName("SummaryCard")
        pnl_card.setFixedHeight(60)
        pnl_layout = QVBoxLayout(pnl_card)
        pnl_layout.setContentsMargins(16, 8, 16, 8)
        pnl_layout.setSpacing(2)
        pnl_lbl = QLabel("TOTAL P&L")
        pnl_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; letter-spacing: 1px; background: transparent;")
        pnl_row = QHBoxLayout()
        pnl_row.setSpacing(8)
        self._pnl_dollar_txt = QLabel("—")
        self._pnl_dollar_txt.setStyleSheet(f"color: {TEXT_1}; font-size: 18px; font-weight: 700; background: transparent;")
        self._pnl_pct_txt = QLabel("")
        self._pnl_pct_txt.setStyleSheet(f"color: {TEXT_2}; font-size: 13px; background: transparent;")
        pnl_row.addWidget(self._pnl_dollar_txt)
        pnl_row.addWidget(self._pnl_pct_txt)
        pnl_row.addStretch()
        pnl_layout.addWidget(pnl_lbl)
        pnl_layout.addLayout(pnl_row)

        # Dividend income card (item 12)
        div_card = QFrame()
        div_card.setObjectName("SummaryCard")
        div_card.setFixedHeight(60)
        div_layout = QVBoxLayout(div_card)
        div_layout.setContentsMargins(16, 8, 16, 8)
        div_layout.setSpacing(2)
        div_lbl = QLabel("ANN. DIVIDEND INCOME")
        div_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; letter-spacing: 1px; background: transparent;")
        self._div_income_txt = QLabel("—")
        self._div_income_txt.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 18px; font-weight: 700; background: transparent;")
        div_layout.addWidget(div_lbl)
        div_layout.addWidget(self._div_income_txt)

        h.addWidget(val_card)
        h.addWidget(pnl_card)
        h.addWidget(div_card)
        h.addStretch()
        return bar

    # ── Data updates ──────────────────────────────────────────────────────

    def _update_summary(self) -> None:
        by_currency: dict[str, tuple[float, float]] = {}
        for h in self._state.portfolio:
            t     = h["ticker"]
            price = self._prices.get(t, h["avg_cost"])
            code  = self._currencies.get(t, "USD")
            val   = price * h["qty"]
            cost  = h["avg_cost"] * h["qty"]
            prev_val, prev_cost = by_currency.get(code, (0.0, 0.0))
            by_currency[code] = (prev_val + val, prev_cost + cost)

        if not by_currency:
            self._total_value_txt.setText("—")
            self._pnl_dollar_txt.setText("—")
            self._pnl_pct_txt.setText("")
            return

        if len(by_currency) == 1:
            code, (val, cost) = next(iter(by_currency.items()))
            pnl  = val - cost
            sign = "+" if pnl >= 0 else ""
            self._total_value_txt.setText(fmt_price(val, code))
            self._pnl_dollar_txt.setText(f"{sign}{fmt_price(pnl, code)}")
        else:
            val_parts = "  ".join(fmt_price(v, c) for c, (v, _) in by_currency.items())
            pnl_parts = []
            for c, (v, co) in by_currency.items():
                p = v - co; s = "+" if p >= 0 else ""
                pnl_parts.append(f"{s}{fmt_price(p, c)}")
            self._total_value_txt.setText(val_parts)
            self._pnl_dollar_txt.setText("  ".join(pnl_parts))

        total_val  = sum(v for v, _ in by_currency.values())
        total_cost = sum(c for _, c in by_currency.values())
        pnl_overall = total_val - total_cost
        pnl_pct  = (pnl_overall / total_cost * 100) if total_cost else 0.0
        pnl_color = POSITIVE if pnl_overall >= 0 else NEGATIVE
        sign = "+" if pnl_overall >= 0 else ""
        self._pnl_pct_txt.setText(f"({sign}{pnl_pct:.2f}%)")
        self._pnl_dollar_txt.setStyleSheet(f"color: {pnl_color}; font-size: 18px; font-weight: 700; background: transparent;")
        self._pnl_pct_txt.setStyleSheet(f"color: {pnl_color}; font-size: 13px; background: transparent;")

    def _build_rows(self) -> None:
        self._table.setRowCount(0)
        for row_idx, h in enumerate(self._state.portfolio):
            ticker   = h["ticker"]
            qty      = h["qty"]
            avg_cost = h["avg_cost"]
            price    = self._prices.get(ticker, avg_cost)
            code     = self._currencies.get(ticker)
            value    = price * qty
            cost     = avg_cost * qty
            pnl      = value - cost
            pnl_pct  = (pnl / cost * 100) if cost else 0.0
            pnl_color = POSITIVE if pnl >= 0 else NEGATIVE
            sign = "+" if pnl >= 0 else ""

            self._table.insertRow(row_idx)

            def _colored(txt: str, color: str, bold: bool = False) -> QTableWidgetItem:
                item = QTableWidgetItem(txt)
                item.setForeground(QColor(color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if bold:
                    from PyQt6.QtGui import QFont
                    f = item.font(); f.setBold(True); item.setFont(f)
                return item

            # Ann. dividend income (item 12)
            ttm_div = self._dividends.get(ticker, 0.0)
            ann_income = ttm_div * qty
            income_str = fmt_price(ann_income, code) if ann_income > 0 else "—"

            self._table.setItem(row_idx, 0, _colored(ticker, ACCENT, bold=True))
            self._table.setItem(row_idx, 1, _colored(f"{qty:g}", TEXT_1))
            self._table.setItem(row_idx, 2, _colored(fmt_price(avg_cost, code), TEXT_2))
            self._table.setItem(row_idx, 3, _colored(fmt_price(price, code), TEXT_1))
            self._table.setItem(row_idx, 4, _colored(fmt_price(value, code), TEXT_1))
            self._table.setItem(row_idx, 5, _colored(f"{sign}{fmt_price(pnl, code)}", pnl_color))
            self._table.setItem(row_idx, 6, _colored(f"{sign}{pnl_pct:.2f}%", pnl_color))
            self._table.setItem(row_idx, 7, _colored(income_str, ACCENT_CYAN))

            del_btn = QPushButton("✕")
            del_btn.setStyleSheet(
                f"QPushButton {{ color: {NEGATIVE}; background: transparent; border: none; font-size: 14px; font-weight: 600; }}"
                f"QPushButton:hover {{ color: #ff6b6b; background: rgba(255,80,80,0.12); border-radius: 4px; }}"
            )
            del_btn.clicked.connect(lambda _=False, t=ticker: self._remove_holding(t))
            self._table.setCellWidget(row_idx, 8, del_btn)

    def _update_dividend_income(self) -> None:
        """Update the Ann. Dividend Income summary card (item 12)."""
        total = sum(
            self._dividends.get(h["ticker"], 0.0) * h["qty"]
            for h in self._state.portfolio
        )
        if total > 0:
            # Use first holding's currency as approximation
            code = next(iter(self._currencies.values()), "USD") if self._currencies else "USD"
            self._div_income_txt.setText(fmt_price(total, code))
        else:
            self._div_income_txt.setText("—")

    def _remove_holding(self, ticker: str) -> None:
        self._state.portfolio = [x for x in self._state.portfolio if x["ticker"] != ticker]
        self._state.save_portfolio()
        self._update_summary()
        self._build_rows()

    def _set_chart_mode(self, mode: str) -> None:
        """Switch chart between value / P&L% / comparison modes (items 10, 11)."""
        self._chart_mode = mode
        self._benchmark_dd.setVisible(mode == "comparison")
        self._update_chart()

    def _update_chart(self) -> None:
        snaps = self._state.portfolio_snapshots
        if len(snaps) < 2:
            self._chart_label.setVisible(False)
            return
        try:
            if self._chart_mode == "pnl":
                from services.charting import render_pnl_chart
                png_bytes = render_pnl_chart(snaps)
            elif self._chart_mode == "comparison":
                bm_sym = self._benchmark_dd.currentData() or "SPY"
                if not bm_sym:
                    from services.charting import render_portfolio_chart
                    png_bytes = render_portfolio_chart(snaps)
                else:
                    from services.charting import render_comparison_chart
                    loop = asyncio.get_event_loop()
                    png_bytes = loop.run_in_executor(None, render_comparison_chart, snaps, bm_sym)
                    # run_in_executor returns a Future; schedule and bail — chart updates on next call
                    asyncio.ensure_future(self._async_update_comparison(snaps, bm_sym))
                    return
            else:
                from services.charting import render_portfolio_chart
                png_bytes = render_portfolio_chart(snaps)

            if png_bytes:
                img    = QImage.fromData(bytes(png_bytes))
                pixmap = QPixmap.fromImage(img)
                scaled = pixmap.scaledToWidth(
                    max(self._chart_label.width(), 600),
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._chart_label.setPixmap(scaled)
                self._chart_label.setVisible(True)
            else:
                self._chart_label.setVisible(False)
        except Exception:
            self._chart_label.setVisible(False)

    async def _async_update_comparison(self, snaps: list, bm_sym: str) -> None:
        """Fetch benchmark data in executor and update chart (item 11)."""
        try:
            from services.charting import render_comparison_chart
            png_bytes = await asyncio.get_event_loop().run_in_executor(
                None, render_comparison_chart, snaps, bm_sym
            )
            if png_bytes:
                img    = QImage.fromData(bytes(png_bytes))
                pixmap = QPixmap.fromImage(img)
                scaled = pixmap.scaledToWidth(
                    max(self._chart_label.width(), 600),
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._chart_label.setPixmap(scaled)
                self._chart_label.setVisible(True)
        except Exception:
            pass

    # ── Refresh ───────────────────────────────────────────────────────────

    async def _refresh(self, _e=None) -> None:
        import yfinance as yf
        self._refresh_btn.setEnabled(False)
        tickers = list({h["ticker"] for h in self._state.portfolio})

        for ticker in tickers:
            try:
                def _fetch(t: str):
                    obj      = yf.Ticker(t)
                    fi       = obj.fast_info
                    price    = fi.last_price      # may be None
                    currency = fi.currency or "USD"
                    return price, currency

                price, currency = await asyncio.get_event_loop().run_in_executor(
                    None, lambda t=ticker: _fetch(t)
                )
                # Only fall back to history if fast_info returned no price
                if price is None or price == 0:
                    raise ValueError("fast_info returned no price")
                self._prices[ticker]     = float(price)
                self._currencies[ticker] = currency
            except Exception:
                # History fallback — one extra call only when truly needed
                try:
                    def _fetch_hist(t: str):
                        obj  = yf.Ticker(t)
                        hist = obj.history(period="1d")
                        try:
                            currency = obj.fast_info.currency or "USD"
                        except Exception:
                            currency = "USD"
                        return hist, currency

                    hist, currency = await asyncio.get_event_loop().run_in_executor(
                        None, lambda t=ticker: _fetch_hist(t)
                    )
                    if not hist.empty:
                        self._prices[ticker]     = float(hist["Close"].iloc[-1])
                        self._currencies[ticker] = currency
                except Exception:
                    pass

        # Fetch annual dividend per share for each holding (item 12)
        for ticker in tickers:
            try:
                def _fetch_div(t: str) -> float:
                    import yfinance as yf
                    import pandas as pd
                    divs = yf.Ticker(t).dividends
                    cutoff = pd.Timestamp.now() - pd.DateOffset(years=1)
                    return float(divs[divs.index >= cutoff].sum())

                ttm = await asyncio.get_event_loop().run_in_executor(
                    None, lambda t=ticker: _fetch_div(t)
                )
                self._dividends[ticker] = ttm
            except Exception:
                self._dividends[ticker] = 0.0

        self._update_summary()
        self._build_rows()
        self._update_dividend_income()
        self._state.save_portfolio_snapshot(self._prices, self._currencies)
        self._update_chart()
        self._refresh_btn.setEnabled(True)

    # ── Add holding dialog ────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Holding")
        dlg.setMinimumWidth(320)
        dlg.setStyleSheet("QDialog { background-color: #141E2E; }")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = QLabel("Add Holding")
        title_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 15px; font-weight: 600;")

        f_ticker = QLineEdit(); f_ticker.setPlaceholderText("Ticker (e.g. AAPL)"); f_ticker.setFocus()
        f_qty    = QLineEdit(); f_qty.setPlaceholderText("Quantity")
        f_cost   = QLineEdit(); f_cost.setPlaceholderText("Avg Cost per Share ($)")
        error_lbl = QLabel(""); error_lbl.setStyleSheet(f"color: {NEGATIVE}; font-size: 12px;")

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(dlg.close)
        add_btn = QPushButton("Add"); add_btn.setObjectName("AccentBtn")

        def _confirm() -> None:
            ticker = f_ticker.text().strip().upper()
            if not ticker:
                error_lbl.setText("Ticker is required."); return
            try:
                qty      = float(f_qty.text().strip())
                avg_cost = float(f_cost.text().strip())
            except ValueError:
                error_lbl.setText("Qty and Avg Cost must be numbers."); return
            if qty <= 0 or avg_cost <= 0:
                error_lbl.setText("Qty and Avg Cost must be positive."); return

            existing = next((h for h in self._state.portfolio if h["ticker"] == ticker), None)
            if existing:
                old_val  = existing["qty"] * existing["avg_cost"]
                new_val  = qty * avg_cost
                new_qty  = existing["qty"] + qty
                existing["avg_cost"] = (old_val + new_val) / new_qty
                existing["qty"]      = new_qty
            else:
                self._state.portfolio.append({"ticker": ticker, "qty": qty, "avg_cost": avg_cost})
            self._state.save_portfolio()
            dlg.close()
            self._update_summary()
            self._build_rows()

        add_btn.clicked.connect(_confirm)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(add_btn)

        layout.addWidget(title_lbl)
        for w in [f_ticker, f_qty, f_cost, error_lbl]:
            layout.addWidget(w)
        layout.addLayout(btn_row)
        dlg.show()
