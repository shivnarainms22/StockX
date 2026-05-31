"""StockX GUI — Portfolio optimization panel (PyQt6)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from gui.theme import NEGATIVE, POSITIVE, TEXT_1, TEXT_2
from services.optimize import fetch_returns, optimize_portfolio

# Cap any single suggested position so the optimizer can't dump everything into
# one name (mean-variance's classic concentration failure).
_MAX_WEIGHT = 0.35


def _run_optimize_job(returns_df, current_weights):
    """Pure: optimize + render. Returns (OptimizeResult, png_bytes)."""
    from services.charting import render_efficient_frontier
    result = optimize_portfolio(
        returns_df, current_weights=current_weights, max_weight=_MAX_WEIGHT)
    return result, render_efficient_frontier(result)


class OptimizeWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, tickers, period, current_weights) -> None:
        super().__init__()
        self._tickers = tickers
        self._period = period
        self._current = current_weights

    def run(self) -> None:
        try:
            df = fetch_returns(self._tickers, self._period)
            if df.shape[1] < 2:
                self.error.emit("Need at least 2 tickers with price history.")
                return
            # Re-align current weights to the tickers that actually returned data.
            cw = None
            if self._current:
                m = dict(zip(self._tickers, self._current))
                vals = [m.get(t, 0.0) for t in df.columns]
                s = sum(vals)
                cw = [v / s for v in vals] if s > 0 else None
            self.finished.emit(_run_optimize_job(df, cw))
        except Exception as exc:
            self.error.emit(str(exc))


class OptimizePanel(QWidget):
    def __init__(self, tickers: list[str], current_weights: list[float] | None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tickers = tickers
        self._current_weights = current_weights
        self._worker: OptimizeWorker | None = None
        self.setWindowTitle("Optimize Portfolio")
        self.resize(720, 620)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("Portfolio Optimization")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 17px; font-weight: 700;")
        root.addWidget(title)

        row = QHBoxLayout()
        self._extra = QLineEdit()
        self._extra.setPlaceholderText("Add tickers (comma-separated), optional")
        self._run = QPushButton("Optimize")
        self._run.setObjectName("PrimaryBtn")
        self._run.clicked.connect(self._on_run)
        row.addWidget(self._extra)
        row.addWidget(self._run)
        root.addLayout(row)

        self._status = QLabel(f"Holdings: {', '.join(self._tickers) or '(none)'}")
        self._status.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")
        root.addWidget(self._status)

        self._chart = QLabel()
        self._chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._chart)

        self._table = QGridLayout()
        self._table.setSpacing(6)
        holder = QWidget()
        holder.setLayout(self._table)
        root.addWidget(holder)
        root.addStretch()

    def _on_run(self) -> None:
        extra = [t.strip().upper() for t in self._extra.text().split(",") if t.strip()]
        tickers = list(dict.fromkeys(self._tickers + extra))  # de-dupe, keep order
        if len(tickers) < 2:
            self._status.setText("Add at least 2 tickers to optimize.")
            return
        self._run.setEnabled(False)
        self._status.setText("Optimizing…")
        self._worker = OptimizeWorker(tickers, "2y", self._current_weights)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, payload) -> None:
        result, png = payload
        if png:
            self._chart.setPixmap(QPixmap.fromImage(QImage.fromData(png)))
        self._render_table(result)
        ms = result.max_sharpe
        self._status.setText(
            f"Max-Sharpe: return {ms['ret'] * 100:.1f}%, vol {ms['vol'] * 100:.1f}%, "
            f"Sharpe {ms['sharpe']:.2f}"
        )
        self._cleanup()

    def _on_error(self, msg: str) -> None:
        self._status.setText(f"Error: {msg}")
        self._cleanup()

    def _cleanup(self) -> None:
        self._run.setEnabled(True)
        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

    def _render_table(self, result) -> None:
        while self._table.count():
            item = self._table.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        headers = ["Ticker", "Current", "Suggested", "Δ"]
        for c, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 11px; font-weight: 600;")
            self._table.addWidget(lbl, 0, c)
        suggested = result.max_sharpe["weights"]
        current = result.current["weights"] if result.current else [0.0] * len(result.tickers)
        for r, t in enumerate(result.tickers, start=1):
            cur, sug = current[r - 1] * 100, suggested[r - 1] * 100
            delta = sug - cur
            color = POSITIVE if delta > 0.05 else NEGATIVE if delta < -0.05 else TEXT_2
            cells = [t, f"{cur:.1f}%", f"{sug:.1f}%", f"{delta:+.1f}%"]
            for c, text in enumerate(cells):
                lbl = QLabel(text)
                col = color if c == 3 else TEXT_1
                lbl.setStyleSheet(f"color: {col}; font-size: 12px;")
                self._table.addWidget(lbl, r, c)
