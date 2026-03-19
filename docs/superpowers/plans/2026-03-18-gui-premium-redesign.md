# StockX GUI Premium Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dated sidebar+table+toolbar GUI with a modern top-nav + list-row + borderless design.

**Architecture:** Replace NavSidebar (QFrame with NavButtons) with a horizontal TopNavBar. Replace all QTableWidget usage in watchlist/portfolio/earnings with QScrollArea + custom QFrame rows. Remove all QFrame#HeaderBar instances and use inline page titles. Restructure news to 2-column grid.

**Tech Stack:** PyQt6 (existing), no new dependencies.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `gui/app.py` | Rewrite | Remove NavButton/NavSidebar, add TopNavBar, change MainWindow layout from HBox→VBox |
| `gui/theme.py` | Modify | Add TopNavBar QSS rules, update #HeaderBar rules |
| `gui/views/analysis.py` | Modify | Remove header bar, add page title, adjust spacing, remove agent bubble borders |
| `gui/views/watchlist.py` | Rewrite | Replace QTableWidget+DraggableTable with QScrollArea+QFrame rows |
| `gui/views/portfolio.py` | Rewrite | Replace QTableWidget with QScrollArea+QFrame rows, keep summary cards |
| `gui/views/earnings.py` | Rewrite | Replace QTableWidget with QScrollArea+QFrame rows |
| `gui/views/news.py` | Modify | Change from vertical list to 2-column QGridLayout |
| `gui/views/heatmap.py` | Modify | Remove borders, increase radius/padding/font on tiles |
| `gui/views/settings.py` | Modify | Remove header bar, add page title, remove card borders |

---

## Chunk 1: Navigation Shell

### Task 1: Replace NavSidebar with TopNavBar in gui/app.py

**Files:**
- Rewrite: `gui/app.py`

- [ ] **Step 1: Rewrite gui/app.py**

Replace the entire NavButton, NavSidebar classes and MainWindow layout with:

```python
"""
StockX GUI — Main PyQt6 application.
TopNavBar shell with 7-panel stock dashboard, qasync event loop.
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
from gui.theme import ACCENT, BORDER_SUBTLE, SURFACE_1, TEXT_1, TEXT_2
from services.monitor import run_monitor


# ── TopNavBar ────────────────────────────────────────────────────────────────

class TopNavBar(QFrame):
    """52px horizontal navigation bar with brand text and tab items."""

    nav_changed = pyqtSignal(int)

    _TAB_LABELS = ["Analysis", "Watchlist", "Portfolio", "News", "Earnings", "Markets", "Settings"]

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
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

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
        from gui.views.settings  import SettingsView

        self._analysis_view  = AnalysisView(self._state, self)
        self._watchlist_view = WatchlistView(self._state, self)
        self._portfolio_view = PortfolioView(self._state, self)
        self._news_view      = NewsView(self._state, self)
        self._earnings_view  = EarningsView(self._state, self)
        self._heatmap_view   = SectorHeatmapView(self._state, self)
        self._settings_view  = SettingsView(self._state, self)

        for view in [
            self._analysis_view, self._watchlist_view, self._portfolio_view,
            self._news_view, self._earnings_view,
            self._heatmap_view, self._settings_view,
        ]:
            self._stack.addWidget(view)

        # ── Keyboard shortcuts — Ctrl+1…7 switch views ──────────
        for i in range(7):
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
            asyncio.ensure_future(self._auto_refresh_loop()),
        ]

    # ── Navigation ────────────────────────────────────────────────────────

    def _on_nav_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    def switch_to_analysis(self, prefill: str) -> None:
        self._topbar.set_active(0)
        self._stack.setCurrentIndex(0)
        self._analysis_view.set_input(prefill)

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
```

- [ ] **Step 2: Update theme.py — add TopNavBar QSS, remove NavSidebar QSS**

In `gui/theme.py` dark STYLESHEET, replace:
```
QFrame#NavSidebar {
    background-color: {NAV_BG}; border-right: 1px solid {BORDER_SUBTLE};
}
```
With:
```
QFrame#TopNavBar {
    background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE};
}
```

- [ ] **Step 3: Verify the app launches**

Run: `python run_gui.py`
Expected: App opens with horizontal top nav bar, no sidebar. All 7 tabs clickable. Ctrl+1-7 works.

- [ ] **Step 4: Commit**

