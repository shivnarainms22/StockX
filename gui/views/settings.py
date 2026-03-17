"""
StockX GUI — Settings view (PyQt6).
Edit API keys and agent parameters; persists to .env file.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QSlider,
    QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, BORDER_CARD, BORDER_SUBTLE, NEGATIVE, POSITIVE,
    SURFACE_1, SURFACE_2, TEXT_1, TEXT_2, TEXT_MUTED,
)

if TYPE_CHECKING:
    from gui.app import MainWindow

_DOTENV_PATH = Path(__file__).parent.parent.parent / ".env"


class SettingsView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw    = main_window
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(40, 24, 40, 24)
        body_layout.setSpacing(0)

        # ── API Keys card ─────────────────────────────────────────────────
        self._nvidia_f    = self._key_field("NVIDIA API Key",    "NVIDIA_API_KEY")
        self._anthropic_f = self._key_field("Anthropic API Key", "ANTHROPIC_API_KEY")
        self._openai_f    = self._key_field("OpenAI API Key",    "OPENAI_API_KEY")

        body_layout.addWidget(self._section_card("LLM Providers", [
            self._nvidia_f, self._anthropic_f, self._openai_f,
        ]))
        body_layout.addSpacing(16)

        # ── Search card ───────────────────────────────────────────────────
        self._search_f = self._key_field("Search API Key", "SEARCH_API_KEY")

        # _search_row_widget() sets self._provider_dd with proper item data
        body_layout.addWidget(self._section_card("Search", [
            self._search_row_widget(), self._search_f,
        ]))
        body_layout.addSpacing(16)

        # ── Agent card ────────────────────────────────────────────────────
        slider_row = QHBoxLayout()
        slider_row.setSpacing(12)

        initial_steps = float(os.environ.get("AGENT_MAX_STEPS", "12"))
        self._steps_lbl = QLabel(f"Max Steps: {int(initial_steps)}")
        self._steps_lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 13px; min-width: 110px;")
        self._steps_slider = QSlider(Qt.Orientation.Horizontal)
        self._steps_slider.setMinimum(1)
        self._steps_slider.setMaximum(30)
        self._steps_slider.setValue(int(initial_steps))
        self._steps_slider.setTickInterval(1)
        self._steps_slider.valueChanged.connect(self._on_slider_change)

        self._context_f = QLineEdit(os.environ.get("AGENT_MAX_CONTEXT_TOKENS", "102400"))
        self._context_f.setPlaceholderText("Max Context Tokens")

        slider_widget = QWidget()
        slider_widget.setStyleSheet("background: transparent;")
        slider_h = QHBoxLayout(slider_widget)
        slider_h.setContentsMargins(0, 0, 0, 0)
        slider_h.setSpacing(12)
        slider_h.addWidget(self._steps_slider, stretch=1)
        slider_h.addWidget(self._steps_lbl)

        body_layout.addWidget(self._section_card("Agent", [slider_widget, self._context_f]))
        body_layout.addSpacing(16)

        # ── Watchlist card ────────────────────────────────────────────────
        self._refresh_interval_dd = self._interval_combo(
            str(self._state.watchlist_refresh_interval),
            [("0", "Off"), ("5", "Every 5 minutes"), ("15", "Every 15 minutes"),
             ("30", "Every 30 minutes"), ("60", "Every 60 minutes")],
        )
        body_layout.addWidget(self._section_card("Watchlist Auto-Refresh", [self._refresh_interval_dd]))
        body_layout.addSpacing(16)

        # ── Alerts card ───────────────────────────────────────────────────
        self._alert_interval_dd = self._interval_combo(
            str(self._state.alert_interval_minutes),
            [("5", "Every 5 minutes"), ("15", "Every 15 minutes"),
             ("30", "Every 30 minutes"), ("60", "Every 60 minutes")],
        )
        body_layout.addWidget(self._section_card("Alert Check Interval", [self._alert_interval_dd]))
        body_layout.addSpacing(16)

        # ── Save row ──────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setObjectName("AccentBtn")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(self._save()))

        self._save_status = QLabel("")
        self._save_status.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")
        save_row.addWidget(save_btn)
        save_row.addWidget(self._save_status)
        save_row.addStretch()

        body_layout.addLayout(save_row)
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
        icon  = QLabel("⚙")
        icon.setStyleSheet("font-size: 18px;")
        title = QLabel("Settings")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {TEXT_1};")
        h.addWidget(icon)
        h.addWidget(title)
        h.addStretch()
        return bar

    def _key_field(self, placeholder: str, env_key: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setText(os.environ.get(env_key, ""))
        field.setEchoMode(QLineEdit.EchoMode.Password)

        # Show/hide toggle handled by wrapping in a container is complex;
        # just provide the field — user can use eye button via system
        return field

    def _search_row_widget(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        lbl = QLabel("Search Provider")
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._provider_dd = QComboBox()
        for key, text in [("brave", "Brave Search"), ("tavily", "Tavily")]:
            self._provider_dd.addItem(text, key)
        current = os.environ.get("SEARCH_PROVIDER", "brave")
        for i in range(self._provider_dd.count()):
            if self._provider_dd.itemData(i) == current:
                self._provider_dd.setCurrentIndex(i)
        h.addWidget(lbl)
        h.addWidget(self._provider_dd)
        h.addStretch()
        return w

    def _interval_combo(self, current_val: str, options: list[tuple[str, str]]) -> QComboBox:
        dd = QComboBox()
        for key, text in options:
            dd.addItem(text, key)
        for i in range(dd.count()):
            if dd.itemData(i) == current_val:
                dd.setCurrentIndex(i)
                break
        return dd

    def _section_card(self, title: str, widgets: list[QWidget]) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setStyleSheet(
            f"QFrame#Card {{ background-color: {SURFACE_1}; border-radius: 12px;"
            f"border: 1px solid {BORDER_SUBTLE}; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Section label
        section_lbl = QLabel(title.upper())
        section_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px;"
            f"border-left: 3px solid {ACCENT}; padding-left: 8px; background: transparent;"
        )
        layout.addWidget(section_lbl)
        layout.addSpacing(4)

        for w in widgets:
            layout.addWidget(w)

        return card

    # ── Handlers ──────────────────────────────────────────────────────────

    def _on_slider_change(self, value: int) -> None:
        self._steps_lbl.setText(f"Max Steps: {value}")

    async def _save(self) -> None:
        from dotenv import set_key

        self._save_status.setText("Saving...")
        self._save_status.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")

        try:
            pairs = [
                ("NVIDIA_API_KEY",           self._nvidia_f.text().strip()),
                ("ANTHROPIC_API_KEY",        self._anthropic_f.text().strip()),
                ("OPENAI_API_KEY",           self._openai_f.text().strip()),
                ("SEARCH_PROVIDER",          self._provider_dd.currentData() or "brave"),
                ("SEARCH_API_KEY",           self._search_f.text().strip()),
                ("AGENT_MAX_STEPS",          str(self._steps_slider.value())),
                ("AGENT_MAX_CONTEXT_TOKENS", self._context_f.text().strip() or "102400"),
            ]

            # Update alert interval on state immediately
            try:
                self._state.alert_interval_minutes = int(self._alert_interval_dd.currentData() or "15")
            except ValueError:
                pass

            # Update watchlist auto-refresh interval
            try:
                self._state.watchlist_refresh_interval = int(self._refresh_interval_dd.currentData() or "0")
            except ValueError:
                pass
            set_key(str(_DOTENV_PATH), "WATCHLIST_REFRESH_INTERVAL",
                    str(self._state.watchlist_refresh_interval))

            for key, val in pairs:
                if val:
                    set_key(str(_DOTENV_PATH), key, val)
                    os.environ[key] = val

            # Re-initialize agent to pick up new keys
            loop = asyncio.get_running_loop()
            from agent.core import AgentCore
            self._state.agent = await loop.run_in_executor(None, AgentCore)

            provider = self._state.detect_provider()
            self._save_status.setText(f"Saved — active: {provider}")
            self._save_status.setStyleSheet(f"color: {POSITIVE}; font-size: 12px;")

            # Update provider label in analysis view
            self._mw._analysis_view.update_provider_label(provider)
            self._mw.show_status(f"Settings saved — {provider}", 4000)

        except Exception as exc:
            self._save_status.setText(f"Error: {exc}")
            self._save_status.setStyleSheet(f"color: {NEGATIVE}; font-size: 12px;")
