"""
StockX GUI — Analysis view (PyQt6).
Streaming stock analysis with chat bubbles, quick-action chips,
compare table, analysis history panel, and export.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QVBoxLayout, QWidget, QLineEdit,
)
from PyQt6.QtGui import QColor, QKeySequence, QShortcut

from gui.state import AppState, Message
from gui.theme import (
    ACCENT, ACCENT_CYAN, ACCENT_GLOW, APP_BG, BORDER_CARD, BORDER_INPUT,
    BORDER_SUBTLE, NEGATIVE, POSITIVE, SURFACE_1, SURFACE_2, TEXT_1, TEXT_MUTED, TEXT_2,
)

if TYPE_CHECKING:
    from gui.app import MainWindow

_EXPORTS_DIR = Path(__file__).parent.parent.parent / "data" / "exports"


# ── AnalysisWorker ────────────────────────────────────────────────────────────

class AnalysisWorker(QThread):
    """Run agent.run() in a dedicated OS thread with its own asyncio event loop.

    All UI signals are emitted from the worker thread; Qt's queued-connection
    mechanism delivers them safely on the main thread — no direct widget access
    from background code.
    """

    chunk_received = pyqtSignal(str)
    finished       = pyqtSignal(str)
    error          = pyqtSignal(str)
    cancelled      = pyqtSignal()

    def __init__(self, agent, task_text: str, history: list) -> None:
        super().__init__()
        self._agent     = agent
        self._task_text = task_text
        self._history   = history
        self._loop:         asyncio.AbstractEventLoop | None = None
        self._asyncio_task: asyncio.Task | None              = None

    def run(self) -> None:  # QThread entry-point
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        exc_info: BaseException | None = None
        result:   str                  = ""

        try:
            def on_chunk(chunk: str) -> None:
                self.chunk_received.emit(chunk)

            async def _execute() -> str:
                self._asyncio_task = asyncio.current_task()
                return await self._agent.run(
                    task=self._task_text,
                    history=self._history,
                    on_chunk=on_chunk,
                )

            result = loop.run_until_complete(_execute())

        except BaseException as exc:
            exc_info = exc

        finally:
            # Mirror asyncio.run(): shut down all async generators while the
            # loop is still live so httpx/httpcore connections close cleanly
            # and never reach GC in a half-open state.
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop         = None
            self._asyncio_task = None

        # Emit result signals after the loop is fully closed
        if exc_info is None:
            self.finished.emit(result)
        elif isinstance(exc_info, asyncio.CancelledError):
            self.cancelled.emit()
        else:
            self.error.emit(str(exc_info))

    def cancel(self) -> None:
        """Thread-safe: schedule task.cancel() on the worker's event loop."""
        if self._loop is not None and self._asyncio_task is not None:
            self._loop.call_soon_threadsafe(self._asyncio_task.cancel)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _icon_btn(icon: str, tooltip: str) -> QPushButton:
    btn = QPushButton(icon)
    btn.setObjectName("IconBtn")
    btn.setToolTip(tooltip)
    btn.setFixedSize(32, 32)
    return btn