```bash
git add gui/app.py gui/theme.py
git commit -m "feat: replace sidebar with top navigation bar"
```

---

## Chunk 2: View Headers → Page Titles

### Task 2: Remove header bars from all views, replace with page titles

**Files:**
- Modify: `gui/views/analysis.py`
- Modify: `gui/views/watchlist.py`
- Modify: `gui/views/portfolio.py`
- Modify: `gui/views/news.py`
- Modify: `gui/views/earnings.py`
- Modify: `gui/views/heatmap.py`
- Modify: `gui/views/settings.py`

For each view, the pattern is the same:
1. Remove the `_build_header()` method that returns a QFrame#HeaderBar with emoji icon
2. Replace with a page title section: 24px bold title + optional subtitle + right-aligned action buttons
3. Use 32px horizontal padding, 24px top padding

- [ ] **Step 5: Update analysis.py header**

Replace `_build_header()` in `AnalysisView` (lines 159-198). Remove the QFrame#HeaderBar, emoji icon. Replace with:

```python
def _build_header(self) -> QWidget:
    header = QWidget()
    header.setStyleSheet("background: transparent;")
    h = QHBoxLayout(header)
    h.setContentsMargins(32, 20, 32, 8)
    h.setSpacing(12)

    title_col = QVBoxLayout()
    title_col.setSpacing(2)
    title = QLabel("Analysis")
    title.setStyleSheet(f"color: {TEXT_1}; font-size: 24px; font-weight: 700;")
    subtitle = QLabel("AI-powered stock insights")
    subtitle.setStyleSheet(f"color: {TEXT_2}; font-size: 13px;")
    title_col.addWidget(title)
    title_col.addWidget(subtitle)
    h.addLayout(title_col)
    h.addStretch()

    self._provider_label = QLabel(self._state.detect_provider())
    self._provider_label.setStyleSheet(
        f"font-size: 11px; color: {ACCENT_CYAN}; background-color: {SURFACE_2};"
        f"border-radius: 10px; padding: 2px 8px;"
    )

    self._export_btn = _icon_btn("⬇", "Export as Markdown")
    self._export_btn.clicked.connect(self._export_chat)
    self._pdf_btn = _icon_btn("📄", "Export as PDF")
    self._pdf_btn.clicked.connect(self._export_pdf)
    self._history_btn = _icon_btn("📋", "Analysis history")
    self._history_btn.clicked.connect(self._toggle_history)

    self._clear_btn = QPushButton("Clear")
    self._clear_btn.setObjectName("DangerBtn")
    self._clear_btn.setFixedHeight(28)
    self._clear_btn.clicked.connect(self._clear_chat)

    for w in [self._provider_label, self._export_btn, self._pdf_btn,
              self._history_btn, self._clear_btn]:
        h.addWidget(w)
    return header
```

Also update `_build_chips_row()` — remove the `SURFACE_1` background and border-bottom:
```python
chips_widget.setStyleSheet("background: transparent;")
```
And update margins:
```python
h.setContentsMargins(32, 4, 32, 8)
```

Remove the border from agent bubbles — change line 409:
```python
f"QFrame {{ background-color: {SURFACE_2};"
"border-radius: 18px; border-top-left-radius: 4px; }"
```
(Remove `border: 1px solid {BORDER_CARD};`)

Update chat layout spacing from 4 to 12:
```python
self._chat_layout.setSpacing(12)
```

Update chat layout margins:
```python
self._chat_layout.setContentsMargins(32, 12, 32, 12)
```

Update score card to remove border:
```python
card.setStyleSheet(
    f"QFrame {{ background-color: {SURFACE_2};"
    f"border-radius: 10px; margin: 4px 8px 4px 8px; }}"
)
```

Update table bubble to remove border:
```python
bubble.setStyleSheet(
    f"QFrame {{ background-color: {SURFACE_2};"
    "border-radius: 18px; border-top-left-radius: 4px; }"
)
```

Update history card to remove border:
```python
card.setStyleSheet(
    f"QFrame {{ background-color: {SURFACE_2}; border-radius: 8px; }}"
    f"QFrame:hover {{ background-color: #222226; }}"
)
```

- [ ] **Step 6: Update watchlist.py header**

Replace `_build_header()` in `WatchlistView` (lines 104-141) with:

```python
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
```

