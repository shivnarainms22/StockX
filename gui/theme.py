"""
StockX GUI — Design system palette constants.
Modern Fintech aesthetic (Robinhood / Webull style).
Import from every view instead of hard-coding colour literals.
"""

APP_BG        = "#0B0F1A"   # Page background (deep ink navy)
SURFACE_1     = "#111827"   # Headers, nav, table headings
SURFACE_2     = "#1A2235"   # Cards, inputs, chips, agent bubble
SURFACE_3     = "#1F2A40"   # Hover states
SURFACE_DLG   = "#141E2E"   # Dialog background

ACCENT        = "#00C896"   # Primary teal — CTA buttons, icons, focused borders
ACCENT_HOVER  = "#00A87C"   # Teal hover state
ACCENT_GLOW   = "#00C89625" # Teal 15% opacity — shadows / ripple ink
ACCENT_CYAN   = "#3DD9EB"   # Cyan — secondary accent (column headers, chip text)

TEXT_1        = "#F0F4F8"   # Primary text
TEXT_2        = "#A0AEC0"   # Secondary text
TEXT_MUTED    = "#4A5568"   # Hints, labels, disabled

BORDER_SUBTLE = "#1E2D42"   # Dividers, section borders
BORDER_CARD   = "#243044"   # Card / chip / bubble borders
BORDER_INPUT  = "#2A3F5C"   # TextField default border

POSITIVE      = "#00D4AA"   # Gain / oversold RSI (≤ 30)
NEGATIVE      = "#FF6B6B"   # Loss / overbought RSI (≥ 70)

NAV_BG        = "#0D1422"   # Navigation rail background

# ── Currency helpers ──────────────────────────────────────────────────────────
_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",   "CAD": "CA$", "AUD": "A$",  "NZD": "NZ$", "HKD": "HK$",
    "SGD": "S$",  "MXN": "MX$","BRL": "R$",  "GBP": "£",   "EUR": "€",
    "JPY": "¥",   "CNY": "¥",  "CNH": "¥",   "INR": "₹",   "KRW": "₩",
    "CHF": "Fr",  "SEK": "kr", "NOK": "kr",  "DKK": "kr",  "ZAR": "R",
    "TRY": "₺",   "ILS": "₪",  "SAR": "﷼",  "AED": "د.إ", "TWD": "NT$",
    "THB": "฿",   "MYR": "RM", "IDR": "Rp",  "PHP": "₱",   "VND": "₫",
}

# Currencies that trade in whole numbers — no decimal places needed
_ZERO_DECIMAL: set[str] = {"JPY", "KRW", "VND", "IDR"}


def currency_symbol(code: str | None) -> str:
    """Return the symbol for a currency code, e.g. 'GBP' → '£'."""
    if not code:
        return "$"
    return _CURRENCY_SYMBOLS.get(code.upper(), f"{code.upper()} ")


def fmt_price(price: float, code: str | None) -> str:
    """Format a price with the correct currency symbol and decimal places."""
    sym = currency_symbol(code)
    if (code or "").upper() in _ZERO_DECIMAL:
        return f"{sym}{price:,.0f}"
    return f"{sym}{price:,.2f}"


# ── Light theme palette ───────────────────────────────────────────────────────
LIGHT_APP_BG        = "#F5F7FA"
LIGHT_SURFACE_1     = "#FFFFFF"
LIGHT_SURFACE_2     = "#F0F2F5"
LIGHT_SURFACE_3     = "#E8ECF0"
LIGHT_SURFACE_DLG   = "#E8ECF0"
LIGHT_ACCENT        = "#00A87C"
LIGHT_ACCENT_HOVER  = "#008F68"
LIGHT_ACCENT_CYAN   = "#0BA5C7"
LIGHT_TEXT_1        = "#1A202C"
LIGHT_TEXT_2        = "#4A5568"
LIGHT_TEXT_MUTED    = "#A0AEC0"
LIGHT_POSITIVE      = "#00A87C"
LIGHT_NEGATIVE      = "#E53E3E"
LIGHT_NAV_BG        = "#E2E8F0"
LIGHT_BORDER_SUBTLE = "#E2E8F0"
LIGHT_BORDER_CARD   = "#CBD5E0"
LIGHT_BORDER_INPUT  = "#A0AEC0"

