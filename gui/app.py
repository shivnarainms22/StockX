"""
StockX GUI — Main PyQt6 application.
NavSidebar shell with 6-panel stock dashboard, qasync event loop.
"""
from __future__ import annotations

import asyncio
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from PyQt6.QtGui import QKeySequence, QShortcut

from gui.state import AppState
from gui.theme import ACCENT, ACCENT_GLOW, BORDER_SUBTLE, NAV_BG, TEXT_1, TEXT_MUTED
from services.monitor import run_monitor


# ── NavButton ─────────────────────────────────────────────────────────────────

class NavButton(QFrame):
    """72×64 nav icon + label button for the sidebar."""

    clicked = pyqtSignal()

    _STYLE_INACTIVE = "QFrame { background: transparent; border-radius: 8px; }"
    _STYLE_ACTIVE   = "QFrame { background-color: rgba(0,200,150,0.15); border-radius: 8px; }"
    _STYLE_HOVER    = f"QFrame {{ background-color: #1F2A40; border-radius: 8px; }}"

    def __init__(self, icon: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self.setFixedSize(72, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._STYLE_INACTIVE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 18px; background: transparent;")

        self._text_lbl = QLabel(label)
        self._text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;")

        layout.addWidget(icon_lbl)
        layout.addWidget(self._text_lbl)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setStyleSheet(self._STYLE_ACTIVE if active else self._STYLE_INACTIVE)
        color = ACCENT if active else TEXT_MUTED
        self._text_lbl.setStyleSheet(f"font-size: 10px; color: {color}; background: transparent;")

    def enterEvent(self, event) -> None:
        if not self._active:
            self.setStyleSheet(self._STYLE_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._active:
            self.setStyleSheet(self._STYLE_INACTIVE)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


# ── NavSidebar ────────────────────────────────────────────────────────────────

class NavSidebar(QFrame):
    """72px left sidebar with logo + 6 NavButtons."""

    nav_changed = pyqtSignal(int)

    _NAV_ITEMS = [
        ("📊", "Analysis"),
        ("⭐", "Watchlist"),
        ("💼", "Portfolio"),
        ("📰", "News"),
        ("📅", "Earnings"),
        ("🌐", "Markets"),
        ("⚙", "Settings"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavSidebar")
        self.setFixedWidth(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Branding logo
        logo_container = QFrame()
        logo_container.setFixedSize(72, 56)
        logo_container.setStyleSheet(f"background-color: {NAV_BG}; border-bottom: 1px solid {BORDER_SUBTLE};")
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl = QLabel("S")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setFixedSize(36, 36)
        logo_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 18px; font-weight: bold;"
            f"background-color: rgba(0,200,150,0.15); border-radius: 8px;"
        )
        logo_layout.addWidget(logo_lbl)
        layout.addWidget(logo_container)

        # Nav buttons
        self._buttons: list[NavButton] = []
        for icon, label in self._NAV_ITEMS:
            btn = NavButton(icon, label)
            idx = len(self._buttons)
            btn.clicked.connect(lambda _checked=False, i=idx: self._on_nav(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        self._active_idx = 0
        self._buttons[0].set_active(True)

    def _on_nav(self, idx: int) -> None:
        self._buttons[self._active_idx].set_active(False)
        self._active_idx = idx
        self._buttons[idx].set_active(True)
        self.nav_changed.emit(idx)

    def set_active(self, idx: int) -> None:
        self._on_nav(idx)


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StockX")
        self.resize(1100, 750)
        self.setMinimumSize(800, 550)

        # ── Shared state ──────────────────────────────────────────────────
        self._state = AppState()
        self._state.load_portfolio()
        self._state.load_watchlist()
        self._state.load_analysis_history()
        self._state.load_portfolio_snapshots()
        self._state.load_alert_history()
        try:
            self._state.watchlist_refresh_interval = int(
                os.environ.get("WATCHLIST_REFRESH_INTERVAL", "0")
            )
        except ValueError:
            pass

        # ── Central layout ────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = NavSidebar()
        self._sidebar.nav_changed.connect(self._on_nav_changed)
        main_layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack)

        # ── Build views (import here to avoid circular deps) ──────────────
        from gui.views.analysis  import AnalysisView
        from gui.views.watchlist import WatchlistView
        from gui.views.portfolio import PortfolioView
        from gui.views.news      import NewsView
        from gui.views.earnings  import EarningsView
        from gui.views.heatmap   import SectorHeatmapView
        from gui.views.settings  import SettingsView

        self._analysis_view  = AnalysisView(self._state, self)
        self._watchlist_view = WatchlistView(self._state, self)
        self._portfolio_view = PortfolioView(self._state, self)
        self._news_view      = NewsView(self._state, self)
        self._earnings_view  = EarningsView(self._state, self)
        self._heatmap_view   = SectorHeatmapView(self._state, self)
        self._settings_view  = SettingsView(self._state, self)

        # Sidebar order: Analysis(0) Watchlist(1) Portfolio(2) News(3)
        #                Earnings(4) Markets(5) Settings(6)
        for view in [
            self._analysis_view, self._watchlist_view, self._portfolio_view,
            self._news_view, self._earnings_view,
            self._heatmap_view, self._settings_view,
        ]:
            self._stack.addWidget(view)

        # ── Keyboard shortcuts (item 6) — Ctrl+1…7 switch views ──────────
        for i in range(7):
            QShortcut(QKeySequence(f"Ctrl+{i+1}"), self).activated.connect(
                lambda _=False, idx=i: self._sidebar.set_active(idx)
            )

        # ── Status bar ────────────────────────────────────────────────────
        self.statusBar().showMessage("Ready")

        self._shutting_down = False

        # ── Background tasks ──────────────────────────────────────────────
        self._bg_tasks = [
            asyncio.ensure_future(self._init_agent()),
            asyncio.ensure_future(run_monitor(self._state, self._show_alert)),
            asyncio.ensure_future(self._auto_refresh_loop()),
        ]

    # ── Navigation ────────────────────────────────────────────────────────

    def _on_nav_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    def switch_to_analysis(self, prefill: str) -> None:
        self._sidebar.set_active(0)
        self._stack.setCurrentIndex(0)
        self._analysis_view.set_input(prefill)

    # ── Theme (item 5) ────────────────────────────────────────────────────

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