Add `TEXT_2` and `SURFACE_3` to watchlist.py imports from `gui.theme`.

- [ ] **Step 7: Update portfolio.py, news.py, earnings.py, heatmap.py, settings.py headers**

Same pattern for each — replace `_build_header()`:

**portfolio.py:**
- Title: "Portfolio", Subtitle: "Track holdings and performance"
- Buttons: "Refresh Prices" + "+ Add Holding"

**news.py:**
- Title: "News", Subtitle: "Latest financial headlines"
- Button: "Refresh" (icon btn)

**earnings.py:**
- Title: "Earnings Calendar", Subtitle: "Upcoming earnings dates"
- Button: "Refresh" (icon btn)

**heatmap.py:**
- Title: "Markets", Subtitle: "Sector performance today"
- Button: "Refresh"

**settings.py:**
- Title: "Settings", no subtitle
- No action buttons

- [ ] **Step 8: Verify all views render with page titles**

Run: `python run_gui.py`
Expected: All 7 views show large page titles instead of toolbar-style headers. No emoji icons visible.

- [ ] **Step 9: Commit**

```bash
git add gui/views/
git commit -m "feat: replace header bars with page titles across all views"
```

---

## Chunk 3: Watchlist — List Rows

### Task 3: Replace watchlist QTableWidget with modern list rows

**Files:**
- Rewrite: `gui/views/watchlist.py`

- [ ] **Step 10: Remove _DraggableTable class entirely**

It won't be needed — drag reorder will be dropped (it was janky in the table anyway).

- [ ] **Step 11: Replace table with QScrollArea + QFrame rows**

Replace `_setup_ui()` from the `root.addWidget(self._build_header())` line onwards:

```python
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
```

- [ ] **Step 12: Rewrite _build_rows() to create QFrame rows**

```python
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

    # Price + change
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

    # Action buttons (edit/delete) — visible on hover via parent
    edit_btn = QPushButton("✎")
    edit_btn.setObjectName("IconBtn")
    edit_btn.setFixedSize(28, 28)
    edit_btn.setToolTip("Edit alerts & targets")
    edit_btn.clicked.connect(lambda _=False, t=ticker: self._open_edit_alerts_dialog(t))

    del_btn = QPushButton("✕")
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
```

- [ ] **Step 13: Update _toggle_alert_panel to use new button text**

Change `self._alerts_hist_btn.setText(f"🔔 Alerts ({count})")` to `self._alerts_hist_btn.setText(f"Alerts ({count})")`.

- [ ] **Step 14: Remove _DraggableTable class and its import**

Delete the entire `_DraggableTable` class (lines 30-46). Remove `QTableWidget`, `QTableWidgetItem`, `QHeaderView`, `QAbstractItemView` from imports.

- [ ] **Step 15: Remove `_on_rows_reordered` method**

No longer needed without the table.

- [ ] **Step 16: Verify watchlist view**

Run: `python run_gui.py`
Navigate to Watchlist tab. Expected: Modern list rows with avatar, ticker, sparkline, price, RSI, edit/delete buttons. No table headers or grid lines.

- [ ] **Step 17: Commit**

```bash
git add gui/views/watchlist.py
git commit -m "feat: replace watchlist table with modern list rows"
```

---

## Chunk 4: Portfolio — List Rows

### Task 4: Replace portfolio QTableWidget with list rows

**Files:**
- Rewrite: `gui/views/portfolio.py`

- [ ] **Step 18: Replace table with QScrollArea + QFrame rows**

Same pattern as watchlist. Replace `self._table` construction in `_setup_ui()` with:

```python
# List rows (replace QTableWidget)
self._rows_widget = QWidget()
self._rows_widget.setStyleSheet("background: transparent;")
self._rows_layout = QVBoxLayout(self._rows_widget)
self._rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
self._rows_layout.setContentsMargins(0, 0, 0, 0)
self._rows_layout.setSpacing(2)
body_layout.addWidget(self._rows_widget)
```

- [ ] **Step 19: Rewrite _build_rows() for portfolio list rows**

