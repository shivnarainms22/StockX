"""
StockX GUI — Main PyQt6 application.
TopNavBar shell with 7-panel stock dashboard, qasync event loop.
"""
from __future__ import annotations

import asyncio
import os

from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from PyQt6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap, QPainter, QColor, QPen, QBrush

from gui.state import AppState
from gui.theme import ACCENT, BORDER_SUBTLE, SURFACE_1, TEXT_1, TEXT_2
from services.monitor import run_commodity_monitor, run_monitor


def _make_window_icon() -> QIcon:
    """Build a branded icon: dark background + ascending green bar chart.
    Saves to data/icon.ico so Windows taskbar can load it as a native icon file."""
    from pathlib import Path

    size = 256
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))  # transparent base

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Dark rounded background
    p.setBrush(QBrush(QColor("#0B0F1A")))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 40, 40)

    # 4 ascending bars: (x, width, height)
    accent = QColor("#00C896")
    p.setBrush(QBrush(accent))
    bars = [(28, 42, 76), (84, 42, 118), (140, 42, 158), (196, 42, 200)]
    for bx, bw, bh in bars:
        p.drawRoundedRect(bx, size - bh - 18, bw, bh, 7, 7)

    # Trend line connecting bar tops
    pen = QPen(accent, 7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    points = [QPoint(bx + bw // 2, size - bh - 18) for bx, bw, bh in bars]
    for i in range(len(points) - 1):
        p.drawLine(points[i], points[i + 1])

    p.end()

    # Save as .ico so Windows taskbar loads it as a native icon (most reliable)
    ico_path = Path(__file__).parent.parent / "data" / "icon.ico"
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(ico_path), "ICO")

    return QIcon(str(ico_path))


# ── TopNavBar ────────────────────────────────────────────────────────────────

class TopNavBar(QFrame):
    """52px horizontal navigation bar with brand text and tab items."""

    nav_changed = pyqtSignal(int)

    _TAB_LABELS = ["Analysis", "Watchlist", "Portfolio", "News", "Earnings", "Markets", "Macro", "Settings"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopNavBar")
        self.setFixedHeight(52)
        self.setStyleSheet(
            f"QFrame#TopNavBar {{ background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE}; }}"
        )

        h = QHBoxLayout(self)
        h.setContentsMargins(24, 0, 24, 0)
        h.setSpacing(0)

        # Brand
        brand = QLabel("StockX")
        brand.setStyleSheet(
            f"color: {ACCENT}; font-size: 17px; font-weight: 700; background: transparent;"
            "padding-right: 32px;"
        )
        h.addWidget(brand)

        # Tab items
        self._tabs: list[QLabel] = []
        for i, label in enumerate(self._TAB_LABELS):
            tab = QLabel(label)
            tab.setCursor(Qt.CursorShape.PointingHandCursor)
            tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tab.setFixedHeight(52)
            tab.setContentsMargins(16, 0, 16, 0)
            tab.mousePressEvent = lambda ev, idx=i: self._on_tab(idx)
            self._tabs.append(tab)
            h.addWidget(tab)

        h.addStretch()

        self._active_idx = 0
        self._update_styles()

    def _on_tab(self, idx: int) -> None:
        self._active_idx = idx
        self._update_styles()
        self.nav_changed.emit(idx)

    def set_active(self, idx: int) -> None:
        self._active_idx = idx
        self._update_styles()
        self.nav_changed.emit(idx)

    def _update_styles(self) -> None:
        for i, tab in enumerate(self._tabs):
            if i == self._active_idx:
                tab.setStyleSheet(
                    f"color: {ACCENT}; font-size: 13px; font-weight: 600;"
                    f"border-bottom: 2px solid {ACCENT}; background: transparent;"
                    "padding-bottom: 0px;"
                )
            else:
                tab.setStyleSheet(
                    f"color: {TEXT_2}; font-size: 13px; font-weight: 500;"
                    "border-bottom: 2px solid transparent; background: transparent;"
                    "padding-bottom: 0px;"
                )


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StockX")
        self.setWindowIcon(_make_window_icon())
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # ── Shared state ──────────────────────────────────────────────────
        self._state = AppState()
        self._state.load_portfolio()
        self._state.load_watchlist()
        self._state.load_analysis_history()
        self._state.load_portfolio_snapshots()
        self._state.load_alert_history()
        self._state.load_commodity_state()
        try:
            self._state.watchlist_refresh_interval = int(
                os.environ.get("WATCHLIST_REFRESH_INTERVAL", "0")
            )
        except ValueError:
            pass

        # ── Central layout (vertical: topbar + stack) ─────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._topbar = TopNavBar()
        self._topbar.nav_changed.connect(self._on_nav_changed)
        main_layout.addWidget(self._topbar)

        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack)

        # ── Build views (import here to avoid circular deps) ──────────────
        from gui.views.analysis  import AnalysisView
        from gui.views.watchlist import WatchlistView
        from gui.views.portfolio import PortfolioView
        from gui.views.news      import NewsView
        from gui.views.earnings  import EarningsView
        from gui.views.heatmap   import SectorHeatmapView
        from gui.views.macro     import MacroView
        from gui.views.settings  import SettingsView

        self._analysis_view  = AnalysisView(self._state, self)
        self._watchlist_view = WatchlistView(self._state, self)
        self._portfolio_view = PortfolioView(self._state, self)
        self._news_view      = NewsView(self._state, self)
        self._earnings_view  = EarningsView(self._state, self)
        self._heatmap_view   = SectorHeatmapView(self._state, self)
        self._macro_view     = MacroView(self._state, self)
        self._settings_view  = SettingsView(self._state, self)

        for view in [
            self._analysis_view, self._watchlist_view, self._portfolio_view,
            self._news_view, self._earnings_view,
            self._heatmap_view, self._macro_view, self._settings_view,
        ]:
            self._stack.addWidget(view)

        # ── Keyboard shortcuts — Ctrl+1…8 switch views ──────────
        for i in range(8):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self).activated.connect(
                lambda _=False, idx=i: self._topbar.set_active(idx)
            )

        # ── Status bar ────────────────────────────────────────────────────
        self.statusBar().showMessage("Ready")

        self._shutting_down = False

        # ── Background tasks ──────────────────────────────────────────────
        self._bg_tasks = [
            asyncio.ensure_future(self._init_agent()),
            asyncio.ensure_future(run_monitor(self._state, self._show_alert)),
            asyncio.ensure_future(run_commodity_monitor(self._state, self._show_alert)),
            asyncio.ensure_future(self._auto_refresh_loop()),
        ]

    # ── Navigation ────────────────────────────────────────────────────────

    def _on_nav_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    def switch_to_analysis(self, prefill: str) -> None:
        self._topbar.set_active(0)
        self._stack.setCurrentIndex(0)
        self._analysis_view.set_input(prefill)

    def switch_to_macro(self) -> None:
        self._topbar.set_active(6)
        self._stack.setCurrentIndex(6)

    # ── Theme ─────────────────────────────────────────────────────────────

    def apply_theme(self, dark: bool) -> None:
        from gui.theme import get_stylesheet
        QApplication.instance().setStyleSheet(get_stylesheet(dark))

    # ── Status / alerts ───────────────────────────────────────────────────

    def _show_alert(self, ticker: str, msg: str) -> None:
        self.statusBar().showMessage(f"\u26a0  {ticker}: {msg}", 15000)

    def show_status(self, msg: str, ms: int = 5000) -> None:
        self.statusBar().showMessage(msg, ms)

    # ── Background async tasks ────────────────────────────────────────────

    async def _init_agent(self) -> None:
        loop = asyncio.get_running_loop()
        from agent.core import AgentCore
        try:
            self._state.agent = await loop.run_in_executor(None, AgentCore)
        except Exception:
            pass
        finally:
            self._analysis_view.update_provider_label(self._state.detect_provider())

    def closeEvent(self, event) -> None:
        if self._shutting_down:
            event.accept()
            return
        event.ignore()
        self._shutting_down = True
        asyncio.ensure_future(self._graceful_shutdown())

    async def _graceful_shutdown(self) -> None:
        current = asyncio.current_task()
        all_tasks = [t for t in asyncio.all_tasks() if t is not current]
        for task in all_tasks:
            task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*all_tasks, return_exceptions=True),
                timeout=3.0,
            )
        except asyncio.TimeoutError:
            pass
        try:
            await asyncio.get_running_loop().shutdown_asyncgens()
        except Exception:
            pass
        QApplication.instance().quit()

    async def _auto_refresh_loop(self) -> None:
        while True:
            interval = self._state.watchlist_refresh_interval
            if interval > 0:
                await asyncio.sleep(interval * 60)
                await self._watchlist_view.refresh()
            else:
                await asyncio.sleep(30)
