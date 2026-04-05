"""
StockX GUI — Global Macro view.
Commodity price dashboard, geopolitical scenario analysis (4-tier cascading
impact), market/consumer impact radar, and portfolio cross-reference.
"""
from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget, QProgressBar,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, CAUTION, NEGATIVE, POSITIVE,
    SURFACE_2, SURFACE_3, TEXT_1, TEXT_2, TEXT_MUTED,
)

if TYPE_CHECKING:
    from gui.app import MainWindow

# ── Commodity registry ─────────────────────────────────────��─────────────────

COMMODITY_CATEGORIES: dict[str, dict[str, str]] = {
    "Energy": {
        "WTI Crude":   "CL=F",
        "Brent Crude": "BZ=F",
        "Natural Gas": "NG=F",
        "Heating Oil": "HO=F",
    },
    "Precious Metals": {
        "Gold":      "GC=F",
        "Silver":    "SI=F",
        "Platinum":  "PL=F",
        "Palladium": "PA=F",
    },
    "Industrial Metals": {
        "Copper":    "HG=F",
        "Aluminum":  "ALI=F",
    },
    "Agriculture": {
        "Wheat":    "ZW=F",
        "Corn":     "ZC=F",
        "Soybeans": "ZS=F",
        "Coffee":   "KC=F",
        "Sugar":    "SB=F",
        "Cotton":   "CT=F",
    },
}

# Flat lookup: symbol → display name
_SYMBOL_NAMES: dict[str, str] = {}
for _cat, _items in COMMODITY_CATEGORIES.items():
    for _name, _sym in _items.items():
        _SYMBOL_NAMES[_sym] = _name

# Commodity → affected sectors/tickers for the impact radar
COMMODITY_SECTOR_MAP: dict[str, dict] = {
    "CL=F": {
        "sectors": ["Energy", "Airlines", "Shipping", "Petrochemicals"],
        "tickers": [
            "XLE", "XOP", "CVX", "XOM", "COP", "OXY",          # US producers
            "BP", "SHEL", "TTE", "EQNR",                        # EU producers
            "RELIANCE.NS", "ONGC.NS",                            # India
            "JETS", "DAL", "UAL", "AAL", "FDX", "UPS",          # US consumers
        ],
    },
    "BZ=F": {
        "sectors": ["Energy", "Airlines", "Shipping"],
        "tickers": [
            "XLE", "CVX", "XOM",                                 # US
            "BP", "SHEL", "TTE", "EQNR",                        # EU
            "2222.SR",                                            # Saudi Aramco
            "JETS",
        ],
    },
    "NG=F": {
        "sectors": ["Utilities", "Fertilizer", "Chemicals"],
        "tickers": [
            "UNG", "LNG", "AR", "EQT",                          # US producers
            "MOS", "NTR", "CF", "XLU",                           # US consumers
            "GAIL.NS",                                            # India
        ],
    },
    "HO=F": {
        "sectors": ["Heating", "Transport", "Logistics"],
        "tickers": ["XLE", "FDX", "UPS", "JBHT"],
    },
    "GC=F": {
        "sectors": ["Gold Miners", "Precious Metals", "Safe Haven"],
        "tickers": [
            "GLD", "GDX", "GDXJ", "NEM", "GOLD", "AEM", "KGC", # US/Canada
            "NST.AX", "EVN.AX",                                  # Australia
        ],
    },
    "SI=F": {
        "sectors": ["Silver Miners", "Solar", "Electronics"],
        "tickers": ["SLV", "SIL", "PAAS", "AG", "MAG", "HL"],
    },
    "PL=F": {
        "sectors": ["Automotive", "Catalysts"],
        "tickers": ["IMPUY", "SBSW", "AMS.JO"],                 # + SA
    },
    "PA=F": {
        "sectors": ["Automotive", "Catalysts"],
        "tickers": ["SBSW", "IMPUY", "AMS.JO"],
    },
    "HG=F": {
        "sectors": ["Copper Miners", "EVs", "Construction"],
        "tickers": [
            "FCX", "SCCO", "TECK", "COPX",                      # US/Americas
            "BHP", "RIO",                                         # Australia/UK
            "TSLA", "RIVN",                                       # EV consumers
            "HINDCOPPER.NS",                                      # India
        ],
    },
    "ALI=F": {
        "sectors": ["Aluminum", "Construction", "Packaging"],
        "tickers": [
            "AA", "CENX", "BLL",                                 # US
            "HINDALCO.NS",                                        # India
        ],
    },
    "ZW=F": {
        "sectors": ["Agriculture", "Food Production", "Farm Equipment"],
        "tickers": [
            "ADM", "BG", "CTVA", "MOS", "NTR", "DE",           # US/Canada
        ],
    },
    "ZC=F": {
        "sectors": ["Agriculture", "Ethanol", "Livestock Feed"],
        "tickers": ["ADM", "BG", "DE", "CTVA"],
    },
    "ZS=F": {
        "sectors": ["Agriculture", "Food Processing"],
        "tickers": [
            "ADM", "BG", "DAR",                                  # US
        ],
    },
    "KC=F": {
        "sectors": ["Consumer Staples", "Restaurants"],
        "tickers": [
            "SBUX", "KDP", "FARM",                               # US
            "TATACONSUM.NS",                                      # India
        ],
    },
    "SB=F": {
        "sectors": ["Consumer Staples", "Food & Beverage"],
        "tickers": ["KO", "PEP", "MDLZ", "HSY"],
    },
    "CT=F": {
        "sectors": ["Apparel", "Textiles"],
        "tickers": ["PVH", "HBI", "RL", "VFC"],
    },
}

# Commodity → consumer impact description
_CONSUMER_MAP: dict[str, dict] = {
    "CL=F": {"label": "Gas / fuel", "detail": "~55% of pump price", "sensitivity": 0.6},
    "BZ=F": {"label": "Diesel / shipping", "detail": "global freight costs", "sensitivity": 0.5},
    "NG=F": {"label": "Electricity & heating", "detail": "30-50% of utility bill", "sensitivity": 0.7},
    "HO=F": {"label": "Home heating", "detail": "direct pass-through", "sensitivity": 0.8},
    "GC=F": {"label": "Jewellery / savings", "detail": "investment + wedding demand", "sensitivity": 0.3},
    "ZW=F": {"label": "Bread & cereals", "detail": "2-5% in West, 20-40% in EM", "sensitivity": 0.4},
    "ZC=F": {"label": "Meat & ethanol", "detail": "feed costs + gas blending", "sensitivity": 0.4},
    "ZS=F": {"label": "Cooking oil & feed", "detail": "soybean oil in most packaged food", "sensitivity": 0.4},
    "KC=F": {"label": "Coffee", "detail": "~30% of retail coffee price", "sensitivity": 0.5},
    "SB=F": {"label": "Sugar & beverages", "detail": "soft drinks, confectionery", "sensitivity": 0.3},
    "CT=F": {"label": "Clothing", "detail": "fast-fashion most exposed", "sensitivity": 0.3},
    "HG=F": {"label": "Wiring & EVs", "detail": "construction, electronics, EV cost", "sensitivity": 0.3},
    "PL=F": {"label": "Car prices", "detail": "catalytic converters", "sensitivity": 0.2},
    "ALI=F": {"label": "Packaging & cans", "detail": "beverage cans, foil, construction", "sensitivity": 0.3},
}

_COLS = 4  # commodity cards per row


# ── Helpers ──────────────────────────────────────────────────────────────────

_SIGNAL_COLOR_MAP = {"positive": POSITIVE, "negative": NEGATIVE, "caution": CAUTION, "neutral": TEXT_2}