LIGHT_STYLESHEET = f"""
/* ══ Global ══════════════════════════════════════════════════════════════ */
QWidget {{
    background-color: {LIGHT_APP_BG};
    color: {LIGHT_TEXT_1};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    selection-background-color: rgba(0,168,124,0.25);
}}
QMainWindow {{ background-color: {LIGHT_APP_BG}; }}

/* ══ ScrollBar ════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    width: 6px; background: {LIGHT_SURFACE_2}; border: none; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {LIGHT_BORDER_CARD}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 6px; background: {LIGHT_SURFACE_2}; border: none; border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {LIGHT_BORDER_CARD}; border-radius: 3px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ══ Tables ═══════════════════════════════════════════════════════════════ */
QTableWidget {{
    background-color: {LIGHT_SURFACE_1};
    border: 1px solid {LIGHT_BORDER_CARD};
    border-radius: 8px;
    gridline-color: {LIGHT_BORDER_CARD};
    selection-background-color: {LIGHT_SURFACE_3};
    outline: 0;
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{ background-color: {LIGHT_SURFACE_3}; color: {LIGHT_TEXT_1}; }}
QHeaderView::section {{
    background-color: {LIGHT_SURFACE_2}; color: {LIGHT_ACCENT_CYAN};
    font-size: 11px; font-weight: 600;
    padding: 7px 8px; border: none;
    border-bottom: 1px solid {LIGHT_BORDER_SUBTLE};
}}
QHeaderView {{ background-color: {LIGHT_SURFACE_2}; border: none; }}

/* ══ Line & Text Edits ════════════════════════════════════════════════════ */
QLineEdit {{
    background-color: {LIGHT_SURFACE_1}; border: 1px solid {LIGHT_BORDER_INPUT};
    border-radius: 8px; padding: 8px 12px; color: {LIGHT_TEXT_1};
}}
QLineEdit:focus {{ border-color: {LIGHT_ACCENT}; }}
QLineEdit:disabled {{ color: {LIGHT_TEXT_MUTED}; border-color: {LIGHT_BORDER_SUBTLE}; }}

/* ══ Buttons ══════════════════════════════════════════════════════════════ */
QPushButton {{
    background-color: {LIGHT_SURFACE_1}; border: 1px solid {LIGHT_BORDER_CARD};
    border-radius: 8px; padding: 7px 16px; color: {LIGHT_TEXT_1}; font-size: 13px;
}}
QPushButton:hover {{ background-color: {LIGHT_SURFACE_3}; border-color: {LIGHT_ACCENT}; }}
QPushButton:pressed {{ background-color: {LIGHT_SURFACE_2}; }}
QPushButton:disabled {{ color: {LIGHT_TEXT_MUTED}; border-color: {LIGHT_BORDER_SUBTLE}; background-color: {LIGHT_SURFACE_2}; }}
QPushButton#AccentBtn {{
    background-color: {LIGHT_ACCENT}; border-color: {LIGHT_ACCENT};
    color: #FFFFFF; font-weight: 600;
}}
QPushButton#AccentBtn:hover {{ background-color: {LIGHT_ACCENT_HOVER}; border-color: {LIGHT_ACCENT_HOVER}; }}
QPushButton#AccentBtn:disabled {{ background-color: {LIGHT_TEXT_MUTED}; border-color: {LIGHT_TEXT_MUTED}; color: {LIGHT_SURFACE_1}; }}
QPushButton#DangerBtn {{
    color: {LIGHT_NEGATIVE}; background-color: transparent; border-color: {LIGHT_NEGATIVE};
}}
QPushButton#DangerBtn:hover {{ background-color: rgba(229,62,62,0.10); }}
QPushButton#Chip {{
    background-color: {LIGHT_SURFACE_2}; border: 1px solid {LIGHT_BORDER_CARD};
    border-radius: 14px; padding: 4px 12px; color: {LIGHT_ACCENT_CYAN}; font-size: 12px;
}}
QPushButton#Chip:hover {{ background-color: {LIGHT_SURFACE_3}; border-color: {LIGHT_ACCENT_CYAN}; }}
QPushButton#IconBtn {{
    background-color: transparent; border: none;
    padding: 4px; color: {LIGHT_ACCENT}; font-size: 16px; border-radius: 6px;
}}
QPushButton#IconBtn:hover {{ background-color: {LIGHT_SURFACE_3}; }}
QPushButton#IconBtn:disabled {{ color: {LIGHT_TEXT_MUTED}; }}

/* ══ ComboBox ═════════════════════════════════════════════════════════════ */
QComboBox {{
    background-color: {LIGHT_SURFACE_1}; border: 1px solid {LIGHT_BORDER_INPUT};
    border-radius: 8px; padding: 7px 12px; color: {LIGHT_TEXT_1};
}}
QComboBox:focus {{ border-color: {LIGHT_ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ width: 0; height: 0; border: none; }}
QComboBox QAbstractItemView {{
    background-color: {LIGHT_SURFACE_1}; border: 1px solid {LIGHT_BORDER_CARD};
    selection-background-color: {LIGHT_SURFACE_3}; color: {LIGHT_TEXT_1}; outline: 0;
}}

/* ══ Slider ═══════════════════════════════════════════════════════════════ */
QSlider::groove:horizontal {{
    background: {LIGHT_SURFACE_3}; height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {LIGHT_ACCENT}; border: none;
    width: 14px; height: 14px; border-radius: 7px; margin: -5px 0;
}}
QSlider::sub-page:horizontal {{ background: {LIGHT_ACCENT}; border-radius: 2px; }}

/* ══ StatusBar ════════════════════════════════════════════════════════════ */
QStatusBar {{
    background-color: {LIGHT_SURFACE_2}; color: {LIGHT_TEXT_2};
    font-size: 12px; border-top: 1px solid {LIGHT_BORDER_SUBTLE};
}}

/* ══ Dialog ═══════════════════════════════════════════════════════════════ */
QDialog {{ background-color: {LIGHT_SURFACE_DLG}; }}

/* ══ Named frames ═════════════════════════════════════════════════════════ */
QFrame#NavSidebar {{
    background-color: {LIGHT_NAV_BG}; border-right: 1px solid {LIGHT_BORDER_SUBTLE};
}}
QFrame#HeaderBar {{
    background-color: {LIGHT_SURFACE_1}; border-bottom: 1px solid {LIGHT_BORDER_SUBTLE};
}}
QFrame#Card {{
    background-color: {LIGHT_SURFACE_1}; border: 1px solid {LIGHT_BORDER_CARD}; border-radius: 12px;
}}
QFrame#SummaryCard {{
    background-color: {LIGHT_SURFACE_1}; border: 1px solid {LIGHT_BORDER_CARD}; border-radius: 10px;
}}

/* ══ Labels ═══════════════════════════════════════════════════════════════ */
QLabel {{ background: transparent; color: {LIGHT_TEXT_1}; }}

/* ══ ToolTip ══════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {LIGHT_SURFACE_DLG}; color: {LIGHT_TEXT_1};
    border: 1px solid {LIGHT_BORDER_CARD}; border-radius: 6px; padding: 4px 8px;
}}

/* ══ RadioButton ══════════════════════════════════════════════════════════ */
QRadioButton {{ color: {LIGHT_TEXT_1}; background: transparent; spacing: 6px; }}
QRadioButton::indicator {{ width: 14px; height: 14px; }}
"""


