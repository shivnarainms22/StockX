"""
StockX GUI — Design system palette constants.
Modern Fintech aesthetic (Robinhood / Webull style).
Import from every view instead of hard-coding colour literals.
"""

APP_BG        = "#0C0C0E"   # Page background (true dark)
SURFACE_1     = "#141416"   # Headers, nav, table headings
SURFACE_2     = "#1A1A1D"   # Cards, inputs, chips, agent bubble
SURFACE_3     = "#222226"   # Hover states
SURFACE_DLG   = "#161618"   # Dialog background

ACCENT        = "#D4A843"   # Primary warm gold — CTA buttons, icons, focused borders
ACCENT_HOVER  = "#C09635"   # Gold hover state
ACCENT_GLOW   = "#D4A84320" # Gold 12% opacity — shadows / ripple ink
ACCENT_CYAN   = "#BFA76E"   # Muted warm gold — secondary accent (column headers, chip text)

TEXT_1        = "#ECECF0"   # Primary text (clean white)
TEXT_2        = "#87878F"   # Secondary text (softer)
TEXT_MUTED    = "#4A4A52"   # Hints, labels, disabled

BORDER_SUBTLE = "#1E1E22"   # Dividers — nearly invisible
BORDER_CARD   = "#232327"   # Card borders — very subtle
BORDER_INPUT  = "#2C2C32"   # TextField default border

POSITIVE      = "#34D399"   # Gain / oversold RSI (≤ 30) — emerald
NEGATIVE      = "#FB7185"   # Loss / overbought RSI (≥ 70) — rose

NAV_BG        = "#0A0A0C"   # Navigation rail background

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
QFrame#TopNavBar {{
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
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
    selection-background-color: rgba(212,168,67,0.20);
}}
QMainWindow {{ background-color: {APP_BG}; }}

/* ══ ScrollBar — thin & invisible until hovered ══════════════════════════ */
QScrollBar:vertical {{
    width: 5px; background: transparent; border: none; margin: 4px 1px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.08); border-radius: 2px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.15); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 5px; background: transparent; border: none; margin: 1px 4px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.08); border-radius: 2px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: rgba(255,255,255,0.15); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ══ Tables — borderless, spacious rows ══════════════════════════════════ */
QTableWidget {{
    background-color: {SURFACE_1};
    border: none;
    border-radius: 10px;
    gridline-color: {BORDER_SUBTLE};
    selection-background-color: rgba(212,168,67,0.10);
    outline: 0;
}}
QTableWidget::item {{ padding: 10px 12px; border: none; }}
QTableWidget::item:selected {{ background-color: rgba(212,168,67,0.10); color: {TEXT_1}; }}
QHeaderView::section {{
    background-color: {SURFACE_1}; color: {TEXT_2};
    font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;
    padding: 10px 12px; border: none;
    border-bottom: 1px solid {BORDER_SUBTLE};
}}
QHeaderView {{ background-color: {SURFACE_1}; border: none; }}

/* ══ Line & Text Edits — subtle, clean ═══════════════════════════════════ */
QLineEdit {{
    background-color: {SURFACE_2}; border: 1px solid transparent;
    border-radius: 10px; padding: 10px 14px; color: {TEXT_1}; font-size: 14px;
}}
QLineEdit:focus {{ border-color: {ACCENT}; background-color: {SURFACE_1}; }}
QLineEdit:disabled {{ color: {TEXT_MUTED}; }}

/* ══ Buttons — clean, generous padding ═══════════════════════════════════ */
QPushButton {{
    background-color: {SURFACE_2}; border: 1px solid transparent;
    border-radius: 10px; padding: 9px 20px; color: {TEXT_1}; font-size: 13px; font-weight: 500;
}}
QPushButton:hover {{ background-color: {SURFACE_3}; }}
QPushButton:pressed {{ background-color: {SURFACE_1}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; background-color: {SURFACE_1}; }}
QPushButton#AccentBtn {{
    background-color: {ACCENT}; border: none;
    color: #0C0C0E; font-weight: 600; font-size: 14px;
}}
QPushButton#AccentBtn:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton#AccentBtn:disabled {{ background-color: {TEXT_MUTED}; color: {SURFACE_1}; }}
QPushButton#DangerBtn {{
    color: {NEGATIVE}; background-color: transparent; border: 1px solid rgba(251,113,133,0.3);
}}
QPushButton#DangerBtn:hover {{ background-color: rgba(251,113,133,0.08); }}
QPushButton#Chip {{
    background-color: rgba(212,168,67,0.08); border: none;
    border-radius: 16px; padding: 6px 16px; color: {ACCENT}; font-size: 12px; font-weight: 600;
}}
QPushButton#Chip:hover {{ background-color: rgba(212,168,67,0.15); }}
QPushButton#IconBtn {{
    background-color: transparent; border: none;
    padding: 6px; color: {TEXT_2}; font-size: 16px; border-radius: 8px;
}}
QPushButton#IconBtn:hover {{ background-color: {SURFACE_3}; color: {TEXT_1}; }}
QPushButton#IconBtn:disabled {{ color: {TEXT_MUTED}; }}

/* ══ ComboBox ═════════════════════════════════════════════════════════════ */
QComboBox {{
    background-color: {SURFACE_2}; border: 1px solid transparent;
    border-radius: 10px; padding: 9px 14px; color: {TEXT_1}; font-size: 13px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ width: 0; height: 0; border: none; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2}; border: 1px solid {BORDER_CARD};
    border-radius: 8px;
    selection-background-color: rgba(212,168,67,0.12); color: {TEXT_1}; outline: 0;
    padding: 4px;
}}

/* ══ Slider — thicker track, bigger handle ═══════════════════════════════ */
QSlider::groove:horizontal {{
    background: {SURFACE_3}; height: 5px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT}; border: none;
    width: 16px; height: 16px; border-radius: 8px; margin: -6px 0;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}

/* ══ StatusBar — minimal ═════════════════════════════════════════════════ */
QStatusBar {{
    background-color: {APP_BG}; color: {TEXT_MUTED};
    font-size: 12px; border-top: 1px solid {BORDER_SUBTLE};
    padding: 4px 12px;
}}

/* ══ Dialog ═══════════════════════════════════════════════════════════════ */
QDialog {{ background-color: {SURFACE_DLG}; border-radius: 14px; }}

/* ══ Named frames ═════════════════════════════════════════════════════════ */
QFrame#TopNavBar {{
    background-color: {SURFACE_1}; border-bottom: 1px solid {BORDER_SUBTLE};
}}
QFrame#Card {{
    background-color: {SURFACE_2}; border: none; border-radius: 14px;
}}
QFrame#SummaryCard {{
    background-color: {SURFACE_2}; border: none; border-radius: 12px;
}}

/* ══ Labels ═══════════════════════════════════════════════════════════════ */
QLabel {{ background: transparent; color: {TEXT_1}; }}

/* ══ ToolTip ══════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {SURFACE_2}; color: {TEXT_1};
    border: none; border-radius: 8px; padding: 6px 10px; font-size: 12px;
}}

/* ══ RadioButton ══════════════════════════════════════════════════════════ */
QRadioButton {{ color: {TEXT_1}; background: transparent; spacing: 8px; }}
QRadioButton::indicator {{ width: 16px; height: 16px; }}
"""