```python
def _build_rows(self) -> None:
    while self._rows_layout.count():
        child = self._rows_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    for idx, h_data in enumerate(self._state.portfolio):
        row = self._make_holding_row(h_data, idx)
        self._rows_layout.addWidget(row)

def _make_holding_row(self, h_data: dict, idx: int) -> QFrame:
    ticker   = h_data["ticker"]
    qty      = h_data["qty"]
    avg_cost = h_data["avg_cost"]
    price    = self._prices.get(ticker, avg_cost)
    code     = self._currencies.get(ticker)
    value    = price * qty
    cost     = avg_cost * qty
    pnl      = value - cost
    pnl_pct  = (pnl / cost * 100) if cost else 0.0
    pnl_color = POSITIVE if pnl >= 0 else NEGATIVE
    sign     = "+" if pnl >= 0 else ""

    ttm_div    = self._dividends.get(ticker, 0.0)
    ann_income = ttm_div * qty
    income_str = fmt_price(ann_income, code) if ann_income > 0 else "\u2014"

    bg = SURFACE_2 if idx % 2 == 0 else SURFACE_1
    row = QFrame()
    row.setStyleSheet(
        f"QFrame {{ background-color: {bg}; border-radius: 14px; }}"
        f"QFrame:hover {{ background-color: {SURFACE_3}; }}"
    )

    h = QHBoxLayout(row)
    h.setContentsMargins(16, 12, 16, 12)
    h.setSpacing(16)

    # Ticker
    ticker_lbl = QLabel(ticker)
    ticker_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 14px; font-weight: 700; background: transparent; min-width: 50px;")

    # Qty
    qty_lbl = QLabel(f"{qty:g} shares")
    qty_lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 12px; background: transparent; min-width: 70px;")

    # Price
    price_lbl = QLabel(fmt_price(price, code))
    price_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 14px; font-weight: 600; background: transparent;")
    price_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

    # Value
    val_lbl = QLabel(fmt_price(value, code))
    val_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 14px; font-weight: 600; background: transparent;")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

    # P&L
    pnl_lbl = QLabel(f"{sign}{fmt_price(pnl, code)}")
    pnl_lbl.setStyleSheet(f"color: {pnl_color}; font-size: 13px; font-weight: 600; background: transparent;")
    pnl_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

    pnl_pct_lbl = QLabel(f"{sign}{pnl_pct:.1f}%")
    pnl_pct_lbl.setStyleSheet(f"color: {pnl_color}; font-size: 12px; background: transparent; min-width: 50px;")
    pnl_pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

    # Delete
    del_btn = QPushButton("✕")
    del_btn.setStyleSheet(
        f"QPushButton {{ color: {TEXT_MUTED}; background: transparent; border: none; font-size: 14px; border-radius: 6px; }}"
        f"QPushButton:hover {{ color: {NEGATIVE}; background: rgba(251,113,133,0.08); }}"
    )
    del_btn.setFixedSize(28, 28)
    del_btn.clicked.connect(lambda _=False, t=ticker: self._remove_holding(t))

    h.addWidget(ticker_lbl)
    h.addWidget(qty_lbl)
    h.addStretch()
    h.addWidget(price_lbl)
    h.addWidget(val_lbl)
    h.addWidget(pnl_lbl)
    h.addWidget(pnl_pct_lbl)
    h.addWidget(del_btn)

    return row
```

- [ ] **Step 20: Remove QTableWidget imports, update header**

Remove `QTableWidget`, `QTableWidgetItem`, `QHeaderView` from imports.
Replace header same pattern as watchlist.

- [ ] **Step 21: Verify portfolio view**

Run: `python run_gui.py`
Expected: Summary cards + chart + modern list rows. No table.

- [ ] **Step 22: Commit**

```bash
git add gui/views/portfolio.py
git commit -m "feat: replace portfolio table with modern list rows"
```

---

## Chunk 5: Earnings — List Rows

### Task 5: Replace earnings QTableWidget with list rows

**Files:**
- Rewrite: `gui/views/earnings.py`

- [ ] **Step 23: Rewrite earnings view**

Replace entire `_setup_ui()` table construction with QScrollArea + QFrame rows. Same pattern as watchlist.

For each earnings row:
- Normal rows: `SURFACE_2`/`SURFACE_1` alternating, 14px radius
- Highlighted rows (≤7 days): `rgba(212,168,67,0.06)` background + `border-left: 3px solid {ACCENT}` via stylesheet
- Row contents: ticker (bold), date, days-until badge, EPS estimate, revenue estimate

Replace the `_refresh()` table population section with row creation.

- [ ] **Step 24: Replace header, remove table imports**