def _chip_btn(label: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setObjectName("Chip")
    return btn


# ── AnalysisView ──────────────────────────────────────────────────────────────

class AnalysisView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw = main_window
        self._streaming_label: QLabel | None = None
        self._worker: AnalysisWorker | None = None
        self._history_panel_visible = False
        self._setup_ui()
        self._rebuild_messages()

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_chips_row())

        # Content area: chat column + history panel side-by-side
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)
        content_row.addLayout(self._build_chat_column(), stretch=1)
        self._history_panel = self._build_history_panel()
        content_row.addWidget(self._history_panel)

        content_frame = QWidget()
        content_frame.setLayout(content_row)
        root.addWidget(content_frame, stretch=1)

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

    def _build_chips_row(self) -> QWidget:
        chips_widget = QWidget()
        chips_widget.setStyleSheet("background: transparent;")
        h = QHBoxLayout(chips_widget)
        h.setContentsMargins(32, 4, 32, 8)
        h.setSpacing(8)

        chip_defs = [
            ("Analyse Ticker",  "Analyse ",                  False),
            ("Screen Sector",   "Screen technology sector",  False),
            ("Market Overview", "Give me a market overview: screen all sectors top 3 picks", True),
            ("Full Report",     "Full report ",              False),
            ("Compare",         "Compare AAPL, TSLA, NVDA",  False),
        ]
        for label, prefill, send_now in chip_defs:
            btn = _chip_btn(label)
            btn.clicked.connect(lambda _=False, p=prefill, s=send_now: self._on_chip(p, s))
            h.addWidget(btn)

        # Session resume chip (item 1)
        session_path = Path(__file__).parent.parent.parent / "data" / "session.json"
        if session_path.exists():
            resume_btn = _chip_btn("↩ Resume Session")
            resume_btn.setStyleSheet(
                f"QPushButton {{ background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD};"
                f"border-radius: 14px; padding: 4px 12px; color: {ACCENT}; font-size: 12px; }}"
                f"QPushButton:hover {{ background-color: {SURFACE_1}; border-color: {ACCENT}; }}"
            )
            resume_btn.clicked.connect(self._resume_session)
            h.addWidget(resume_btn)

        h.addStretch()
        return chips_widget

    def _build_chat_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # Scroll area for bubbles
        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet(f"QScrollArea {{ background: {APP_BG}; border: none; }}")

        self._chat_inner = QWidget()
        self._chat_inner.setStyleSheet(f"background-color: {APP_BG};")
        self._chat_layout = QVBoxLayout(self._chat_inner)
        self._chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chat_layout.setContentsMargins(32, 12, 32, 12)
        self._chat_layout.setSpacing(12)

        self._chat_scroll.setWidget(self._chat_inner)
        col.addWidget(self._chat_scroll, stretch=1)

        # Thinking indicator (hidden by default)
        self._thinking_frame = self._make_thinking_frame()
        col.addWidget(self._thinking_frame)

        col.addWidget(self._build_input_bar())
        return col

    def _make_thinking_frame(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {SURFACE_1}; border-top: 1px solid {BORDER_SUBTLE};")
        frame.setFixedHeight(0)  # collapsed
        frame.setVisible(False)
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 0, 0, 0)
        lbl = QLabel("  ⟳ thinking...")
        lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 12px; font-style: italic; background: transparent;")
        h.addWidget(lbl)
        h.addStretch()
        return frame

    def _build_input_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("InputBar")
        bar.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_1}; border-top: 1px solid {BORDER_SUBTLE}; }}"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask StockX... e.g. Analyse AAPL  (Enter or Ctrl+Enter to send)")
        self._input.setStyleSheet(
            f"QLineEdit {{ background-color: {SURFACE_2}; border: 1px solid {BORDER_INPUT};"
            f"border-radius: 20px; padding: 8px 16px; color: {TEXT_1}; }}"
            f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
        )
        self._input.returnPressed.connect(
            lambda: asyncio.ensure_future(self._send())
        )
        # Ctrl+Enter also sends (item 6)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(
            lambda: asyncio.ensure_future(self._send())
        )

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setObjectName("IconBtn")
        self._stop_btn.setToolTip("Stop analysis")
        self._stop_btn.setFixedSize(32, 32)
        self._stop_btn.setStyleSheet(f"QPushButton {{ color: {NEGATIVE}; background: transparent; border: none; font-size: 18px; }} QPushButton:hover {{ background: {SURFACE_2}; border-radius: 6px; }}")
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._stop_analysis)

        self._send_btn = QPushButton("➤")
        self._send_btn.setObjectName("IconBtn")
        self._send_btn.setToolTip("Send (Enter)")
        self._send_btn.setFixedSize(32, 32)
        self._send_btn.setStyleSheet(f"QPushButton {{ color: {ACCENT}; background: transparent; border: none; font-size: 16px; }} QPushButton:hover {{ background: {SURFACE_2}; border-radius: 6px; }}")
        self._send_btn.clicked.connect(
            lambda: asyncio.ensure_future(self._send())
        )

        h.addWidget(self._input, stretch=1)
        h.addWidget(self._stop_btn)
        h.addWidget(self._send_btn)
        return bar

    def _build_history_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(280)
        panel.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_1}; border-left: 1px solid {BORDER_SUBTLE}; }}"
        )
        panel.setVisible(False)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE};")
        hdr.setFixedHeight(40)
        hdr_h = QHBoxLayout(hdr)
        hdr_h.setContentsMargins(10, 0, 10, 0)
        title = QLabel("History")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 13px; font-weight: 600;")
        close_btn = QPushButton("✕")
        close_btn.setObjectName("IconBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self._toggle_history)
        hdr_h.addWidget(title)
        hdr_h.addStretch()
        hdr_h.addWidget(close_btn)
        layout.addWidget(hdr)

        # Scroll area for history cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {SURFACE_1}; border: none; }}")

        self._history_inner = QWidget()
        self._history_inner.setStyleSheet(f"background-color: {SURFACE_1};")
        self._history_layout = QVBoxLayout(self._history_inner)
        self._history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._history_layout.setContentsMargins(8, 8, 8, 8)
        self._history_layout.setSpacing(6)

        scroll.setWidget(self._history_inner)
        layout.addWidget(scroll, stretch=1)
        return panel

    # ── Public API ────────────────────────────────────────────────────────

    def set_input(self, text: str) -> None:
        self._input.setText(text)
        self._input.setFocus()

    def update_provider_label(self, text: str) -> None:
        self._provider_label.setText(text)

    # ── Bubble helpers ────────────────────────────────────────────────────

    def _add_bubble(self, text: str, is_user: bool) -> QLabel:
        """Append a chat bubble and return its QLabel for streaming updates."""
        row = QWidget()
        row.setStyleSheet(f"background: transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(0)

        bubble = QFrame()
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(14, 10, 14, 10)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(f"color: {TEXT_1}; font-size: 13px; background: transparent; border: none;")
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        inner.addWidget(label)

        if is_user:
            bubble.setStyleSheet(
                "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 #9A7B2F, stop:1 #C09635);"
                "border-radius: 18px; border-bottom-right-radius: 4px; }"
            )
            h.addSpacing(80)
            h.addWidget(bubble)
            h.addSpacing(8)
        else:
            bubble.setStyleSheet(
                f"QFrame {{ background-color: {SURFACE_2};"
                "border-radius: 18px; border-top-left-radius: 4px; }"
            )
            h.addSpacing(8)
            h.addWidget(bubble)
            h.addSpacing(80)

        self._chat_layout.addWidget(row)
        QTimer.singleShot(60, self._scroll_to_bottom)
        return label

    def _add_table_bubble(self, rows_data: list) -> None:
        """Add a comparison DataTable wrapped in an agent bubble."""

        def _fmt_mcap(v) -> str:
            if v is None: return "—"
            if v >= 1e12: return f"${v/1e12:.2f}T"
            if v >= 1e9:  return f"${v/1e9:.2f}B"
            if v >= 1e6:  return f"${v/1e6:.2f}M"
            return f"${v:,.0f}"

        headers = ["Ticker", "Price", "1D %", "RSI", "P/E", "Mkt Cap"]
        tbl = QTableWidget(len(rows_data), len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        tbl.setShowGrid(True)
        tbl.setFixedHeight(min(44 * len(rows_data) + 36, 300))

        for r, (t, price, chg, rsi, pe, mcap) in enumerate(rows_data):
            chg_color  = POSITIVE if (chg or 0) >= 0 else NEGATIVE
            rsi_color  = NEGATIVE if (rsi or 50) >= 70 else (POSITIVE if (rsi or 50) <= 30 else TEXT_1)
            sign = "+" if (chg or 0) >= 0 else ""

            values = [
                (t,                                       ACCENT,    True),
                (f"${price:.2f}" if price else "—",      TEXT_1,    False),
                (f"{sign}{chg:.2f}%" if chg is not None else "—", chg_color, False),
                (f"{rsi:.1f}" if rsi is not None else "—",        rsi_color, False),
                (f"{pe:.1f}" if pe is not None else "—",          TEXT_2,    False),
                (_fmt_mcap(mcap),                         TEXT_2,    False),
            ]
            for c, (txt, color, bold) in enumerate(values):
                item = QTableWidgetItem(txt)
                item.setForeground(QColor(color))
                if bold:
                    from PyQt6.QtGui import QFont
                    f = item.font(); f.setBold(True); item.setFont(f)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                tbl.setItem(r, c, item)

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(row_w)
        h.setContentsMargins(0, 2, 0, 2)

        bubble = QFrame()
        bubble.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2};"
            "border-radius: 18px; border-top-left-radius: 4px; }"
        )
        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(8, 8, 8, 8)
        b_layout.addWidget(tbl)

        h.addSpacing(8)
        h.addWidget(bubble)
        h.addSpacing(80)

        self._chat_layout.addWidget(row_w)
        QTimer.singleShot(60, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        sb = self._chat_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _rebuild_messages(self) -> None:
        # Clear layout
        while self._chat_layout.count():
            child = self._chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for msg in self._state.conversation:
            self._add_bubble(msg.content, msg.role == "user")

    # ── Chip handler ──────────────────────────────────────────────────────

    def _on_chip(self, prefill: str, send_now: bool) -> None:
        self._input.setText(prefill)
        if send_now:
            asyncio.ensure_future(self._send_text(prefill))
        else:
            self._input.setFocus()

    # ── History panel ─────────────────────────────────────────────────────

    def _toggle_history(self) -> None:
        self._state.load_analysis_history()
        self._load_history_panel()
        self._history_panel_visible = not self._history_panel_visible
        self._history_panel.setVisible(self._history_panel_visible)

    def _load_history_panel(self) -> None:
        while self._history_layout.count():
            child = self._history_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for entry in self._state.analysis_history:
            card = self._make_history_card(entry)
            self._history_layout.addWidget(card)

    def _make_history_card(self, entry: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2}; border-radius: 8px; }}"
            f"QFrame:hover {{ background-color: #222226; }}"
        )
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        preview = QLabel(entry["preview"])
        preview.setStyleSheet(f"color: {TEXT_1}; font-size: 12px; background: transparent; border: none;")
        preview.setWordWrap(True)

        ts_str = entry.get("ts", "")[:16].replace("T", " ")
        ts_lbl = QLabel(ts_str)
        ts_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")

        layout.addWidget(preview)
        layout.addWidget(ts_lbl)

        card.mousePressEvent = lambda _ev, e=entry: self._on_history_click(e)
        return card

    def _on_history_click(self, entry: dict) -> None:
        user_msg  = Message(id=entry["id"] + "_u", role="user",  content=entry["query"])
        agent_msg = Message(id=entry["id"] + "_a", role="agent", content=entry["response"])
        self._state.conversation.append(user_msg)
        self._state.conversation.append(agent_msg)
        self._add_bubble(entry["query"],    is_user=True)
        self._add_bubble(entry["response"], is_user=False)

    # ── Chat actions ──────────────────────────────────────────────────────

    def _clear_chat(self) -> None:
        self._state.clear_conversation()
        self._rebuild_messages()

    def _export_chat(self) -> None:
        if not self._state.conversation:
            self._mw.show_status("Nothing to export.", 3000)
            return
        _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = _EXPORTS_DIR / f"analysis_{ts}.md"
        lines = [f"# StockX Analysis\n_Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n---\n"]
        for msg in self._state.conversation:
            if msg.role == "user":
                lines.append(f"\n**You:** {msg.content}\n")
            else:
                lines.append(f"\n**StockX:** {msg.content}\n\n---\n")
        filepath.write_text("\n".join(lines), encoding="utf-8")
        self._mw.show_status(f"Exported to data/exports/analysis_{ts}.md", 5000)

    def _resume_session(self) -> None:
        """Reload persisted session into the chat view (item 1)."""
        if self._state.load_session():
            self._rebuild_messages()
            self._mw.show_status("Session restored.", 3000)
        else:
            self._mw.show_status("No saved session found.", 3000)

    def _export_pdf(self) -> None:
        """Export current conversation to PDF (item 9)."""
        if not self._state.conversation:
            self._mw.show_status("Nothing to export.", 3000)
            return
        try:
            from PyQt6.QtPrintSupport import QPrinter
            from PyQt6.QtGui import QTextDocument
            _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(_EXPORTS_DIR / f"analysis_{ts}.pdf")

            printer = QPrinter()
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)

            doc = QTextDocument()
            lines = [f"# StockX Analysis\n_Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n---\n"]
            for msg in self._state.conversation:
                if msg.is_streaming:
                    continue
                role = "You" if msg.role == "user" else "Agent"
                # Strip SCORE_CARD sentinel if present
                content = "\n".join(
                    line for line in msg.content.splitlines()
                    if not line.startswith("SCORE_CARD:")
                )
                lines.append(f"\n**{role}:** {content}\n\n---\n")
            doc.setMarkdown("\n".join(lines))
            doc.print(printer)
            self._mw.show_status(f"PDF saved → {path}", 5000)
        except Exception as exc:
            self._mw.show_status(f"PDF export failed: {exc}", 5000)

    def _insert_score_card(self, data: dict) -> None:
        """Insert a compact score card widget into the chat layout (item 3)."""
        tech  = data.get("tech", 0)
        fund  = data.get("fund", 0)
        risk  = data.get("risk", 0)
        total = data.get("total", 0)
        rating = data.get("rating", "")

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2};"
            f"border-radius: 10px; margin: 4px 8px 4px 8px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Rating badge
        rating_color = (
            ACCENT if "BUY" in rating and "STRONG" not in rating
            else POSITIVE if "STRONG" in rating
            else TEXT_2 if "HOLD" in rating or "WATCH" in rating
            else NEGATIVE
        )
        badge = QLabel(f"  {rating}  ")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: #000; background-color: {rating_color}; border-radius: 8px;"
            f"font-weight: 700; font-size: 12px; padding: 3px 8px;"
        )
        badge.setFixedHeight(26)

        def _score_row(label: str, value: int, max_val: int, color: str) -> QWidget:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            lbl = QLabel(f"{label}: {value:+d}" if label == "Risk" else f"{label}: {value}")
            lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 11px; min-width: 100px; background: transparent;")
            bar = QProgressBar()
            bar.setRange(0, max(max_val, 1))
            bar.setValue(max(0, value))
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {SURFACE_1}; border-radius: 3px; border: none; }}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
            )
            h.addWidget(lbl)
            h.addWidget(bar, stretch=1)
            return row

        layout.addWidget(badge)
        layout.addWidget(_score_row("Technical", tech, 20, ACCENT_CYAN))
        layout.addWidget(_score_row("Fundamental", fund, 25, ACCENT))
        layout.addWidget(_score_row("Risk", risk + 5, 10, POSITIVE if risk >= 0 else NEGATIVE))
        layout.addWidget(_score_row("Total", total, 45, rating_color))

        # Wrap in same left-aligned row as agent bubbles
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(row_w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addSpacing(8)
        h.addWidget(card)
        h.addSpacing(80)

        self._chat_layout.addWidget(row_w)
        QTimer.singleShot(60, self._scroll_to_bottom)

    def _stop_analysis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()

    def _set_busy(self, busy: bool) -> None:
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        self._stop_btn.setVisible(busy)
        if busy:
            self._thinking_frame.setFixedHeight(36)
            self._thinking_frame.setVisible(True)
        else:
            self._thinking_frame.setFixedHeight(0)
            self._thinking_frame.setVisible(False)

    # ── Core send logic ───────────────────────────────────────────────────

    async def _send_text(self, text: str) -> None:
        if not text.strip() or self._state.is_busy:
            return
        self._input.setText("")
        await self._run_query(text.strip())

    async def _send(self) -> None:
        text = self._input.text().strip()
        if not text or self._state.is_busy:
            return
        self._input.setText("")
        await self._run_query(text)

    async def _run_query(self, text: str) -> None:
        # ── Compare shortcut ──────────────────────────────────────────────
        if text.lower().startswith("compare "):
            rest  = text[len("compare "):].strip()
            parts = [p.strip().upper() for p in rest.split(",")]
            if len(parts) >= 2:
                user_msg = self._state.add_display_user(text)
                self._add_bubble(user_msg.content, is_user=True)
                try:
                    await self._run_compare(parts)
                    return
                except Exception as exc:
                    self._add_bubble(f"Compare failed: {exc}\nTry asking the agent instead.", is_user=False)
                    return

        # Guard: agent still initializing
        if self._state.agent is None:
            self._add_bubble("Agent is still initializing — please wait a moment.", is_user=False)
            return

        self._state.is_busy = True
        self._set_busy(True)

        user_msg = self._state.add_display_user(text)
        self._add_bubble(user_msg.content, is_user=True)

        agent_msg = self._state.add_display_agent_placeholder()
        agent_label = self._add_bubble("", is_user=False)
        self._streaming_label = agent_label
        self._thinking_frame.setFixedHeight(0)
        self._thinking_frame.setVisible(False)

        chunk_counter = [0]

        # ── Signal handlers — called on main thread via Qt queued connection ──

        def _on_chunk(chunk: str) -> None:
            agent_msg.content += chunk
            try:
                if self._streaming_label is not None:
                    self._streaming_label.setText(agent_msg.content)
            except RuntimeError:
                self._streaming_label = None
            chunk_counter[0] += 1
            if chunk_counter[0] % 6 == 0:
                self._scroll_to_bottom()

        def _on_done(final_text: str) -> None:
            # Extract and strip SCORE_CARD sentinel (item 3)
            score_data: dict | None = None
            clean_lines = []
            for line in final_text.splitlines():
                if line.startswith("SCORE_CARD:"):
                    try:
                        score_data = json.loads(line[len("SCORE_CARD:"):])
                    except Exception:
                        pass
                else:
                    clean_lines.append(line)
            display_text = "\n".join(clean_lines)

            agent_msg.content      = display_text
            agent_msg.is_streaming = False
            try:
                if self._streaming_label is not None:
                    self._streaming_label.setText(display_text)
            except RuntimeError:
                pass
            if score_data:
                self._insert_score_card(score_data)
            self._state.commit_to_history(text, display_text)
            self._state.save_history_entry(text, display_text)
            _cleanup()

        def _on_error(err: str) -> None:
            msg = f"Error: {err}"
            agent_msg.content = msg
            try:
                if self._streaming_label is not None:
                    self._streaming_label.setText(msg)
            except RuntimeError:
                pass
            _cleanup()

        def _on_cancelled() -> None:
            stopped = agent_msg.content.rstrip() + "\n\n[Analysis stopped]"
            agent_msg.content = stopped
            try:
                if self._streaming_label is not None:
                    self._streaming_label.setText(stopped)
            except RuntimeError:
                pass
            _cleanup()

        def _cleanup() -> None:
            try:
                self._worker.chunk_received.disconnect(_on_chunk)
                self._worker.finished.disconnect(_on_done)
                self._worker.error.disconnect(_on_error)
                self._worker.cancelled.disconnect(_on_cancelled)
            except (RuntimeError, TypeError):
                pass
            self._state.is_busy   = False
            self._streaming_label = None
            self._set_busy(False)
            try:
                self._provider_label.setText(self._state.detect_provider())
            except RuntimeError:
                pass
            self._scroll_to_bottom()

        # ── Worker thread: own asyncio event loop, signals back to main thread ──
        self._worker = AnalysisWorker(self._state.agent, text, list(self._state.history))
        self._worker.chunk_received.connect(_on_chunk)
        self._worker.finished.connect(_on_done)
        self._worker.error.connect(_on_error)
        self._worker.cancelled.connect(_on_cancelled)
        self._worker.start()

    async def _run_compare(self, tickers: list[str]) -> None:
        import yfinance as yf

        def _fetch_all():
            rows = []
            for t in tickers:
                try:
                    obj  = yf.Ticker(t)
                    fi   = obj.fast_info
                    info = obj.info
                    hist = obj.history(period="1mo")
                    price = float(fi.last_price or 0)
                    prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
                    chg   = ((price - prev) / prev * 100) if prev else 0.0
                    delta  = hist["Close"].diff()
                    gains  = delta.clip(lower=0).rolling(14).mean()
                    losses = (-delta.clip(upper=0)).rolling(14).mean()
                    rsi    = float((100 - 100 / (1 + gains / losses)).iloc[-1])
                    pe     = info.get("trailingPE") or info.get("forwardPE")
                    mcap   = fi.market_cap or 0
                    rows.append((t, price, chg, rsi, pe, mcap))
                except Exception:
                    rows.append((t, None, None, None, None, None))
            return rows

        rows_data = await asyncio.get_event_loop().run_in_executor(None, _fetch_all)
        self._add_table_bubble(rows_data)
