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
    QPushButton, QScrollArea, QSlider,
    QVBoxLayout, QWidget, QSizePolicy,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, NEGATIVE, POSITIVE,
    SURFACE_2, SURFACE_3, TEXT_1, TEXT_2, TEXT_MUTED,
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
        body_layout.setContentsMargins(32, 16, 32, 16)
        body_layout.setSpacing(0)

        # ── API Keys card ─────────────────────────────────────────────────
        nvidia_row,    self._nvidia_f    = self._key_field("NVIDIA API Key",    "NVIDIA_API_KEY")
        anthropic_row, self._anthropic_f = self._key_field("Anthropic API Key", "ANTHROPIC_API_KEY")
        openai_row,    self._openai_f    = self._key_field("OpenAI API Key",    "OPENAI_API_KEY")

        body_layout.addWidget(self._section_card("LLM Providers", [
            nvidia_row, anthropic_row, openai_row,
        ]))
        body_layout.addSpacing(16)

        # ── Search card ───────────────────────────────────────────────────
        search_row, self._search_f = self._key_field("Search API Key", "SEARCH_API_KEY")

        # _search_row_widget() sets self._provider_dd with proper item data
        body_layout.addWidget(self._section_card("Search", [
            self._search_row_widget(), search_row,
        ]))
        body_layout.addSpacing(16)

        # ── Research Data card ────────────────────────────────────────────
        fred_row, self._fred_f = self._key_field("FRED API Key (free — stlouisfed.org)", "FRED_API_KEY")
        eia_row,  self._eia_f  = self._key_field("EIA API Key (free — eia.gov)", "EIA_API_KEY")
        body_layout.addWidget(self._section_card("Research Data", [fred_row, eia_row]))
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

        # ── Commodity Alerts card ─────────────────────────────────────────
        self._commodity_enabled_dd = QComboBox()
        for key, text in [("true", "Enabled"), ("false", "Disabled")]:
            self._commodity_enabled_dd.addItem(text, key)
        if not self._state.commodity_alert_enabled:
            self._commodity_enabled_dd.setCurrentIndex(1)

        commodity_threshold_row = QWidget()
        commodity_threshold_row.setStyleSheet("background: transparent;")
        ct_h = QHBoxLayout(commodity_threshold_row)
        ct_h.setContentsMargins(0, 0, 0, 0)
        ct_h.setSpacing(12)

        self._commodity_threshold_lbl = QLabel(
            f"Threshold: {self._state.commodity_alert_threshold:.1f}%"
        )
        self._commodity_threshold_lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 13px; min-width: 120px;")
        self._commodity_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._commodity_threshold_slider.setMinimum(2)   # 1.0%
        self._commodity_threshold_slider.setMaximum(20)  # 10.0%
        self._commodity_threshold_slider.setValue(int(self._state.commodity_alert_threshold * 2))
        self._commodity_threshold_slider.setTickInterval(1)
        self._commodity_threshold_slider.valueChanged.connect(
            lambda v: self._commodity_threshold_lbl.setText(f"Threshold: {v / 2:.1f}%")
        )

        ct_h.addWidget(self._commodity_threshold_slider, stretch=1)
        ct_h.addWidget(self._commodity_threshold_lbl)

        body_layout.addWidget(self._section_card("Commodity Alerts", [
            self._commodity_enabled_dd, commodity_threshold_row,
        ]))
        body_layout.addSpacing(16)

        # ── Save row ──────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("AccentBtn")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(lambda: asyncio.get_event_loop().create_task(self._save()))

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setFixedHeight(38)
        self._test_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none;"
            f"border-radius: 10px; padding: 6px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
            f"QPushButton:disabled {{ color: {TEXT_MUTED}; }}"
        )
        self._test_btn.clicked.connect(
            lambda: asyncio.get_event_loop().create_task(self._test_connection())
        )

        self._save_status = QLabel("")
        self._save_status.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")
        save_row.addWidget(save_btn)
        save_row.addWidget(self._test_btn)
        save_row.addWidget(self._save_status)
        save_row.addStretch()

        body_layout.addLayout(save_row)
        body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h = QHBoxLayout(header)
        h.setContentsMargins(32, 20, 32, 8)
        h.setSpacing(12)

        title = QLabel("Settings")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 24px; font-weight: 700;")
        h.addWidget(title)
        h.addStretch()
        return header

    def _key_field(self, placeholder: str, env_key: str) -> tuple[QWidget, QLineEdit]:
        """Returns (row_widget, line_edit) — row has the field + show/hide toggle."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setText(os.environ.get(env_key, ""))
        field.setEchoMode(QLineEdit.EchoMode.Password)

        toggle_btn = QPushButton("Show")
        toggle_btn.setCheckable(True)
        toggle_btn.setFixedWidth(48)
        toggle_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        toggle_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_MUTED}; background: transparent; border: none;"
            f"font-size: 11px; padding: 0; }}"
            f"QPushButton:hover {{ color: {TEXT_2}; }}"
            f"QPushButton:checked {{ color: {ACCENT}; }}"
        )

        def _toggle(checked: bool) -> None:
            field.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
            toggle_btn.setText("Hide" if checked else "Show")

        toggle_btn.toggled.connect(_toggle)
        h.addWidget(field, stretch=1)
        h.addWidget(toggle_btn)
        return row, field

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
            f"QFrame#Card {{ background-color: {SURFACE_2}; border-radius: 14px; border: none; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        # Section label
        section_lbl = QLabel(title.upper())
        section_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
            f"background: transparent;"
        )
        layout.addWidget(section_lbl)
        layout.addSpacing(4)

        for w in widgets:
            layout.addWidget(w)

        return card

    # ── Handlers ──────────────────────────────────────────────────────────

    def _on_slider_change(self, value: int) -> None:
        self._steps_lbl.setText(f"Max Steps: {value}")

    async def _test_connection(self) -> None:
        """Ping the active provider with a minimal 1-token request."""
        import httpx

        self._test_btn.setEnabled(False)
        self._test_btn.setText("Testing…")
        self._save_status.setText("")

        provider = self._state.detect_provider()
        nvidia_key     = self._nvidia_f.text().strip()
        anthropic_key  = self._anthropic_f.text().strip()
        openai_key     = self._openai_f.text().strip()

        ok = False
        detail = ""
        try:
            loop = asyncio.get_running_loop()
            if "NVIDIA" in provider and nvidia_key:
                def _ping_nvidia():
                    r = httpx.post(
                        "https://integrate.api.nvidia.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"},
                        json={"model": "meta/llama-3.1-70b-instruct", "max_tokens": 1,
                              "messages": [{"role": "user", "content": "hi"}]},
                        timeout=10,
                    )
                    return r.status_code
                status = await loop.run_in_executor(None, _ping_nvidia)
                ok = status == 200
                detail = f"NVIDIA ({status})"

            elif "Anthropic" in provider and anthropic_key:
                def _ping_anthropic():
                    r = httpx.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": anthropic_key, "anthropic-version": "2023-06-01",
                                 "content-type": "application/json"},
                        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
                              "messages": [{"role": "user", "content": "hi"}]},
                        timeout=10,
                    )
                    return r.status_code
                status = await loop.run_in_executor(None, _ping_anthropic)
                ok = status == 200
                detail = f"Anthropic ({status})"

            elif "OpenAI" in provider and openai_key:
                def _ping_openai():
                    r = httpx.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                        json={"model": "gpt-4o-mini", "max_tokens": 1,
                              "messages": [{"role": "user", "content": "hi"}]},
                        timeout=10,
                    )
                    return r.status_code
                status = await loop.run_in_executor(None, _ping_openai)
                ok = status == 200
                detail = f"OpenAI ({status})"
            else:
                detail = "No provider configured — save API keys first"
        except Exception as exc:
            detail = str(exc)[:60]

        if ok:
            self._save_status.setText(f"Connected — {detail}")
            self._save_status.setStyleSheet(f"color: {POSITIVE}; font-size: 12px;")
        else:
            self._save_status.setText(f"Failed — {detail}")
            self._save_status.setStyleSheet(f"color: {NEGATIVE}; font-size: 12px;")

        self._test_btn.setEnabled(True)
        self._test_btn.setText("Test Connection")

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
                ("FRED_API_KEY",            self._fred_f.text().strip()),
                ("EIA_API_KEY",             self._eia_f.text().strip()),
            ]

            # Update alert interval on state immediately
            try:
                self._state.alert_interval_minutes = int(self._alert_interval_dd.currentData() or "15")
            except ValueError:
                pass

            # Update commodity alert settings
            self._state.commodity_alert_enabled = (
                self._commodity_enabled_dd.currentData() == "true"
            )
            self._state.commodity_alert_threshold = self._commodity_threshold_slider.value() / 2.0
            self._state.save_commodity_state()

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