Same page title pattern. Remove `QTableWidget`, `QTableWidgetItem`, `QHeaderView` imports.

- [ ] **Step 25: Commit**

```bash
git add gui/views/earnings.py
git commit -m "feat: replace earnings table with modern list rows"
```

---

## Chunk 6: News — Card Grid

### Task 6: Change news from vertical list to 2-column grid

**Files:**
- Modify: `gui/views/news.py`

- [ ] **Step 26: Change body layout from QVBoxLayout to QGridLayout**

Replace `self._body_layout = QVBoxLayout(self._body_widget)` with:
```python
self._body_layout = QGridLayout(self._body_widget)
self._body_layout.setContentsMargins(32, 12, 32, 16)
self._body_layout.setSpacing(12)
```

Import `QGridLayout` from `PyQt6.QtWidgets`.

- [ ] **Step 27: Update _refresh() to place cards in grid**

Replace:
```python
for art in articles:
    card = _NewsCard(art)
    self._body_layout.addWidget(card)
```
With:
```python
for i, art in enumerate(articles):
    card = _NewsCard(art)
    self._body_layout.addWidget(card, i // 2, i % 2)
```

- [ ] **Step 28: Update _NewsCard styling**

Remove `border: 1px solid {BORDER_CARD}` from `_NewsCard.__init__()`. Update to:
```python
self.setStyleSheet(
    f"QFrame#Card {{ background-color: {SURFACE_2}; border: none; border-radius: 14px; }}"
    f"QFrame#Card:hover {{ background-color: {SURFACE_3}; }}"
)
```

Update ticker chip background from `rgba(0,200,150,0.15)` to `rgba(212,168,67,0.08)` and color to `{ACCENT}`.

Update headline font-size to 14px.

- [ ] **Step 29: Replace header, update margins**

Same page title pattern. Title: "News", Subtitle: "Latest financial headlines".

- [ ] **Step 30: Commit**

```bash
git add gui/views/news.py
git commit -m "feat: change news to 2-column card grid layout"
```

---

## Chunk 7: Heatmap + Settings — Minor Polish

### Task 7: Polish heatmap tiles and settings cards

**Files:**
- Modify: `gui/views/heatmap.py`
- Modify: `gui/views/settings.py`

- [ ] **Step 31: Update _HeatCell styling**

In `_apply_style()`, change:
```python
self.setStyleSheet(
    f"QFrame {{ background-color: {bg}; border: none; border-radius: 14px; }}"
    f"QFrame:hover {{ background-color: {bg}; }}"
)
```
Remove the `border: 1px solid {BORDER_CARD}`. Increase radius from 8 to 14.

Update `_pct_lbl` font-size from 14px to 18px.

Increase cell size from `140, 80` to `160, 90`.

Replace header with page title pattern.

- [ ] **Step 32: Update settings cards**

In `_section_card()`, change:
```python
card.setStyleSheet(
    f"QFrame#Card {{ background-color: {SURFACE_2}; border-radius: 14px; border: none; }}"
)
```

Update margins from `(20, 16, 20, 16)` to `(24, 20, 24, 20)`.

Replace header with page title pattern.

Update body margins from `(40, 24, 40, 24)` to `(32, 16, 32, 16)`.

- [ ] **Step 33: Commit**

```bash
git add gui/views/heatmap.py gui/views/settings.py
git commit -m "feat: polish heatmap tiles and settings cards"
```

---

## Chunk 8: Final Verification

### Task 8: Full app verification

- [ ] **Step 34: Launch and verify all views**

Run: `python run_gui.py`

Verify:
1. Top nav bar with "StockX" brand and 7 text tabs — no emoji icons
2. Ctrl+1-7 switches views correctly
3. Analysis: page title, chips, chat bubbles with more spacing, no borders on agent bubbles
4. Watchlist: page title, modern list rows, add/edit/delete work, sparklines show after refresh
5. Portfolio: summary cards + chart + list rows, add/delete work, refresh updates prices
6. News: 2-column card grid, cards clickable, sentiment dots visible
7. Earnings: list rows with accent-highlighted near-term earnings
8. Markets: borderless heatmap tiles, bigger %, click navigates to analysis
9. Settings: borderless cards, save works

- [ ] **Step 35: Final commit**

```bash
git add -A
git commit -m "feat: complete StockX GUI premium redesign"
```
