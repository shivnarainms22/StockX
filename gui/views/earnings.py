"""
StockX GUI — Earnings Calendar view (PyQt6).
Shows upcoming earnings dates for portfolio + watchlist tickers.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, BORDER_CARD, BORDER_SUBTLE, NEGATIVE, POSITIVE,
    SURFACE_1, SURFACE_2, SURFACE_3, TEXT_1, TEXT_2, TEXT_MUTED,
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

        # Status label (shown when empty)
        self._status_lbl = QLabel("No upcoming earnings data available")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; font-style: italic; padding: 40px;"
        )
        self._status_lbl.setVisible(False)

        root.addWidget(scroll, stretch=1)
        root.addWidget(self._status_lbl)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h = QHBoxLayout(header)
        h.setContentsMargins(32, 20, 32, 8)
        h.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Earnings Calendar")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Upcoming earnings dates for watched tickers")
        subtitle.setStyleSheet(f"color: {TEXT_2}; font-size: 13px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        h.addLayout(title_col)
        h.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none; border-radius: 10px; padding: 6px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
        )
        self._refresh_btn.clicked.connect(
            lambda: asyncio.get_event_loop().create_task(self._refresh())
        )

        h.addWidget(self._refresh_btn)
        return header

    # ── Data loading ──────────────────────────────────────────────────────

    async def _refresh(self, _e=None) -> None:
        import yfinance as yf

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Loading…")
        # Clear existing rows
        while self._rows_layout.count():
            child = self._rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
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
            self._refresh_btn.setText("Refresh")
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
            self._refresh_btn.setText("Refresh")
            return

        def _fmt_rev(v) -> str:
            if v is None: return "—"
            try: v = float(v)
            except Exception: return "—"
            if v >= 1e9: return f"${v/1e9:.2f}B"
            if v >= 1e6: return f"${v/1e6:.2f}M"
            return f"${v:,.0f}"

        # Clear existing rows
        while self._rows_layout.count():
            child = self._rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for row_idx, r in enumerate(rows):
            imminent  = 0 <= r["days"] <= 3   # very soon — extra prominent
            highlight = r["days"] <= 7
            date_str = r["date"].strftime("%b %d, %Y")
            days_str = f"{r['days']}d" if imminent else f"{r['days']} days"
            eps_str = "—"
            try: eps_str = f"${float(r['eps_est']):.2f}"
            except Exception: pass

            # Row frame
            if imminent:
                bg = "rgba(255, 165, 0, 0.08)"
                border_style = "border-left: 3px solid #FFA500;"
            elif highlight:
                bg = "rgba(212,168,67,0.06)"
                border_style = f"border-left: 3px solid {ACCENT};"
            else:
                bg = SURFACE_2 if row_idx % 2 == 0 else SURFACE_1
                border_style = ""

            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background-color: {bg}; border-radius: 12px; {border_style} }}"
                f"QFrame:hover {{ background-color: {SURFACE_3}; }}"
            )

            h = QHBoxLayout(row)
            h.setContentsMargins(20, 14, 20, 14)
            h.setSpacing(20)

            # Ticker
            ticker_lbl = QLabel(r["ticker"])
            ticker_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 14px; font-weight: 700; background: transparent; min-width: 60px;")

            # Date
            date_lbl = QLabel(date_str)
            date_lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 13px; background: transparent;")

            # Days-until badge — orange for ≤3 days, accent for ≤7, muted otherwise
            if imminent:
                badge_bg = "rgba(255, 165, 0, 0.20)"
                badge_color = "#FFA500"
            elif highlight:
                badge_bg = "rgba(212,168,67,0.12)"
                badge_color = ACCENT
            else:
                badge_bg = SURFACE_3
                badge_color = TEXT_2
            days_badge = QLabel(days_str)
            days_badge.setStyleSheet(
                f"padding: 4px 12px; background: {badge_bg}; border-radius: 8px;"
                f"font-size: 12px; color: {badge_color}; font-weight: 600;"
            )

            # EPS estimate
            eps_col = QVBoxLayout()
            eps_col.setSpacing(0)
            eps_hdr = QLabel("EPS Est.")
            eps_hdr.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
            eps_hdr.setAlignment(Qt.AlignmentFlag.AlignRight)
            eps_val = QLabel(eps_str)
            eps_val.setStyleSheet(f"color: {TEXT_1}; font-size: 13px; font-weight: 600; background: transparent;")
            eps_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            eps_col.addWidget(eps_hdr)
            eps_col.addWidget(eps_val)
            eps_widget = QWidget()
            eps_widget.setFixedWidth(80)
            eps_widget.setLayout(eps_col)
            eps_widget.setStyleSheet("background: transparent;")

            # Revenue estimate
            rev_col = QVBoxLayout()
            rev_col.setSpacing(0)
            rev_hdr = QLabel("Rev Est.")
            rev_hdr.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
            rev_hdr.setAlignment(Qt.AlignmentFlag.AlignRight)
            rev_val = QLabel(_fmt_rev(r["rev_est"]))
            rev_val.setStyleSheet(f"color: {TEXT_1}; font-size: 13px; font-weight: 600; background: transparent;")
            rev_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            rev_col.addWidget(rev_hdr)
            rev_col.addWidget(rev_val)
            rev_widget = QWidget()
            rev_widget.setFixedWidth(80)
            rev_widget.setLayout(rev_col)
            rev_widget.setStyleSheet("background: transparent;")

            h.addWidget(ticker_lbl)
            h.addWidget(date_lbl, stretch=1)
            h.addWidget(days_badge)
            h.addWidget(eps_widget)
            h.addWidget(rev_widget)

            self._rows_layout.addWidget(row)

        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Refresh")
