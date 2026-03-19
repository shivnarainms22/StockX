# StockX GUI Premium Redesign — Design Spec

**Date:** 2026-03-18
**Status:** Approved

## Problem

The current GUI feels dated and cheap due to: emoji nav icons, toolbar-style header bars on every view, spreadsheet-like QTableWidget usage, cramped boxy layouts with visible borders everywhere.

## Design Decisions

### 1. Navigation — Top Bar (replaces sidebar)

- **Remove** the 80px NavSidebar entirely
- **Add** a 52px top navigation bar:
  - Left: "StockX" brand text (bold, ACCENT color)
  - Center: 7 text-only tab items (Analysis, Watchlist, Portfolio, News, Earnings, Markets, Settings)
  - Active tab: ACCENT-colored text + 2px bottom border indicator
  - Inactive tabs: TEXT_2 color, no underline
  - No icons anywhere in the nav
- Ctrl+1–7 shortcuts remain functional
- Layout changes from QHBoxLayout (sidebar + stack) to QVBoxLayout (topbar + stack)

### 2. Data Display — Modern List Rows (replaces QTableWidget)

**Watchlist:**
- Replace QTableWidget with QScrollArea containing custom QFrame rows
- Each row: full-width, 14px border-radius, 16px vertical padding
- Alternating backgrounds: SURFACE_2 / SURFACE_1
- Row contents L→R: 2-letter avatar badge (accent-tinted bg, 10px radius) → Ticker + company name (stacked) → sparkline area → price + change % (stacked) → RSI value → action icons (edit/delete, hover-reveal only)
- Clicking a row navigates to Analysis
- No column headers — layout is self-explanatory
- "Add" button next to page title

**Portfolio:**
- Top: 2–3 summary cards in horizontal row (Total Value, Total P&L, Annual Dividends)
- Cards: borderless, SURFACE_2 bg, 14px radius, label/value/subtext
- Chart area below cards (existing matplotlib PNG, just more padding)
- Chart mode toggle: pill-group style buttons
- Below chart: list rows same style as watchlist
- Row contents: ticker, qty, avg cost, price, value, P&L $, P&L %, annual income

**Earnings:**
- List rows same style as watchlist
- Rows with ≤7 days until earnings: accent-tinted background + 3px left accent border
- Row contents: ticker, date, days-until badge, EPS estimate, revenue estimate

### 3. View Headers — Page Titles (replaces header bar frames)

- Remove QFrame#HeaderBar from all views
- Each view starts with: 24px bold title + 13px muted subtitle (optional)
- Action buttons (refresh, add) sit inline next to title, right-aligned
- 32px horizontal padding, 24px top padding on all views

### 4. News — Card Grid (replaces stacked list)

- 2-column grid layout using QGridLayout
- Each card: borderless QFrame, SURFACE_2 bg, 14px radius, 20px padding
- Contents: headline (14px, semibold), ticker chip (accent-tinted pill), source + timestamp + sentiment dot
- Click opens URL in browser
- Hover: background lightens to SURFACE_3

### 5. Markets Heatmap — Cleaner Tiles

- Keep 3-column grid structure
- Remove borders, increase radius to 14px, more padding (16px)
- Bigger % change text (18px, bold)
- Same color-coding logic (green/red tint backgrounds)

### 6. Settings — Borderless Cards

- Remove borders from section cards
- Increase padding to 24px
- Section titles: 11px uppercase, accent color, letter-spacing
- Wider inputs with SURFACE_1 background
- Bigger save button (14px, 12px vertical padding)

### 7. Analysis — Spacing Refinements

- Large page title + subtitle (same pattern as other views)
- Chips: pill buttons with accent-tint background, no borders
- Agent bubbles: SURFACE_2 bg, no border
- 12px gap between messages (up from 4px)
- Score card: borderless styling
- Input bar: more padding, larger send button

### 8. Global Stylesheet

- 14px base font, "Segoe UI Variable" / "Segoe UI"
- Borderless cards and inputs (border: none or transparent)
- Depth via surface color layering, not outlines
- Scrollbars: transparent track, faint white-opacity handles
- Selection highlight: accent at 10-20% opacity
- Button hover: background shift only, no border color change

## Files Affected

- `gui/app.py` — Replace NavSidebar with TopNavBar, change MainWindow layout from HBox to VBox
- `gui/theme.py` — Stylesheet updates (already partially done)
- `gui/views/analysis.py` — Remove header bar frame, add page title, adjust spacing
- `gui/views/watchlist.py` — Full rewrite: QTableWidget → QScrollArea with row QFrames
- `gui/views/portfolio.py` — Full rewrite: QTableWidget → QScrollArea with row QFrames, keep summary cards
- `gui/views/news.py` — Rewrite to 2-column QGridLayout of card QFrames
- `gui/views/earnings.py` — Rewrite: QTableWidget → QScrollArea with row QFrames
- `gui/views/heatmap.py` — Minor: remove borders, increase radius/padding/font
- `gui/views/settings.py` — Minor: remove card borders, increase padding
- `services/charting.py` — Update color constants to match new palette

## Constraints

- Must preserve all existing functionality (data flow, state persistence, threading model)
- AnalysisWorker threading model must not change
- All view cross-navigation (switch_to_analysis) must still work
- Keyboard shortcuts Ctrl+1–7 must still work
- Monitor service and alert system unchanged
- No new dependencies