def _change_color(pct: float | None) -> tuple[str, str]:
    """Return (background_rgba, text_color) for a % change value."""
    if pct is None:
        return "rgba(30, 45, 66, 0.30)", TEXT_MUTED
    if abs(pct) >= 5.0:
        return "rgba(212, 168, 67, 0.35)", CAUTION  # extreme move — caution
    if pct >= 2.0:
        return "rgba(52, 211, 153, 0.35)", POSITIVE
    if pct >= 0.5:
        return "rgba(52, 211, 153, 0.18)", POSITIVE
    if pct <= -2.0:
        return "rgba(251, 113, 133, 0.35)", NEGATIVE
    if pct <= -0.5:
        return "rgba(251, 113, 133, 0.18)", NEGATIVE
    return "rgba(30, 45, 66, 0.50)", TEXT_2


def _fetch_commodities() -> dict[str, dict]:
    """Fetch 7-day history for all commodity futures. Runs in a thread pool."""
    import yfinance as yf

    all_symbols: list[tuple[str, str, str]] = []
    for cat, items in COMMODITY_CATEGORIES.items():
        for name, sym in items.items():
            all_symbols.append((cat, name, sym))

    results: dict[str, dict] = {}

    def _fetch_one(cat: str, name: str, sym: str) -> None:
        try:
            hist = yf.Ticker(sym).history(period="7d")
            if hist.empty or len(hist) < 1:
                results[sym] = {"name": name, "category": cat, "price": None,
                                "pct_1d": None, "pct_1w": None, "prices_5d": []}
                return
            closes = [float(c) for c in hist["Close"].tolist()]
            price = closes[-1]
            pct_1d = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else None
            pct_1w = ((closes[-1] - closes[0]) / closes[0] * 100) if len(closes) >= 2 else None
            results[sym] = {
                "name": name, "category": cat, "price": price,
                "pct_1d": pct_1d, "pct_1w": pct_1w,
                "prices_5d": closes[-5:] if len(closes) >= 5 else closes,
            }
        except Exception:
            results[sym] = {"name": name, "category": cat, "price": None,
                            "pct_1d": None, "pct_1w": None, "prices_5d": []}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_fetch_one, cat, name, sym) for cat, name, sym in all_symbols]
        for f in futures:
            f.result()

    return results


# ── Scenario Worker (QThread) ────────────────────────────────────────────────

class _ScenarioWorker(QThread):
    """Run scenario analysis through the ReAct agent in a dedicated thread."""

    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, agent, task_text: str) -> None:
        super().__init__()
        self._agent = agent
        self._task_text = task_text
        self._loop: asyncio.AbstractEventLoop | None = None
        self._asyncio_task: asyncio.Task | None = None

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        exc_info: BaseException | None = None
        result: str = ""

        try:
            def on_chunk(chunk: str) -> None:
                self.chunk_received.emit(chunk)

            async def _execute() -> str:
                self._asyncio_task = asyncio.current_task()
                return await self._agent.run(
                    task=self._task_text,
                    history=[],
                    on_chunk=on_chunk,
                    skip_memory=True,
                )

            result = loop.run_until_complete(_execute())

        except BaseException as exc:
            exc_info = exc

        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None
            self._asyncio_task = None

        if exc_info is None:
            self.finished.emit(result)
        elif isinstance(exc_info, asyncio.CancelledError):
            self.finished.emit(result or "Analysis cancelled.")
        else:
            self.error.emit(str(exc_info))

    def cancel(self) -> None:
        if self._loop is not None and self._asyncio_task is not None:
            self._loop.call_soon_threadsafe(self._asyncio_task.cancel)


# ── Commodity Card ───────────────────────────────────────────────────────────

class _CommodityCard(QFrame):
    """200x120 card showing commodity name, price, 1D/1W %, and sparkline."""

    clicked = pyqtSignal(str, str)  # symbol, name

    def __init__(self, name: str, symbol: str, main_window: "MainWindow",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._symbol = symbol
        self._mw = main_window

        self.setFixedSize(200, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_bg(None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        # Top row: name + sparkline
        top = QHBoxLayout()
        top.setSpacing(6)

        name_col = QVBoxLayout()
        name_col.setSpacing(1)
        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_1}; background: transparent;")
        self._sym_lbl = QLabel(symbol)
        self._sym_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;")
        name_col.addWidget(self._name_lbl)
        name_col.addWidget(self._sym_lbl)
        top.addLayout(name_col)
        top.addStretch()

        self._spark_lbl = QLabel()
        self._spark_lbl.setFixedSize(54, 20)
        self._spark_lbl.setStyleSheet("background: transparent;")
        top.addWidget(self._spark_lbl)

        layout.addLayout(top)
        layout.addStretch()

        # Price
        self._price_lbl = QLabel("--")
        self._price_lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {TEXT_1}; background: transparent;")
        layout.addWidget(self._price_lbl)

        # Change row
        change_row = QHBoxLayout()
        change_row.setSpacing(10)
        self._pct_1d_lbl = QLabel("--")
        self._pct_1d_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {TEXT_2}; background: transparent;")
        self._pct_1w_lbl = QLabel("")
        self._pct_1w_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_2}; background: transparent;")
        change_row.addWidget(self._pct_1d_lbl)
        change_row.addWidget(self._pct_1w_lbl)
        change_row.addStretch()
        layout.addLayout(change_row)

    def update_data(self, price: float | None, pct_1d: float | None,
                    pct_1w: float | None, sparkline_bytes: bytes) -> None:
        if price is not None:
            self._price_lbl.setText(f"${price:,.2f}")
        else:
            self._price_lbl.setText("--")

        if pct_1d is not None:
            sign = "+" if pct_1d >= 0 else ""
            self._pct_1d_lbl.setText(f"{sign}{pct_1d:.2f}%")
            _, txt_c = _change_color(pct_1d)
            self._pct_1d_lbl.setStyleSheet(
                f"font-size: 16px; font-weight: 700; color: {txt_c}; background: transparent;"
            )
        else:
            self._pct_1d_lbl.setText("--")

        if pct_1w is not None:
            sign = "+" if pct_1w >= 0 else ""
            self._pct_1w_lbl.setText(f"1W {sign}{pct_1w:.1f}%")
        else:
            self._pct_1w_lbl.setText("")

        self._apply_bg(pct_1d)

        if sparkline_bytes:
            img = QImage.fromData(sparkline_bytes)
            self._spark_lbl.setPixmap(
                QPixmap.fromImage(img).scaled(
                    54, 20, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _apply_bg(self, pct: float | None) -> None:
        bg, _ = _change_color(pct)
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: none; border-radius: 14px; }}"
        )

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._symbol, self._name)
        super().mousePressEvent(event)


# ── Scenario Result Panel ────────────────────────────────────────────────────

