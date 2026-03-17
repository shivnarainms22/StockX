"""
StockX GUI — Earnings Calendar view (PyQt6).
Shows upcoming earnings dates for portfolio + watchlist tickers.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QScrollArea, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, BORDER_SUBTLE, NEGATIVE, POSITIVE,
    SURFACE_1, SURFACE_2, TEXT_1, TEXT_2, TEXT_MUTED,
)

if TYPE_CHECKING:
    from gui.app import MainWindow


class EarningsView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw    = main_window
        self._setup_ui()
        # Auto-load on startup (matches Flet behavior)
        asyncio.get_event_loop().create_task(self._refresh())

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Ticker", "Date", "Days Until", "EPS Est.", "Revenue Est."]
        )
        hh = self._table.horizontalHeader()
        for col, width in enumerate([90, 110, 100, 110, 130]):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(col, width)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(48)

        # Status label (shown when empty)
        self._status_lbl = QLabel("No upcoming earnings data available")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; font-style: italic; padding: 40px;"
        )
        self._status_lbl.setVisible(False)

        root.addWidget(self._table, stretch=1)
        root.addWidget(self._status_lbl)

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(48)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        icon  = QLabel("📅")
        icon.setStyleSheet("font-size: 18px;")
        title = QLabel("Earnings Calendar")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_1};")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setObjectName("IconBtn")
        self._refresh_btn.setToolTip("Refresh earnings calendar")
        self._refresh_btn.setFixedSize(32, 32)
        self._refresh_btn.clicked.connect(
            lambda: asyncio.get_event_loop().create_task(self._refresh())
        )

        h.addWidget(icon)
        h.addWidget(title)
        h.addWidget(spacer)
        h.addWidget(self._refresh_btn)
        return bar

    # ── Data loading ──────────────────────────────────────────────────────

    async def _refresh(self, _e=None) -> None:
        import yfinance as yf

        self._refresh_btn.setEnabled(False)
        self._table.setRowCount(0)
        self._status_lbl.setVisible(False)

        tickers: list[str] = list({
            h["ticker"] for h in self._state.portfolio
        } | {
            w["ticker"] for w in self._state.watchlist
        })

        if not tickers:
            self._status_lbl.setText("Add tickers to Watchlist or Portfolio to see earnings")
            self._status_lbl.setVisible(True)
            self._refresh_btn.setEnabled(True)
            return

        def _fetch_all():
            rows: list[dict] = []
            seen: set[str] = set()
            for t in tickers:
                if t in seen:
                    continue
                seen.add(t)
                try:
                    cal = yf.Ticker(t).calendar
                    if cal is None:
                        continue
                    if hasattr(cal, "to_dict"):
                        cal = cal.to_dict()
                    ed_raw = cal.get("Earnings Date") or cal.get("earnings_date")
                    if ed_raw is None:
                        continue
                    if isinstance(ed_raw, (list, tuple)):
                        ed_raw = ed_raw[0] if ed_raw else None
                    if ed_raw is None:
                        continue
                    if isinstance(ed_raw, datetime):
                        ed = ed_raw.date()
                    elif isinstance(ed_raw, date):
                        ed = ed_raw
                    else:
                        try:
                            ed = datetime.strptime(str(ed_raw)[:10], "%Y-%m-%d").date()
                        except Exception:
                            continue

                    days_until = (ed - date.today()).days
                    eps_est = cal.get("Earnings Average") or cal.get("EPS Estimate")
                    rev_est = cal.get("Revenue Average") or cal.get("Revenue Estimate")

                    rows.append({
                        "ticker": t, "date": ed,
                        "days": days_until, "eps_est": eps_est, "rev_est": rev_est,
                    })
                except Exception:
                    pass
            rows.sort(key=lambda r: r["date"])
            return rows

        rows = await asyncio.get_event_loop().run_in_executor(None, _fetch_all)

        if not rows:
            self._status_lbl.setText("No upcoming earnings data available")
            self._status_lbl.setVisible(True)
            self._refresh_btn.setEnabled(True)
            return

        def _fmt_rev(v) -> str:
            if v is None: return "—"
            try: v = float(v)
            except Exception: return "—"
            if v >= 1e9: return f"${v/1e9:.2f}B"
            if v >= 1e6: return f"${v/1e6:.2f}M"
            return f"${v:,.0f}"

        self._table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            highlight   = r["days"] <= 7
            date_str    = r["date"].strftime("%Y-%m-%d")
            days_str    = f"{r['days']}d"
            days_color  = ACCENT if highlight else TEXT_2
            eps_str = "—"
            try: eps_str = f"${float(r['eps_est']):.2f}"
            except Exception: pass

            def _item(txt: str, color: str, bold: bool = False, center: bool = True) -> QTableWidgetItem:
                it = QTableWidgetItem(txt)
                it.setForeground(QColor(color))
                if center:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if bold:
                    from PyQt6.QtGui import QFont
                    f = it.font(); f.setBold(True); it.setFont(f)
                if highlight:
                    it.setBackground(QColor(0, 200, 150, 30))
                return it

            self._table.setItem(row_idx, 0, _item(r["ticker"],   ACCENT,     bold=True))
            self._table.setItem(row_idx, 1, _item(date_str,      TEXT_1))
            self._table.setItem(row_idx, 2, _item(days_str,      days_color, bold=highlight))
            self._table.setItem(row_idx, 3, _item(eps_str,       TEXT_2))
            self._table.setItem(row_idx, 4, _item(_fmt_rev(r["rev_est"]), TEXT_2))

        self._refresh_btn.setEnabled(True)
