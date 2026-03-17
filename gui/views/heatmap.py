"""
StockX — Sector Heatmap view (item 18).
Displays 1-day % change for representative sector ETFs as a colour-coded grid.
Click any cell to analyse the ETF in the Analysis view.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, BORDER_CARD, BORDER_SUBTLE,
    NEGATIVE, POSITIVE, SURFACE_1, SURFACE_2, TEXT_1, TEXT_2, TEXT_MUTED,
)

if TYPE_CHECKING:
    from gui.app import MainWindow

# Representative ETF per sector
SECTOR_ETFS: dict[str, str] = {
    "Technology":       "QQQ",
    "Financials":       "XLF",
    "Energy":           "XLE",
    "Healthcare":       "XLV",
    "Utilities":        "XLU",
    "Materials":        "XLB",
    "Industrials":      "XLI",
    "Consumer Disc.":   "XLY",
    "Consumer Staples": "XLP",
    "Real Estate":      "XLRE",
    "Communication":    "XLC",
    "Semiconductors":   "SOXX",
    "Biotech":          "XBI",
    "Defence":          "ITA",
    "Gold":             "GLD",
    "Silver":           "SLV",
    "Oil":              "USO",
    "Crypto":           "BITO",
}

_COLS = 3  # cells per row


def _change_color(pct: float) -> tuple[str, str]:
    """Return (background_rgba, text_color) for a % change value."""
    if pct >= 2.0:
        return "rgba(0, 212, 170, 0.35)", POSITIVE
    if pct >= 0.5:
        return "rgba(0, 212, 170, 0.18)", POSITIVE
    if pct <= -2.0:
        return "rgba(255, 107, 107, 0.35)", NEGATIVE
    if pct <= -0.5:
        return "rgba(255, 107, 107, 0.18)", NEGATIVE
    return f"rgba(30, 45, 66, 0.50)", TEXT_2


class _HeatCell(QFrame):
    """Fixed 140×80 px tile showing sector name, ETF ticker, and 1D % change."""

    def __init__(self, sector: str, etf: str, main_window: "MainWindow",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sector = sector
        self._etf    = etf
        self._mw     = main_window

        self.setFixedSize(140, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(0.0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._sector_lbl = QLabel(sector)
        self._sector_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_1}; background: transparent;")
        self._sector_lbl.setWordWrap(True)

        self._etf_lbl = QLabel(etf)
        self._etf_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;")

        self._pct_lbl = QLabel("—")
        self._pct_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_2}; background: transparent;")

        layout.addWidget(self._sector_lbl)
        layout.addWidget(self._etf_lbl)
        layout.addStretch()
        layout.addWidget(self._pct_lbl)

    def update_change(self, pct: float) -> None:
        sign = "+" if pct >= 0 else ""
        self._pct_lbl.setText(f"{sign}{pct:.2f}%")
        self._apply_style(pct)
        _, txt_color = _change_color(pct)
        self._pct_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {txt_color}; background: transparent;"
        )

    def _apply_style(self, pct: float) -> None:
        bg, _ = _change_color(pct)
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {BORDER_CARD}; border-radius: 8px; }}"
            f"QFrame:hover {{ border-color: {ACCENT}; }}"
        )

    def mousePressEvent(self, event) -> None:
        self._mw.switch_to_analysis(f"Analyse {self._etf}")
        super().mousePressEvent(event)


class SectorHeatmapView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state  = state
        self._mw     = main_window
        self._cells: dict[str, _HeatCell] = {}
        self._setup_ui()
        # Auto-load shortly after startup to avoid blocking init
        QTimer.singleShot(2000, lambda: asyncio.ensure_future(self._refresh()))

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        body_v = QVBoxLayout(body)
        body_v.setContentsMargins(16, 16, 16, 16)
        body_v.setSpacing(12)

        # Last-updated label
        self._updated_lbl = QLabel("Loading…")
        self._updated_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        body_v.addWidget(self._updated_lbl)

        # Grid of heat cells
        grid_widget = QWidget()
        self._grid = QGridLayout(grid_widget)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(0, 0, 0, 0)

        for idx, (sector, etf) in enumerate(SECTOR_ETFS.items()):
            row = idx // _COLS
            col = idx % _COLS
            cell = _HeatCell(sector, etf, self._mw)
            self._cells[etf] = cell
            self._grid.addWidget(cell, row, col)

        body_v.addWidget(grid_widget)
        body_v.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("HeaderBar")
        bar.setFixedHeight(48)
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        icon  = QLabel("🌐")
        icon.setStyleSheet("font-size: 18px;")
        title = QLabel("Markets Heatmap")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_1};")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setObjectName("IconBtn")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: transparent; border: none; }}"
            f"QPushButton:hover {{ background: #1F2A40; border-radius: 6px; }}"
        )
        self._refresh_btn.clicked.connect(
            lambda: asyncio.ensure_future(self._refresh())
        )

        for w in [icon, title, spacer, self._refresh_btn]:
            h.addWidget(w)
        return bar

    # ── Data loading ──────────────────────────────────────────────────────

    async def _refresh(self) -> None:
        import yfinance as yf
        from datetime import datetime

        self._refresh_btn.setEnabled(False)
        self._updated_lbl.setText("Fetching data…")

        def _fetch_all() -> dict[str, float]:
            results: dict[str, float] = {}
            for sector, etf in SECTOR_ETFS.items():
                try:
                    hist = yf.Ticker(etf).history(period="2d")
                    if len(hist) >= 2:
                        prev  = float(hist["Close"].iloc[-2])
                        close = float(hist["Close"].iloc[-1])
                        pct   = (close - prev) / prev * 100 if prev else 0.0
                        results[etf] = pct
                    elif len(hist) == 1:
                        results[etf] = 0.0
                except Exception:
                    results[etf] = 0.0
            return results

        changes = await asyncio.get_event_loop().run_in_executor(None, _fetch_all)

        for etf, pct in changes.items():
            if etf in self._cells:
                self._cells[etf].update_change(pct)

        ts = datetime.now().strftime("%H:%M:%S")
        self._updated_lbl.setText(f"Last updated: {ts}  ·  Click a cell to analyse the ETF")
        self._refresh_btn.setEnabled(True)