class _ScenarioResultPanel(QWidget):
    """Renders the 4-tier scenario analysis with visual differentiation."""

    _TIER_CONFIG = {
        "PRIMARY":   {"color": NEGATIVE,    "label": "PRIMARY IMPACT"},
        "SECONDARY": {"color": ACCENT_CYAN, "label": "SECONDARY IMPACT"},
        "TERTIARY":  {"color": TEXT_2,       "label": "TERTIARY IMPACT"},
        "CONSUMER":  {"color": ACCENT,       "label": "CONSUMER IMPACT"},
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    def set_result(self, text: str, portfolio_tickers: set[str]) -> None:
        """Parse agent response and render tier-separated panels."""
        # Clear previous
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Split response into tier sections
        sections = self._split_tiers(text)
        if not sections:
            # No tier headers found — render as a single block
            self._add_text_block(text, TEXT_1, portfolio_tickers)
            return

        for tier_key, content in sections:
            cfg = self._TIER_CONFIG.get(tier_key, {"color": TEXT_2, "label": tier_key})
            self._add_tier_frame(cfg["label"], cfg["color"], content, portfolio_tickers)

    def _split_tiers(self, text: str) -> list[tuple[str, str]]:
        """Split text into (tier_key, content) pairs based on headers."""
        tier_keys = list(self._TIER_CONFIG.keys())
        pattern = r"(?:^|\n)\s*(?:\*\*)?(" + "|".join(tier_keys) + r")[\s_]*(?:IMPACT)?[\s:]*(?:\*\*)?[:\-—]*\s*"
        parts = re.split(pattern, text, flags=re.IGNORECASE)

        if len(parts) < 3:
            return []

        # parts[0] is preamble, then alternating: tier_key, content, tier_key, content…
        result = []
        preamble = parts[0].strip()
        if preamble:
            result.append(("PREAMBLE", preamble))

        for i in range(1, len(parts) - 1, 2):
            key = parts[i].upper().strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                result.append((key, content))

        return result

    def _add_tier_frame(self, label: str, accent: str, content: str,
                        portfolio_tickers: set[str]) -> None:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 14px;"
            f"border-left: 3px solid {accent}; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(8)

        header = QLabel(label)
        header.setStyleSheet(
            f"color: {accent}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
            f"background: transparent;"
        )
        v.addWidget(header)

        self._add_text_block(content, TEXT_1, portfolio_tickers, parent_layout=v)
        self._layout.addWidget(frame)

    def _add_text_block(self, text: str, color: str, portfolio_tickers: set[str],
                        parent_layout: QVBoxLayout | None = None) -> None:
        target = parent_layout or self._layout
        lbl = QLabel(self._highlight_tickers(text, portfolio_tickers))
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet(
            f"color: {color}; font-size: 13px; line-height: 1.5; background: transparent;"
        )
        target.addWidget(lbl)

    @staticmethod
    def _highlight_tickers(text: str, tickers: set[str]) -> str:
        """Wrap portfolio tickers in the text with accent-colored spans."""
        if not tickers:
            # Basic HTML-escape
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for t in sorted(tickers, key=len, reverse=True):
            pattern = re.compile(r'\b(' + re.escape(t) + r')\b')
            escaped = pattern.sub(
                rf'<span style="color: {ACCENT}; font-weight: 700;">\1</span>',
                escaped,
            )
        return escaped.replace("\n", "<br>")


# ── Commodity Detail Panel ────────────────────────────────────────────────────

class _CommodityDetailPanel(QFrame):
    """Expandable panel showing technical indicators for a single commodity."""

    def __init__(self, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mw = main_window
        self.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 14px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        self._title = QLabel("")
        self._title.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
            f"background: transparent;"
        )
        layout.addWidget(self._title)

        # 4x3 grid of indicator labels
        grid = QGridLayout()
        grid.setSpacing(6)
        self._indicator_labels: dict[str, QLabel] = {}

        indicators = [
            ("RSI-14", "rsi"), ("MACD", "macd"), ("Stochastic", "stoch"),
            ("EMA-20", "ema20"), ("EMA-50", "ema50"), ("vs Price", "price_vs"),
            ("Support", "support"), ("Resistance", "resistance"), ("Bollinger", "bb"),
            ("30d Vol", "vol"), ("ATR-14", "atr"), ("ADX", "adx"),
        ]

        for idx, (label_text, key) in enumerate(indicators):
            row, col = divmod(idx, 3)
            container = QVBoxLayout()
            container.setSpacing(1)
            title_lbl = QLabel(label_text)
            title_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;")
            value_lbl = QLabel("--")
            value_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 13px; background: transparent;")
            self._indicator_labels[key] = value_lbl
            container.addWidget(title_lbl)
            container.addWidget(value_lbl)
            w = QWidget()
            w.setLayout(container)
            w.setStyleSheet("background: transparent;")
            grid.addWidget(w, row, col)

        layout.addLayout(grid)

        # Deep Analyse button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._analyse_btn = QPushButton("Deep Analyse")
        self._analyse_btn.setFixedHeight(28)
        self._analyse_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_3}; border: none;"
            f"border-radius: 8px; padding: 4px 14px; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {TEXT_1}; }}"
        )
        btn_row.addWidget(self._analyse_btn)
        layout.addLayout(btn_row)

    def update_data(self, symbol: str, name: str, data: dict) -> None:
        self._title.setText(f"TECHNICAL ANALYSIS — {name} ({symbol})")

        def _fmt(val, fmt_str=".2f", suffix="") -> str:
            return f"{val:{fmt_str}}{suffix}" if val is not None else "--"

        def _color(val, high_bad=70, low_good=30) -> str:
            if val is None:
                return TEXT_2
            if val >= high_bad:
                return NEGATIVE
            if val <= low_good:
                return POSITIVE
            return TEXT_1

        # RSI
        rsi = data.get("rsi")
        self._set_val("rsi", _fmt(rsi, ".1f"), _color(rsi))

        # MACD
        mh = data.get("macd_hist")
        if mh is not None:
            direction = "Bullish" if mh >= 0 else "Bearish"
            c = POSITIVE if mh >= 0 else NEGATIVE
            self._set_val("macd", f"{direction} ({mh:+.3f})", c)
        else:
            self._set_val("macd", "--", TEXT_2)

        # Stochastic
        from services.macro_signals import (
            get_stochastic_signal, get_bollinger_signal, get_proximity_signal,
        )
        k, d = data.get("stoch_k"), data.get("stoch_d")
        stoch_c = _SIGNAL_COLOR_MAP.get(get_stochastic_signal(k), TEXT_1)
        self._set_val("stoch", f"%K={_fmt(k, '.0f')} %D={_fmt(d, '.0f')}", stoch_c)

        # EMAs
        price = data.get("price")
        ema20 = data.get("ema20")
        ema50 = data.get("ema50")
        if ema20 is not None:
            above = price is not None and price >= ema20
            self._set_val("ema20", f"${ema20:,.2f}", POSITIVE if above else NEGATIVE)
        else:
            self._set_val("ema20", "--", TEXT_2)
        if ema50 is not None:
            above = price is not None and price >= ema50
            self._set_val("ema50", f"${ema50:,.2f}", POSITIVE if above else NEGATIVE)
        else:
            self._set_val("ema50", "--", TEXT_2)

        if price is not None:
            self._set_val("price_vs", f"${price:,.2f}", TEXT_1)
        else:
            self._set_val("price_vs", "--", TEXT_2)

        # Support/Resistance — colored by proximity
        support = data.get("support")
        resistance = data.get("resistance")
        sup_c = _SIGNAL_COLOR_MAP.get(get_proximity_signal(price, support, True), TEXT_1)
        res_c = _SIGNAL_COLOR_MAP.get(get_proximity_signal(price, resistance, False), TEXT_1)
        self._set_val("support", f"${support:,.2f}" if support else "--", sup_c)
        self._set_val("resistance", f"${resistance:,.2f}" if resistance else "--", res_c)

        # Bollinger position — colored by band position
        bb_u, bb_l = data.get("bb_upper"), data.get("bb_lower")
        if bb_u and bb_l and price:
            bb_range = bb_u - bb_l
            if bb_range > 0:
                pct = (price - bb_l) / bb_range * 100
                bb_c = _SIGNAL_COLOR_MAP.get(get_bollinger_signal(pct), TEXT_1)
                self._set_val("bb", f"{pct:.0f}% (of band)", bb_c)
            else:
                self._set_val("bb", "--", TEXT_2)
        else:
            self._set_val("bb", "--", TEXT_2)

        # Volatility, ATR, ADX
        vol = data.get("volatility_30d")
        self._set_val("vol", f"{vol:.1f}%" if vol else "--", NEGATIVE if vol and vol > 40 else TEXT_1)
        atr = data.get("atr14")
        self._set_val("atr", f"${atr:,.2f}" if atr else "--", TEXT_1)
        adx = data.get("adx")
        if adx is not None:
            trend = "strong" if adx > 25 else "weak"
            self._set_val("adx", f"{adx:.1f} ({trend})", TEXT_1)
        else:
            self._set_val("adx", "--", TEXT_2)

        # Wire deep analyse button
        try:
            self._analyse_btn.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self._analyse_btn.clicked.connect(
            lambda: self._mw.switch_to_analysis(
                f"Analyse the commodity {name} ({symbol}) — "
                "what's driving the price and what sectors are affected?"
            )
        )

    def _set_val(self, key: str, text: str, color: str) -> None:
        lbl = self._indicator_labels.get(key)
        if lbl:
            lbl.setText(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")


# ── Risk Metrics Panel ───────────────────────────────────────────────────────

class _RiskMetricsPanel(QFrame):
    """Displays portfolio risk metrics: VaR, betas, drawdown, stress tests."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 14px; }}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(6)
        self._content_label = QLabel("Click 'Compute Risk Metrics' to analyse your portfolio's commodity exposure")
        self._content_label.setWordWrap(True)
        self._content_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        self._layout.addWidget(self._content_label)

    def update_metrics(self, metrics: dict) -> None:
        self._content_label.hide()

        # Clear previous dynamic widgets
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # VaR row
        var95 = metrics.get("var_95")
        var99 = metrics.get("var_99")
        if var95 is not None:
            var_text = f"VaR (95%): {var95:+.2f}%  |  VaR (99%): {var99:+.2f}%  — daily worst-case loss estimate"
            lbl = QLabel(var_text)
            lbl.setStyleSheet(f"color: {NEGATIVE}; font-size: 13px; background: transparent;")
            self._layout.addWidget(lbl)

        # Max drawdown
        mdd = metrics.get("max_drawdown")
        if mdd is not None:
            lbl = QLabel(f"Max Drawdown (90d): {mdd:.1f}%")
            lbl.setStyleSheet(f"color: {NEGATIVE}; font-size: 13px; background: transparent;")
            self._layout.addWidget(lbl)

        # Commodity betas
        betas = metrics.get("commodity_betas", {})
        if betas:
            beta_parts = [f"{name}: {beta:+.3f}" for name, beta in betas.items()]
            lbl = QLabel("Commodity Betas: " + "  |  ".join(beta_parts))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 12px; background: transparent;")
            self._layout.addWidget(lbl)

        # Stress tests
        stresses = metrics.get("stress_tests", [])
        for s in stresses:
            c = POSITIVE if s["portfolio_impact"] >= 0 else NEGATIVE
            lbl = QLabel(f"If {s['commodity']} {s['move']}: portfolio {s['portfolio_impact']:+.2f}%")
            lbl.setStyleSheet(f"color: {c}; font-size: 12px; background: transparent;")
            self._layout.addWidget(lbl)

    def show_error(self, msg: str) -> None:
        self._content_label.setText(msg)
        self._content_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        self._content_label.show()


# ── Main View ────────────────────────────────────────────────────────────────

class MacroView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw = main_window
        self._cards: dict[str, _CommodityCard] = {}
        self._commodity_data: dict[str, dict] = {}
        self._scenario_worker: _ScenarioWorker | None = None
        self._pending_scenario: str | None = None
        self._cached_technicals: dict[str, dict] = {}
        self._cached_risk: dict | None = None
        self._detail_symbol: str | None = None  # currently expanded commodity
        self._setup_ui()
        QTimer.singleShot(2500, lambda: asyncio.ensure_future(self._refresh()))

    # ── UI construction ──────────────────────────────────────────────────

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
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(32, 16, 32, 32)
        self._body_layout.setSpacing(16)

        # Status label
        self._updated_lbl = QLabel("Loading commodity data...")
        self._updated_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._body_layout.addWidget(self._updated_lbl)

        # Briefing banner (hidden initially)
        self._briefing_frame = QFrame()
        self._briefing_frame.setStyleSheet(
            f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 14px; }}"
        )
        bf_layout = QVBoxLayout(self._briefing_frame)
        bf_layout.setContentsMargins(20, 16, 20, 16)
        self._briefing_lbl = QLabel("")
        self._briefing_lbl.setWordWrap(True)
        self._briefing_lbl.setStyleSheet(
            f"color: {TEXT_1}; font-size: 13px; background: transparent;"
        )
        bf_layout.addWidget(self._briefing_lbl)
        self._briefing_frame.hide()
        self._body_layout.addWidget(self._briefing_frame)

        # Macro indicators panel (FRED data)
        indicators_lbl = QLabel("MACRO INDICATORS")
        indicators_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        self._body_layout.addWidget(indicators_lbl)
        self._indicators_widget = QWidget()
        self._indicators_grid = QGridLayout(self._indicators_widget)
        self._indicators_grid.setSpacing(8)
        self._indicators_grid.setContentsMargins(0, 0, 0, 0)
        self._body_layout.addWidget(self._indicators_widget)
        # Placeholder until data loads
        self._indicators_placeholder = QLabel("Add FRED API key in Settings for live macro data")
        self._indicators_placeholder.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._indicators_grid.addWidget(self._indicators_placeholder, 0, 0)
        self._indicators_chip_count = 0

        self._body_layout.addSpacing(12)

        # Commodity grid sections
        for cat, items in COMMODITY_CATEGORIES.items():
            cat_lbl = QLabel(cat.upper())
            cat_lbl.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
            )
            self._body_layout.addWidget(cat_lbl)

            grid_widget = QWidget()
            grid = QGridLayout(grid_widget)
            grid.setSpacing(10)
            grid.setContentsMargins(0, 0, 0, 0)

            for idx, (name, sym) in enumerate(items.items()):
                card = _CommodityCard(name, sym, self._mw)
                card.clicked.connect(self._on_card_clicked)
                self._cards[sym] = card
                grid.addWidget(card, idx // _COLS, idx % _COLS)

            self._body_layout.addWidget(grid_widget)

        # ── Commodity Detail Panel (expandable) ───────────────────────────
        self._detail_panel = _CommodityDetailPanel(self._mw)
        self._detail_panel.hide()
        self._body_layout.addWidget(self._detail_panel)

        # ── Risk Metrics Panel ────────────────────────────────────────────
        self._body_layout.addSpacing(12)
        risk_lbl = QLabel("PORTFOLIO RISK METRICS")
        risk_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        self._body_layout.addWidget(risk_lbl)
        self._risk_panel = _RiskMetricsPanel()
        self._body_layout.addWidget(self._risk_panel)

        compute_risk_btn = QPushButton("Compute Risk Metrics")
        compute_risk_btn.setFixedHeight(30)
        compute_risk_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none;"
            f"border-radius: 10px; padding: 6px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
        )
        compute_risk_btn.clicked.connect(
            lambda: asyncio.ensure_future(self._compute_and_show_risk())
        )
        self._risk_compute_btn = compute_risk_btn
        self._body_layout.addWidget(compute_risk_btn)

        # ── Scenario Analysis section ─────��─────────────────────────────���─
        self._body_layout.addSpacing(12)
        scenario_lbl = QLabel("SCENARIO ANALYSIS")
        scenario_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        self._body_layout.addWidget(scenario_lbl)

        scenario_desc = QLabel(
            "Type a geopolitical or macro scenario to see cascading impact "
            "across commodities, sectors, your portfolio, and consumer prices."
        )
        scenario_desc.setWordWrap(True)
        scenario_desc.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")
        self._body_layout.addWidget(scenario_desc)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self._scenario_input = QLineEdit()
        self._scenario_input.setPlaceholderText(
            "What if... (e.g., 'Iran closes the Strait of Hormuz')"
        )
        self._scenario_input.returnPressed.connect(self._on_analyse_clicked)
        input_row.addWidget(self._scenario_input, stretch=1)

        self._analyse_btn = QPushButton("Analyse Scenario")
        self._analyse_btn.setObjectName("AccentBtn")
        self._analyse_btn.setFixedHeight(36)
        self._analyse_btn.clicked.connect(self._on_analyse_clicked)
        input_row.addWidget(self._analyse_btn)

        self._body_layout.addLayout(input_row)

        # Streaming output
        self._scenario_status = QLabel("")
        self._scenario_status.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._body_layout.addWidget(self._scenario_status)

        # Result panel
        self._result_panel = _ScenarioResultPanel()
        self._result_panel.hide()
        self._body_layout.addWidget(self._result_panel)

        # ── Market & Consumer Impact Radar ────────────────────────────────
        self._body_layout.addSpacing(12)
        radar_lbl = QLabel("MARKET IMPACT RADAR")
        radar_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        self._body_layout.addWidget(radar_lbl)

        self._radar_container = QVBoxLayout()
        self._radar_container.setSpacing(8)
        self._body_layout.addLayout(self._radar_container)

        # Consumer ticker
        self._body_layout.addSpacing(8)
        consumer_lbl = QLabel("CONSUMER IMPACT")
        consumer_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        self._body_layout.addWidget(consumer_lbl)

        self._consumer_widget = QWidget()
        self._consumer_grid = QGridLayout(self._consumer_widget)
        self._consumer_grid.setSpacing(8)
        self._consumer_grid.setContentsMargins(0, 0, 0, 0)
        self._body_layout.addWidget(self._consumer_widget)
        self._consumer_chip_count = 0

        # ── Correlation Matrix section ────────────────────────────────────
        self._body_layout.addSpacing(12)
        corr_lbl = QLabel("CORRELATION MATRIX")
        corr_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        self._body_layout.addWidget(corr_lbl)

        corr_desc = QLabel(
            "Shows how commodity prices move together over 90 days. "
            "+1 = move in lockstep, 0 = unrelated, -1 = move opposite. "
            "Green = move together, red = move opposite. Bold = strong relationship (|r| > 0.7). "
            "Use this to check diversification (high correlation = less diversified), "
            "find hedges (negative correlation), and predict cascades (correlated commodities follow each other)."
        )
        corr_desc.setWordWrap(True)
        corr_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        self._body_layout.addWidget(corr_desc)

        self._corr_btn = QPushButton("Compute Correlations")
        self._corr_btn.setFixedHeight(30)
        self._corr_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none;"
            f"border-radius: 10px; padding: 6px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
        )
        self._corr_btn.clicked.connect(
            lambda: asyncio.ensure_future(self._compute_correlations())
        )
        self._body_layout.addWidget(self._corr_btn)

        self._corr_image = QLabel()
        self._corr_image.setStyleSheet("background: transparent;")
        self._corr_image.hide()
        self._body_layout.addWidget(self._corr_image)

        self._corr_summary = QLabel()
        self._corr_summary.setWordWrap(True)
        self._corr_summary.setStyleSheet(f"color: {TEXT_2}; font-size: 12px;")
        self._corr_summary.hide()
        self._body_layout.addWidget(self._corr_summary)

        self._body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h = QHBoxLayout(header)
        h.setContentsMargins(32, 20, 32, 8)
        h.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Global Macro")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Commodity prices, scenario analysis, and impact radar")
        subtitle.setStyleSheet(f"color: {TEXT_2}; font-size: 13px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        h.addLayout(title_col)
        h.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none;"
            f"border-radius: 10px; padding: 6px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
        )
        self._refresh_btn.clicked.connect(
            lambda: asyncio.ensure_future(self._refresh())
        )
        h.addWidget(self._refresh_btn)
        return header

    # ── Data loading ─────────────────────────────────────────────────────

    async def _refresh(self) -> None:
        from services.charting import render_commodity_sparkline

        self._refresh_btn.setEnabled(False)
        self._updated_lbl.setText("Fetching commodity data...")

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _fetch_commodities)
        self._commodity_data = data

        for sym, info in data.items():
            if sym in self._cards:
                prices = info.get("prices_5d", [])
                up = (info.get("pct_1d") or 0) >= 0
                spark = b""
                if len(prices) >= 2:
                    spark = await loop.run_in_executor(
                        None, render_commodity_sparkline, prices, up,
                    )
                self._cards[sym].update_data(
                    info.get("price"), info.get("pct_1d"),
                    info.get("pct_1w"), spark,
                )

        # Update briefing
        self._update_briefing(data)
        # Update radar
        self._update_radar(data)
        # Update consumer ticker
        self._update_consumer_ticker(data)
        # Update FRED macro indicators
        asyncio.ensure_future(self._update_indicators_panel())

        # Save current prices for next-session comparison
        now_iso = datetime.now().isoformat(timespec="seconds")
        self._state.last_commodity_prices = {
            sym: {"price": info.get("price"), "ts": now_iso}
            for sym, info in data.items()
            if info.get("price") is not None
        }
        self._state.save_commodity_state()

        ts = datetime.now().strftime("%H:%M:%S")
        self._updated_lbl.setText(f"Last updated: {ts}  --  Click a commodity to analyse")
        self._refresh_btn.setEnabled(True)

    def _update_briefing(self, data: dict[str, dict]) -> None:
        """Show 'since last session' banner if previous prices exist."""
        prev = self._state.last_commodity_prices
        if not prev:
            self._briefing_frame.hide()
            return

        deltas = []
        affected_holdings = set()
        portfolio_tickers = {h["ticker"] for h in self._state.portfolio}

        for sym, info in data.items():
            curr_price = info.get("price")
            prev_info = prev.get(sym)
            if curr_price is None or prev_info is None:
                continue
            prev_price = prev_info.get("price")
            if prev_price is None or prev_price == 0:
                continue
            pct = (curr_price - prev_price) / prev_price * 100
            if abs(pct) >= 1.0:
                sign = "+" if pct >= 0 else ""
                name = _SYMBOL_NAMES.get(sym, sym)
                deltas.append(f"{name} {sign}{pct:.1f}%")
                # Check portfolio overlap
                for t in COMMODITY_SECTOR_MAP.get(sym, {}).get("tickers", []):
                    if t in portfolio_tickers:
                        affected_holdings.add(t)

        if not deltas:
            self._briefing_frame.hide()
            return

        msg = "Since your last session: " + ", ".join(deltas[:6])
        if affected_holdings:
            msg += f". {len(affected_holdings)} of your holdings in affected sectors."
        self._briefing_lbl.setText(msg)
        self._briefing_frame.show()

    def _update_radar(self, data: dict[str, dict]) -> None:
        """Update market impact radar with current commodity moves."""
        from services.macro_signals import get_commodity_move_signal

        # Clear previous
        while self._radar_container.count():
            item = self._radar_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        portfolio_tickers = {h["ticker"] for h in self._state.portfolio}
        shown = 0

        for sym, info in data.items():
            pct = info.get("pct_1d")
            if pct is None or abs(pct) < 1.0:
                continue
            name = info.get("name", sym)
            mapping = COMMODITY_SECTOR_MAP.get(sym)
            if not mapping:
                continue

            signal = get_commodity_move_signal(sym, pct, info.get("pct_1w"))
            sign = "+" if pct >= 0 else ""
            tickers = mapping["tickers"]

            # Build description with producer/consumer split
            lines: list[str] = []
            header = f"{name} {sign}{pct:.1f}%"

            if signal["producer_desc"] and signal["consumer_desc"]:
                lines.append(f"{header}  |  Producers: {signal['producer_desc']}  |  Consumers: {signal['consumer_desc']}")
            elif signal["producer_desc"]:
                lines.append(f"{header} -- {', '.join(mapping['sectors'][:3])}: {signal['producer_desc']}")
            elif signal["consumer_desc"]:
                lines.append(f"{header} -- {', '.join(mapping['sectors'][:3])}: {signal['consumer_desc']}")
            else:
                lines.append(f"{header} -- {', '.join(mapping['sectors'][:3])}")

            # Portfolio matches
            matches = [t for t in tickers if t in portfolio_tickers]
            if matches:
                lines[0] += f"  |  Your holdings: {', '.join(matches)}"

            # Direction color — extreme moves get gold
            if signal["severity"] == "extreme":
                dir_color = CAUTION
            elif pct >= 0:
                dir_color = POSITIVE
            else:
                dir_color = NEGATIVE

            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 10px; }}"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 10, 16, 10)
            row_layout.setSpacing(8)

            dir_lbl = QLabel("!" if signal["severity"] == "extreme" else ("^" if pct >= 0 else "v"))
            dir_lbl.setFixedWidth(16)
            dir_lbl.setStyleSheet(
                f"color: {dir_color}; font-size: 14px; font-weight: 700; background: transparent;"
            )
            row_layout.addWidget(dir_lbl)

            txt_lbl = QLabel(lines[0])
            txt_lbl.setWordWrap(True)
            txt_lbl.setStyleSheet(f"color: {TEXT_1}; font-size: 12px; background: transparent;")
            row_layout.addWidget(txt_lbl, stretch=1)

            self._radar_container.addWidget(row)
            shown += 1

            # Demand destruction warning row
            if signal["warning"]:
                warn_row = QFrame()
                warn_row.setStyleSheet(
                    f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 10px;"
                    f"border-left: 3px solid {CAUTION}; }}"
                )
                wl = QHBoxLayout(warn_row)
                wl.setContentsMargins(16, 8, 16, 8)
                wlbl = QLabel(f"Demand destruction: {signal['warning']}")
                wlbl.setWordWrap(True)
                wlbl.setStyleSheet(f"color: {CAUTION}; font-size: 11px; background: transparent;")
                wl.addWidget(wlbl)
                self._radar_container.addWidget(warn_row)
                shown += 1

            if shown >= 10:
                break

        if shown == 0:
            no_data = QLabel("No significant commodity moves today (threshold: 1% daily change)")
            no_data.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            self._radar_container.addWidget(no_data)

    def _update_consumer_ticker(self, data: dict[str, dict]) -> None:
        """Update consumer impact ticker strip."""
        while self._consumer_grid.count():
            item = self._consumer_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._consumer_chip_count = 0

        shown = 0
        for sym, cmap in _CONSUMER_MAP.items():
            info = data.get(sym)
            if not info or info.get("pct_1d") is None:
                continue
            pct = info["pct_1d"]
            sensitivity = cmap["sensitivity"]
            # Scale impact by sensitivity — a 1% oil move matters more than 1% gold move
            effective = abs(pct) * sensitivity

            if effective < 0.5:
                status = "stable"
                color = TEXT_MUTED
            elif pct > 0:
                if effective >= 2.0:
                    status = f"up sharply ({pct:+.1f}%)"
                else:
                    status = f"costs rising ({pct:+.1f}%)"
                color = NEGATIVE  # consumer cost rising is bad
            else:
                if effective >= 2.0:
                    status = f"down sharply ({pct:+.1f}%)"
                else:
                    status = f"costs easing ({pct:+.1f}%)"
                color = POSITIVE  # consumer cost falling is good

            chip = QFrame()
            chip.setStyleSheet(
                f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 10px; }}"
            )
            chip_layout = QVBoxLayout(chip)
            chip_layout.setContentsMargins(12, 8, 12, 8)
            chip_layout.setSpacing(1)

            name_lbl = QLabel(cmap["label"])
            name_lbl.setStyleSheet(f"color: {TEXT_2}; font-size: 10px; background: transparent;")
            status_lbl = QLabel(status)
            status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;")
            detail_lbl = QLabel(cmap["detail"])
            detail_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; background: transparent;")

            chip_layout.addWidget(name_lbl)
            chip_layout.addWidget(status_lbl)
            chip_layout.addWidget(detail_lbl)
            row, col = divmod(self._consumer_chip_count, _COLS)
            self._consumer_grid.addWidget(chip, row, col)
            self._consumer_chip_count += 1
            shown += 1

        if shown == 0:
            no_data = QLabel("Loading...")
            no_data.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
            self._consumer_grid.addWidget(no_data, 0, 0)

    # ── Scenario Analysis ────────────────────────────────────────────────

    def _on_analyse_clicked(self) -> None:
        scenario = self._scenario_input.text().strip()
        if not scenario:
            return
        if self._state.agent is None:
            self._analyse_btn.setEnabled(False)
            self._scenario_status.setText("Waiting for agent to initialize...")
            self._pending_scenario = scenario
            QTimer.singleShot(1000, self._retry_analyse)
            return

        self._analyse_btn.setEnabled(False)
        self._scenario_status.setText("Analysing scenario...")
        self._pending_scenario = None
        self._result_panel.hide()
        self._accumulated_text = ""

        # Build commodity prices table for prompt context
        price_lines = []
        for sym, info in self._commodity_data.items():
            if info.get("price") is not None:
                pct_str = ""
                if info.get("pct_1d") is not None:
                    sign = "+" if info["pct_1d"] >= 0 else ""
                    pct_str = f" ({sign}{info['pct_1d']:.1f}% today)"
                price_lines.append(f"  {info['name']} ({sym}): ${info['price']:,.2f}{pct_str}")

        prices_table = "\n".join(price_lines) if price_lines else "  (data unavailable)"

        # Portfolio holdings
        if self._state.portfolio:
            holdings = "\n".join(
                f"  {h['ticker']} — {h['qty']} shares @ ${h['avg_cost']:.2f}"
                for h in self._state.portfolio
            )
        else:
            holdings = "  None — show full analysis regardless"

        # Inject knowledge base context (chokepoints, crisis parallels, seasonals)
        knowledge_block = ""
        try:
            from services.knowledge import build_knowledge_context
            current_prices = {
                sym: info["price"]
                for sym, info in self._commodity_data.items()
                if info.get("price") is not None
            }
            kb = build_knowledge_context(scenario, datetime.now().month, current_prices)
            if kb:
                knowledge_block = f"\nEXPERT KNOWLEDGE BASE:\n{kb}\n"
        except Exception:
            pass

        # Inject FRED/EIA research data
        research_block = ""
        try:
            from services.research import build_research_context
            rc = build_research_context()
            if rc:
                research_block = f"\n{rc}\n"
        except Exception:
            pass

        # Inject cached technicals for significant movers
        technicals_block = ""
        if self._cached_technicals:
            tech_lines = ["COMMODITY TECHNICAL READINGS:"]
            for sym, tdata in self._cached_technicals.items():
                name = _SYMBOL_NAMES.get(sym, sym)
                rsi = tdata.get("rsi")
                macd_h = tdata.get("macd_hist")
                vol = tdata.get("volatility_30d")
                parts = []
                if rsi is not None:
                    parts.append(f"RSI={rsi:.1f}")
                if macd_h is not None:
                    parts.append(f"MACD={'bullish' if macd_h >= 0 else 'bearish'}")
                if vol is not None:
                    parts.append(f"30dVol={vol:.1f}%")
                if parts:
                    tech_lines.append(f"  {name}: {', '.join(parts)}")
            if len(tech_lines) > 1:
                technicals_block = "\n" + "\n".join(tech_lines) + "\n"

        # Inject risk metrics summary
        risk_block = ""
        if self._cached_risk:
            risk_lines = ["PORTFOLIO RISK METRICS:"]
            v95 = self._cached_risk.get("var_95")
            if v95 is not None:
                risk_lines.append(f"  VaR (95%): {v95:+.2f}% daily")
            mdd = self._cached_risk.get("max_drawdown")
            if mdd is not None:
                risk_lines.append(f"  Max Drawdown (90d): {mdd:.1f}%")
            betas = self._cached_risk.get("commodity_betas", {})
            for bname, bval in betas.items():
                risk_lines.append(f"  Beta to {bname}: {bval:+.3f}")
            if len(risk_lines) > 1:
                risk_block = "\n" + "\n".join(risk_lines) + "\n"

        task = (
            f"Analyze this geopolitical/macro scenario for cascading market impact.\n\n"
            f"SCENARIO: {scenario}\n\n"
            f"CURRENT COMMODITY PRICES:\n{prices_table}\n"
            f"{knowledge_block}"
            f"{research_block}"
            f"{technicals_block}"
            f"{risk_block}\n"
            f"USER PORTFOLIO HOLDINGS (if any):\n{holdings}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Search for the latest news and institutional research related to this scenario\n"
            f"2. Analyze cascading impact in FOUR tiers with GLOBAL scope. For EACH tier, "
            f"cover US, European, Asian (China, India, Japan), and emerging markets. "
            f"List ALL affected sectors/commodities/areas — not just ones the user holds:\n\n"
            f"   - PRIMARY IMPACT: Directly affected commodities — direction, "
            f"estimated magnitude, key tickers/ETFs across US AND international markets. "
            f"Reference exact numbers from the knowledge base above (chokepoints, "
            f"pass-through rates, trade flows, EM vulnerability)\n"
            f"   - SECONDARY IMPACT: Industries with direct input cost exposure — "
            f"airlines, petrochemicals, fertilizer, shipping, defense, etc. "
            f"Include companies from US, Europe, India, China where relevant. "
            f"Use input-output relationships to trace global supply chain effects. "
            f"Note which emerging markets are most vulnerable and why\n"
            f"   - TERTIARY IMPACT: Downstream market effects across major economies — "
            f"Fed/ECB/RBI/PBoC rate policy responses, currency shifts (USD, EUR, INR, CNY), "
            f"yield curves globally, emerging market debt stress, capital flow shifts. "
            f"Reference FRED/EIA data if available above. Note demand destruction risk "
            f"if commodity prices reach extreme levels\n"
            f"   - CONSUMER IMPACT: How this affects everyday life GLOBALLY — "
            f"fuel prices (US, India, EU), food costs (especially in import-dependent nations "
            f"like Egypt, India, Indonesia), utility bills, travel expenses. "
            f"Include estimated magnitude with regional variation. "
            f"Use inflation pass-through rates and EM vulnerability data from knowledge base\n\n"
            f"3. Compare to historical parallels with specific price impacts "
            f"(reference crisis data from knowledge base if relevant)\n"
            f"4. Note seasonal patterns for the current month if relevant\n"
            f"5. If the user has portfolio holdings, highlight which ones appear in each tier "
            f"— but always show the FULL analysis for all tiers regardless\n"
            f"6. Note what is already priced in vs. what hasn't moved yet — "
            f"compare across regions (US vs EM pricing efficiency)\n"
            f"7. Provide probability-weighted estimates: "
            f"'Base case (60%): ... Bull (25%): ... Bear (15%): ...'\n"
            f"8. Suggest specific investment opportunities or hedges across ALL tiers "
            f"and across global markets (not just US). Include FX hedges where relevant\n\n"
            f"Structure your Final Answer with clear PRIMARY IMPACT / SECONDARY IMPACT / "
            f"TERTIARY IMPACT / CONSUMER IMPACT sections."
        )

        self._scenario_worker = _ScenarioWorker(self._state.agent, task)
        self._scenario_worker.chunk_received.connect(self._on_scenario_chunk)
        self._scenario_worker.finished.connect(self._on_scenario_done)
        self._scenario_worker.error.connect(self._on_scenario_error)
        self._scenario_worker.start()

    def _retry_analyse(self) -> None:
        """Retry scenario analysis after waiting for agent init."""
        if self._state.agent is not None and self._pending_scenario:
            self._scenario_input.setText(self._pending_scenario)
            self._pending_scenario = None
            self._analyse_btn.setEnabled(True)
            self._on_analyse_clicked()
        elif self._pending_scenario:
            self._scenario_status.setText("Still waiting for agent...")
            QTimer.singleShot(1000, self._retry_analyse)
        else:
            self._analyse_btn.setEnabled(True)
            self._scenario_status.setText("")

    def _on_scenario_chunk(self, chunk: str) -> None:
        self._accumulated_text += chunk
        # Show streaming progress
        lines = self._accumulated_text.count("\n")
        self._scenario_status.setText(f"Analysing scenario... ({lines} lines)")

    def _on_scenario_done(self, result: str) -> None:
        text = result or self._accumulated_text
        portfolio_tickers = {h["ticker"] for h in self._state.portfolio}
        self._result_panel.set_result(text, portfolio_tickers)
        self._result_panel.show()
        self._scenario_status.setText("Analysis complete.")
        self._cleanup_scenario()

    def _on_scenario_error(self, err: str) -> None:
        self._scenario_status.setText(f"Error: {err}")
        # Still show partial results if any
        if self._accumulated_text:
            portfolio_tickers = {h["ticker"] for h in self._state.portfolio}
            self._result_panel.set_result(self._accumulated_text, portfolio_tickers)
            self._result_panel.show()
        self._cleanup_scenario()

    def _cleanup_scenario(self) -> None:
        self._analyse_btn.setEnabled(True)
        if self._scenario_worker is not None:
            try:
                self._scenario_worker.chunk_received.disconnect()
                self._scenario_worker.finished.disconnect()
                self._scenario_worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

    # ── Commodity Detail Panel (Phase 4) ─────────────────────────────────

    def _on_card_clicked(self, symbol: str, name: str) -> None:
        """Toggle the commodity detail panel for the clicked card."""
        if self._detail_symbol == symbol and self._detail_panel.isVisible():
            self._detail_panel.hide()
            self._detail_symbol = None
            return

        self._detail_symbol = symbol
        self._detail_panel.show()

        # Show cached data immediately or fetch
        if symbol in self._cached_technicals:
            self._detail_panel.update_data(symbol, name, self._cached_technicals[symbol])
        else:
            # Set loading state and fetch in background
            self._detail_panel._title.setText(f"TECHNICAL ANALYSIS — {name} ({symbol})  loading...")
            asyncio.ensure_future(self._fetch_and_show_technicals(symbol, name))

    async def _fetch_and_show_technicals(self, symbol: str, name: str) -> None:
        """Fetch technical indicators for a commodity and update the detail panel."""
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _fetch_commodity_technicals, symbol)
        self._cached_technicals[symbol] = data
        # Only update if still showing the same symbol
        if self._detail_symbol == symbol:
            self._detail_panel.update_data(symbol, name, data)

    # ── Risk Metrics (Phase 6) ───────────────────────────────────────────

    async def _compute_and_show_risk(self) -> None:
        """Compute portfolio risk metrics: VaR, drawdown, commodity betas, stress tests."""
        if not self._state.portfolio:
            self._risk_panel.show_error("No portfolio holdings — add holdings in Portfolio view")
            return

        self._risk_compute_btn.setEnabled(False)
        self._risk_panel.show_error("Computing risk metrics...")

        loop = asyncio.get_event_loop()
        try:
            metrics = await loop.run_in_executor(
                None, _compute_risk_metrics, self._state.portfolio
            )
            self._cached_risk = metrics
            self._risk_panel.update_metrics(metrics)
        except Exception as exc:
            self._risk_panel.show_error(f"Error computing risk: {exc}")
        finally:
            self._risk_compute_btn.setEnabled(True)

    # ── Correlation Matrix (Phase 5) ─────────────────────────────────────

    async def _compute_correlations(self) -> None:
        """Compute 90-day correlation matrix for all commodities."""
        self._corr_btn.setEnabled(False)
        self._corr_btn.setText("Computing...")

        loop = asyncio.get_event_loop()
        try:
            labels, corr_values, summary = await loop.run_in_executor(
                None, _compute_correlation_matrix
            )
            if not corr_values:
                self._corr_btn.setText("No data — retry")
                self._corr_btn.setEnabled(True)
                return

            # Render heatmap
            from services.macro_charts import render_correlation_heatmap
            png = await loop.run_in_executor(
                None, render_correlation_heatmap, corr_values, labels, 10.0, 8.0
            )
            if png:
                img = QImage.fromData(png)
                self._corr_image.setPixmap(QPixmap.fromImage(img))
                self._corr_image.show()

            if summary:
                self._corr_summary.setText(summary)
                self._corr_summary.show()

            self._corr_btn.setText("Recompute")
        except Exception as exc:
            self._corr_btn.setText(f"Error: {exc}")
        finally:
            self._corr_btn.setEnabled(True)

    # ── Macro Indicators Panel (Phase 8) ─────────────────────────────────

    async def _update_indicators_panel(self) -> None:
        """Fetch FRED data and show as chip-style indicators."""
        loop = asyncio.get_event_loop()
        try:
            from services.research import fetch_fred_indicators
            fred = await loop.run_in_executor(None, fetch_fred_indicators)
        except Exception:
            return

        if not fred:
            return  # keep placeholder text

        # Remove placeholder
        self._indicators_placeholder.hide()

        # Clear all existing indicator chips, rebuild fresh
        while self._indicators_grid.count():
            item = self._indicators_grid.takeAt(0)
            w = item.widget()
            if w and w is not self._indicators_placeholder:
                w.deleteLater()
        self._indicators_chip_count = 0

        for sid, info in fred.items():
            val = info["value"]
            prev = info.get("previous")
            name = info["name"]
            unit = info.get("unit", "")

            # Format value
            if unit == "%":
                val_str = f"{val:.2f}%"
            else:
                val_str = f"{val:,.1f}"

            # Contextual signal coloring
            from services.macro_signals import get_fred_signal
            signal = get_fred_signal(sid, val, prev)
            chip_color = _SIGNAL_COLOR_MAP.get(signal["color"], TEXT_2)
            zone_label = signal["zone_label"]

            change_str = ""
            if prev is not None:
                delta = val - prev
                if abs(delta) > 0.001:
                    sign = "+" if delta >= 0 else ""
                    change_str = f" ({sign}{delta:.2f})"

            chip = QFrame()
            chip.setStyleSheet(
                f"QFrame {{ background-color: {SURFACE_2}; border: none; border-radius: 10px; }}"
            )
            cl = QVBoxLayout(chip)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(1)

            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; background: transparent;")
            val_text = f"{val_str}{change_str}"
            v_lbl = QLabel(val_text)
            v_lbl.setStyleSheet(f"color: {chip_color}; font-size: 12px; font-weight: 600; background: transparent;")
            if zone_label:
                z_lbl = QLabel(zone_label)
                z_lbl.setStyleSheet(f"color: {chip_color}; font-size: 9px; background: transparent;")

            cl.addWidget(n_lbl)
            cl.addWidget(v_lbl)
            if zone_label:
                cl.addWidget(z_lbl)

            row, col = divmod(self._indicators_chip_count, _COLS)
            self._indicators_grid.addWidget(chip, row, col)
            self._indicators_chip_count += 1


# ── Module-level helper functions (run in thread pool) ──────────────────────


def _fetch_commodity_technicals(symbol: str) -> dict:
    """Download 6-month history and compute all technicals. Thread-safe."""
    try:
        import yfinance as yf
        from services.indicators import calc_commodity_technicals

        hist = yf.Ticker(symbol).history(period="6mo")
        if hist.empty or len(hist) < 30:
            return {}
        return calc_commodity_technicals(hist)
    except Exception:
        return {}


def _compute_risk_metrics(portfolio: list[dict]) -> dict:
    """Compute VaR, max drawdown, commodity betas, stress tests. Thread-safe."""
    import numpy as np
    import yfinance as yf

    tickers = [h["ticker"] for h in portfolio]
    weights_map = {}
    total_value = 0.0
    for h in portfolio:
        val = h["qty"] * h["avg_cost"]
        weights_map[h["ticker"]] = val
        total_value += val

    if total_value == 0:
        return {}

    # Normalize weights
    for t in weights_map:
        weights_map[t] /= total_value

    # Download 90 days of data for portfolio tickers + key commodities + SPY
    commodity_syms = ["CL=F", "GC=F", "NG=F", "HG=F"]
    all_syms = list(set(tickers + commodity_syms + ["SPY"]))

    try:
        data = yf.download(all_syms, period="90d", progress=False, threads=True)
        if data.empty:
            return {}
        closes = data["Close"].dropna(how="all")
    except Exception:
        return {}

    returns = closes.pct_change().dropna()
    if len(returns) < 10:
        return {}

    # Weighted portfolio returns
    port_returns = np.zeros(len(returns))
    for t, w in weights_map.items():
        if t in returns.columns:
            port_returns += returns[t].fillna(0).values * w

    result: dict = {}

    # VaR
    result["var_95"] = float(np.percentile(port_returns, 5) * 100)
    result["var_99"] = float(np.percentile(port_returns, 1) * 100)

    # Max Drawdown
    cum = np.cumprod(1 + port_returns)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak * 100
    result["max_drawdown"] = float(np.min(dd))

    # Commodity betas
    betas = {}
    for csym in commodity_syms:
        if csym not in returns.columns:
            continue
        cr = returns[csym].fillna(0).values
        cov_val = np.cov(port_returns, cr)[0, 1]
        var_val = np.var(cr)
        if var_val > 1e-10:
            betas[_SYMBOL_NAMES.get(csym, csym)] = float(cov_val / var_val)
    result["commodity_betas"] = betas

    # Stress tests: what if commodity moves ±20%?
    stresses = []
    for csym in commodity_syms:
        name = _SYMBOL_NAMES.get(csym, csym)
        beta = betas.get(name, 0.0)
        for move_pct, move_label in [(20, "+20%"), (-20, "-20%")]:
            impact = beta * move_pct
            stresses.append({
                "commodity": name,
                "move": move_label,
                "portfolio_impact": round(impact, 2),
            })
    result["stress_tests"] = stresses

    return result


def _compute_correlation_matrix() -> tuple[list[str], list[list[float]], str]:
    """Compute 90-day correlation matrix for all commodities. Thread-safe.

    Returns (labels, corr_values_2d, summary_text).
    """
    import numpy as np
    import yfinance as yf

    symbols = []
    names = []
    for cat, items in COMMODITY_CATEGORIES.items():
        for name, sym in items.items():
            symbols.append(sym)
            names.append(name)

    try:
        data = yf.download(symbols, period="90d", progress=False, threads=True)
        if data.empty:
            return [], [], ""
        closes = data["Close"].dropna(how="all")
    except Exception:
        return [], [], ""

    # Only keep symbols with enough data
    valid_syms = []
    valid_names = []
    for sym, name in zip(symbols, names):
        if sym in closes.columns and closes[sym].notna().sum() >= 20:
            valid_syms.append(sym)
            valid_names.append(name)

    if len(valid_syms) < 3:
        return [], [], ""

    returns = closes[valid_syms].pct_change().dropna()
    if len(returns) < 10:
        return [], [], ""

    corr = returns.corr().values.tolist()

    # Build summary of strongest correlations
    n = len(valid_names)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((valid_names[i], valid_names[j], corr[i][j]))

    pairs.sort(key=lambda x: abs(x[2]), reverse=True)

    summary_lines = []
    pos = [p for p in pairs if p[2] > 0.5][:3]
    neg = [p for p in pairs if p[2] < -0.3][:3]

    if pos:
        summary_lines.append("Strongest positive: " + ", ".join(
            f"{a}/{b} ({v:.2f})" for a, b, v in pos
        ))
    if neg:
        summary_lines.append("Strongest negative: " + ", ".join(
            f"{a}/{b} ({v:.2f})" for a, b, v in neg
        ))

    return valid_names, corr, "  |  ".join(summary_lines) if summary_lines else ""
