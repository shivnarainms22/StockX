"""StockX GUI — Backtest view (PyQt6).

Run a technical strategy over a single ticker's history and show the equity
curve vs buy-and-hold plus a metrics tearsheet. Compute runs off the UI thread
in a sync QThread (no asyncio loop needed).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import NEGATIVE, POSITIVE, SURFACE_2, TEXT_1, TEXT_2
from services.backtest import STRATEGIES, run_backtest

if TYPE_CHECKING:
    from gui.app import MainWindow

_PERIODS = ["6mo", "1y", "2y", "5y", "10y", "max"]


def _build_strategy(name: str, params: dict):
    factory, _ = STRATEGIES[name]
    return factory(**params)


def _parse_params(text: str, defaults: dict) -> dict:
    """Parse 'fast=20, slow=50' into a kwargs dict, coercing to default types."""
    out = dict(defaults)
    for part in text.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k in defaults:
            try:
                out[k] = type(defaults[k])(v)
            except (TypeError, ValueError):
                pass
    return out


def _run_backtest_job(hist, strategy, *, initial_cash: float):
    """Pure: run the backtest and render its chart. Returns (result, png_bytes)."""
    from services.charting import render_equity_curve
    result = run_backtest(hist, strategy, initial_cash=initial_cash)
    png = render_equity_curve(result.equity, result.benchmark_equity)
    return result, png


class BacktestWorker(QThread):
    finished = pyqtSignal(object)   # (BacktestResult, png_bytes)
    error = pyqtSignal(str)

    def __init__(self, ticker: str, strategy, period: str, initial_cash: float) -> None:
        super().__init__()
        self._ticker = ticker
        self._strategy = strategy
        self._period = period
        self._cash = initial_cash

    def run(self) -> None:  # QThread entry-point (sync work)
        try:
            import yfinance as yf
            hist = yf.Ticker(self._ticker).history(period=self._period)
            if hist is None or len(hist) < 2:
                self.error.emit(f"No price data for '{self._ticker}'.")
                return
            self.finished.emit(_run_backtest_job(
                hist, self._strategy, initial_cash=self._cash))
        except Exception as exc:  # surfaced to the UI, never swallowed
            self.error.emit(str(exc))


class BacktestView(QWidget):
    _PERCENT_KEYS = {"total_return", "cagr", "annualized_vol", "max_drawdown",
                     "win_rate", "exposure", "alpha"}
    _LABELS = {
        "total_return": "Total Return", "cagr": "CAGR", "sharpe": "Sharpe",
        "sortino": "Sortino", "max_drawdown": "Max Drawdown", "calmar": "Calmar",
        "annualized_vol": "Volatility", "win_rate": "Win Rate",
        "exposure": "Exposure", "num_trades": "Trades", "alpha": "Alpha",
        "beta": "Beta",
    }

    def __init__(self, state: AppState, main_window: "MainWindow",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw = main_window
        self._worker: BacktestWorker | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("Backtest")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        # ── Controls row ──────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self._ticker = QLineEdit()
        self._ticker.setPlaceholderText("Ticker (e.g. AAPL)")
        self._ticker.setFixedWidth(140)

        self._strategy = QComboBox()
        self._strategy.addItems(list(STRATEGIES))
        self._strategy.currentTextChanged.connect(self._sync_params)

        self._params = QLineEdit()
        self._params.setFixedWidth(220)

        self._period = QComboBox()
        self._period.addItems(_PERIODS)
        self._period.setCurrentText("2y")

        self._cash = QLineEdit("10000")
        self._cash.setFixedWidth(90)

        self._run_btn = QPushButton("Run")
        self._run_btn.setObjectName("PrimaryBtn")
        self._run_btn.clicked.connect(self._on_run)

        for w in (self._ticker, self._strategy, self._params, self._period,
                  self._cash, self._run_btn):
            controls.addWidget(w)
        controls.addStretch()
        root.addLayout(controls)
        self._sync_params(self._strategy.currentText())

        # ── Results area ──────────────────────────────────────────────
        self._status = QLabel("Enter a ticker and run a backtest.")
        self._status.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")
        root.addWidget(self._status)

        self._chart = QLabel()
        self._chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._chart)

        self._metrics = QGridLayout()
        self._metrics.setSpacing(8)
        metrics_frame = QFrame()
        metrics_frame.setLayout(self._metrics)
        root.addWidget(metrics_frame)
        root.addStretch()

    def _sync_params(self, name: str) -> None:
        _, defaults = STRATEGIES[name]
        self._params.setText(", ".join(f"{k}={v}" for k, v in defaults.items()))

    def _on_run(self) -> None:
        ticker = self._ticker.text().strip().upper()
        if not ticker:
            self._status.setText("Enter a ticker first.")
            return
        try:
            cash = float(self._cash.text())
        except ValueError:
            self._status.setText("Initial capital must be a number.")
            return

        name = self._strategy.currentText()
        _, defaults = STRATEGIES[name]
        params = _parse_params(self._params.text(), defaults)
        strategy = _build_strategy(name, params)

        self._run_btn.setEnabled(False)
        self._status.setText(f"Running {name} on {ticker}…")
        self._worker = BacktestWorker(ticker, strategy,
                                      self._period.currentText(), cash)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, payload) -> None:
        result, png = payload
        self._render_metrics(result.metrics)
        if png:
            self._chart.setPixmap(QPixmap.fromImage(QImage.fromData(png)))
        self._status.setText(
            f"Done — {result.metrics['num_trades']} trades, "
            f"{result.metrics['total_return'] * 100:+.1f}% total return."
        )
        self._cleanup()

    def _on_error(self, msg: str) -> None:
        self._status.setText(f"Error: {msg}")
        self._cleanup()

    def _cleanup(self) -> None:
        self._run_btn.setEnabled(True)
        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

    def _render_metrics(self, metrics: dict) -> None:
        while self._metrics.count():
            item = self._metrics.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, (key, label) in enumerate(self._LABELS.items()):
            val = metrics.get(key, 0.0)
            if key in self._PERCENT_KEYS:
                text = f"{val * 100:+.1f}%"
            elif key == "num_trades":
                text = str(val)
            else:
                text = f"{val:.2f}"
            if key == "max_drawdown":
                color = NEGATIVE
            elif isinstance(val, (int, float)) and val > 0:
                color = POSITIVE
            else:
                color = TEXT_1
            card = QFrame()
            card.setStyleSheet(f"background: {SURFACE_2}; border-radius: 8px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 11px;")
            val_lbl = QLabel(text)
            val_lbl.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 600;")
            cl.addWidget(name_lbl)
            cl.addWidget(val_lbl)
            self._metrics.addWidget(card, i // 4, i % 4)