def get_stylesheet(dark: bool = True) -> str:
    """Return the active QSS stylesheet for the given theme mode."""
    return STYLESHEET if dark else LIGHT_STYLESHEET


# ── PyQt6 QSS dark stylesheet ─────────────────────────────────────────────────
STYLESHEET = f"""
/* ══ Global ══════════════════════════════════════════════════════════════ */
QWidget {{
    background-color: {APP_BG};
    color: {TEXT_1};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    selection-background-color: rgba(0,200,150,0.25);
}}
QMainWindow {{ background-color: {APP_BG}; }}

/* ══ ScrollBar ════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    width: 6px; background: {SURFACE_1}; border: none; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_CARD}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 6px; background: {SURFACE_1}; border: none; border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_CARD}; border-radius: 3px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ══ Tables ═══════════════════════════════════════════════════════════════ */
QTableWidget {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_CARD};
    border-radius: 8px;
    gridline-color: {BORDER_CARD};
    selection-background-color: {SURFACE_3};
    outline: 0;
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{ background-color: {SURFACE_3}; color: {TEXT_1}; }}
QHeaderView::section {{
    background-color: {SURFACE_1}; color: {ACCENT_CYAN};
    font-size: 11px; font-weight: 600;
    padding: 7px 8px; border: none;
    border-bottom: 1px solid {BORDER_SUBTLE};
}}
QHeaderView {{ background-color: {SURFACE_1}; border: none; }}

/* ══ Line & Text Edits ════════════════════════════════════════════════════ */
QLineEdit {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_INPUT};
    border-radius: 8px; padding: 8px 12px; color: {TEXT_1};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled {{ color: {TEXT_MUTED}; border-color: {BORDER_SUBTLE}; }}

/* ══ Buttons ══════════════════════════════════════════════════════════════ */
QPushButton {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD};
    border-radius: 8px; padding: 7px 16px; color: {TEXT_1}; font-size: 13px;
}}
QPushButton:hover {{ background-color: {SURFACE_3}; border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: {SURFACE_1}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; border-color: {BORDER_SUBTLE}; background-color: {SURFACE_1}; }}
QPushButton#AccentBtn {{
    background-color: {ACCENT}; border-color: {ACCENT};
    color: {APP_BG}; font-weight: 600;
}}
QPushButton#AccentBtn:hover {{ background-color: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#AccentBtn:disabled {{ background-color: {TEXT_MUTED}; border-color: {TEXT_MUTED}; color: {SURFACE_1}; }}
QPushButton#DangerBtn {{
    color: {NEGATIVE}; background-color: transparent; border-color: {NEGATIVE};
}}
QPushButton#DangerBtn:hover {{ background-color: rgba(255,107,107,0.12); }}
QPushButton#Chip {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD};
    border-radius: 14px; padding: 4px 12px; color: {ACCENT_CYAN}; font-size: 12px;
}}
QPushButton#Chip:hover {{ background-color: {SURFACE_3}; border-color: {ACCENT_CYAN}; }}
QPushButton#IconBtn {{
    background-color: transparent; border: none;
    padding: 4px; color: {ACCENT}; font-size: 16px; border-radius: 6px;
}}
QPushButton#IconBtn:hover {{ background-color: {SURFACE_3}; }}
QPushButton#IconBtn:disabled {{ color: {TEXT_MUTED}; }}

/* ══ ComboBox ═════════════════════════════════════════════════════════════ */
QComboBox {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_INPUT};
    border-radius: 8px; padding: 7px 12px; color: {TEXT_1};
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ width: 0; height: 0; border: none; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD};
    selection-background-color: {SURFACE_3}; color: {TEXT_1}; outline: 0;
}}

/* ══ Slider ═══════════════════════════════════════════════════════════════ */
QSlider::groove:horizontal {{
    background: {SURFACE_3}; height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT}; border: none;
    width: 14px; height: 14px; border-radius: 7px; margin: -5px 0;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}

/* ══ StatusBar ════════════════════════════════════════════════════════════ */
QStatusBar {{
    background-color: {SURFACE_1}; color: {TEXT_2};
    font-size: 12px; border-top: 1px solid {BORDER_SUBTLE};
}}

/* ══ Dialog ═══════════════════════════════════════════════════════════════ */
QDialog {{ background-color: {SURFACE_DLG}; }}

/* ══ Named frames ═════════════════════════════════════════════════════════ */
QFrame#NavSidebar {{
    background-color: {NAV_BG}; border-right: 1px solid {BORDER_SUBTLE};
}}
QFrame#HeaderBar {{
    background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE};
}}
QFrame#Card {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD}; border-radius: 12px;
}}
QFrame#SummaryCard {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD}; border-radius: 10px;
}}

/* ══ Labels ═══════════════════════════════════════════════════════════════ */
QLabel {{ background: transparent; color: {TEXT_1}; }}

/* ══ ToolTip ══════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {SURFACE_DLG}; color: {TEXT_1};
    border: 1px solid {BORDER_CARD}; border-radius: 6px; padding: 4px 8px;
}}

/* ══ RadioButton ══════════════════════════════════════════════════════════ */
QRadioButton {{ color: {TEXT_1}; background: transparent; spacing: 6px; }}
QRadioButton::indicator {{ width: 14px; height: 14px; }}
"""
