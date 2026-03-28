"""
StockX GUI — News Feed view (PyQt6).
Aggregates yfinance news for all watchlist tickers. Auto-loads on first show.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from gui.state import AppState
from gui.theme import (
    ACCENT, ACCENT_CYAN, ACCENT_GLOW, BORDER_CARD, BORDER_SUBTLE,
    NEGATIVE, POSITIVE, SURFACE_1, SURFACE_2, SURFACE_3, TEXT_1, TEXT_2, TEXT_MUTED,
)

if TYPE_CHECKING:
    from gui.app import MainWindow


def _time_ago(ts: int | float) -> str:
    delta = int(time.time() - ts)
    if delta < 60:   return "just now"
    if delta < 3600: return f"{delta // 60}m ago"
    if delta < 86400:return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


class _NewsCard(QFrame):
    """Clickable news card that opens the article URL."""

    def __init__(self, article: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._url = article.get("url", "")
        if self._url:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setObjectName("Card")
        self.setStyleSheet(
            f"QFrame#Card {{ background-color: {SURFACE_2}; border: none; border-radius: 14px; }}"
            f"QFrame#Card:hover {{ background-color: {SURFACE_3}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        headline = QLabel(article["title"])
        headline.setWordWrap(True)
        headline.setStyleSheet(f"color: {TEXT_1}; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        headline.setMaximumHeight(60)

        ticker_chip = QLabel(article["ticker"])
        ticker_chip.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 600;"
            f"background-color: rgba(212,168,67,0.08); border-radius: 12px; padding: 3px 10px;"
        )
        ticker_chip.setFixedHeight(18)

        source_lbl = QLabel(f"{article['publisher']}  ·  {_time_ago(article['ts'])}")
        source_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")

        # Sentiment dot (item 17)
        score = article.get("sentiment", 0.5)
        if score >= 0.6:
            sent_color = POSITIVE
        elif score <= 0.4:
            sent_color = NEGATIVE
        else:
            sent_color = TEXT_MUTED
        sent_dot = QLabel("●")
        sent_dot.setToolTip(
            f"Sentiment: {'Bullish' if score >= 0.6 else ('Bearish' if score <= 0.4 else 'Neutral')} ({score:.2f})"
        )
        sent_dot.setStyleSheet(
            f"color: {sent_color}; font-size: 10px; background: transparent; border: none;"
        )

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta_row.addWidget(ticker_chip)
        meta_row.addWidget(source_lbl)
        meta_row.addStretch()
        meta_row.addWidget(sent_dot)

        layout.addWidget(headline)
        layout.addLayout(meta_row)

    def mousePressEvent(self, event) -> None:
        if self._url:
            QDesktopServices.openUrl(QUrl(self._url))
        super().mousePressEvent(event)


class NewsView(QWidget):
    def __init__(self, state: AppState, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._mw    = main_window
        self._setup_ui()
        # Auto-load on startup (matches Flet behavior)
        asyncio.get_event_loop().create_task(self._refresh())

    # ── UI construction ───────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        # Scroll area for news cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self._body_widget = QWidget()
        self._body_layout = QGridLayout(self._body_widget)
        self._body_layout.setContentsMargins(32, 12, 32, 16)
        self._body_layout.setSpacing(12)

        # Initial loading label — _clear_cards() will remove it on first refresh
        loading_lbl = QLabel("Loading news...")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; font-style: italic;")
        self._body_layout.addWidget(loading_lbl)

        scroll.setWidget(self._body_widget)
        root.addWidget(scroll, stretch=1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h = QHBoxLayout(header)
        h.setContentsMargins(32, 20, 32, 8)
        h.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("News")
        title.setStyleSheet(f"color: {TEXT_1}; font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Latest financial headlines")
        subtitle.setStyleSheet(f"color: {TEXT_2}; font-size: 13px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        h.addLayout(title_col)
        h.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_2}; background: {SURFACE_2}; border: none; border-radius: 10px; padding: 6px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {SURFACE_3}; }}"
        )
        self._refresh_btn.clicked.connect(
            lambda: asyncio.get_event_loop().create_task(self._refresh())
        )

        h.addWidget(self._refresh_btn)
        return header

    # ── Data loading ──────────────────────────────────────────────────────

    def _clear_cards(self) -> None:
        while self._body_layout.count():
            child = self._body_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    async def _refresh(self, _e=None) -> None:
        import yfinance as yf

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Loading…")
        self._clear_cards()

        tickers = [item["ticker"] for item in self._state.watchlist]
        if not tickers:
            lbl = QLabel("Add tickers to your Watchlist to see news here")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; font-style: italic;")
            self._body_layout.addWidget(lbl)
            self._refresh_btn.setEnabled(True)
            self._refresh_btn.setText("Refresh")
            return

        # Loading indicator
        loading_lbl = QLabel("  ⟳ Loading news...")
        loading_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; font-style: italic; padding: 16px;")
        self._body_layout.addWidget(loading_lbl)

        def _fetch_news():
            from datetime import datetime, timezone
            seen: set[str] = set()
            items: list[dict] = []
            for t in tickers:
                try:
                    raw = yf.Ticker(t).news or []
                    for article in raw:
                        # yfinance ≥1.0 wraps everything under 'content'
                        c = article.get("content") or article
                        title = c.get("title") or ""
                        if not title:
                            continue
                        key = hashlib.md5(title.encode()).hexdigest()
                        if key in seen:
                            continue
                        seen.add(key)
                        # publisher
                        provider = c.get("provider") or {}
                        publisher = provider.get("displayName") or c.get("publisher") or ""
                        # timestamp — new API uses ISO string, old used Unix int
                        ts_raw = c.get("pubDate") or c.get("providerPublishTime") or 0
                        if isinstance(ts_raw, str):
                            try:
                                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
                            except ValueError:
                                ts = 0.0
                        else:
                            ts = float(ts_raw)
                        # url
                        canon = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
                        url = (canon.get("url") if isinstance(canon, dict) else "") or c.get("link") or ""
                        items.append({
                            "ticker":    t,
                            "title":     title,
                            "publisher": publisher,
                            "ts":        ts,
                            "url":       url,
                        })
                except Exception:
                    pass
            items.sort(key=lambda x: x["ts"], reverse=True)
            return items

        articles = await asyncio.get_event_loop().run_in_executor(None, _fetch_news)

        # Score sentiment for each headline (item 17)
        try:
            from services.sentiment import score_headline
            for art in articles:
                art["sentiment"] = score_headline(art["title"])
        except Exception:
            pass

        self._clear_cards()

        if not articles:
            no_news = QLabel("No news found for your watchlist tickers")
            no_news.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_news.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; font-style: italic; padding: 32px;")
            self._body_layout.addWidget(no_news)
        else:
            for i, art in enumerate(articles):
                card = _NewsCard(art)
                self._body_layout.addWidget(card, i // 2, i % 2)

        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Refresh")
