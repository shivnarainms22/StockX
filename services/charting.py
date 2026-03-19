"""
StockX — Portfolio performance chart rendering.
Returns a PNG as raw bytes using matplotlib with the app dark theme.
"""
from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

APP_BG    = "#0C0C0E"
ACCENT    = "#D4A843"
ACCENT_CYAN = "#BFA76E"
TEXT_2    = "#87878F"
SURFACE_2 = "#1A1A1D"
POSITIVE  = "#34D399"
NEGATIVE  = "#FB7185"


def render_portfolio_chart(snapshots: list[dict]) -> bytes:
    """
    Render a line chart of portfolio value over time.

    Args:
        snapshots: list of {"date": "YYYY-MM-DD", "value": float, "currency": str}

    Returns:
        PNG image bytes. Returns empty bytes on error.
    """
    if len(snapshots) < 2:
        return b""

    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend — must be before pyplot import
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime

        dates = [datetime.strptime(s["date"], "%Y-%m-%d") for s in snapshots]
        values = [s["value"] for s in snapshots]

        fig, ax = plt.subplots(figsize=(8, 2.4), dpi=110)
        fig.patch.set_facecolor(APP_BG)
        ax.set_facecolor(SURFACE_2)

        # Fill area under the line
        ax.fill_between(dates, values, alpha=0.18, color=ACCENT)
        ax.plot(dates, values, color=ACCENT, linewidth=2, solid_capstyle="round")

        # Axes styling
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.tick_params(colors=TEXT_2, labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#1E1E22")
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")

        # Grid
        ax.yaxis.grid(True, color="#1E1E22", linewidth=0.6, linestyle="--")
        ax.set_axisbelow(True)
        ax.xaxis.grid(False)

        # Currency label on rightmost tick
        currency = snapshots[-1].get("currency", "USD")
        sym_map = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥", "CAD": "CA$"}
        sym = sym_map.get(currency, f"{currency} ")
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"{sym}{x:,.0f}")
        )

        fig.autofmt_xdate(rotation=0, ha="center")
        plt.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=APP_BG, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception:
        return b""


def render_sparkline(prices: list[float], up: bool = True) -> bytes:
    """
    Render a tiny 7-bar sparkline (item 7).
    Returns PNG bytes at 1.5×0.4 inches / 100 DPI.
    """
    if len(prices) < 2:
        return b""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        color = POSITIVE if up else NEGATIVE
        fig, ax = plt.subplots(figsize=(1.5, 0.4), dpi=100)
        fig.patch.set_facecolor("none")
        ax.set_facecolor("none")

        x = list(range(len(prices)))
        ax.plot(x, prices, color=color, linewidth=1.5, solid_capstyle="round")
        ax.fill_between(x, prices, alpha=0.20, color=color)
        ax.axis("off")
        plt.tight_layout(pad=0)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return b""


def render_pnl_chart(snapshots: list[dict]) -> bytes:
    """
    Render a % return chart normalised to first snapshot value (item 10).
    Returns PNG bytes.
    """
    if len(snapshots) < 2:
        return b""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime

        dates  = [datetime.strptime(s["date"], "%Y-%m-%d") for s in snapshots]
        values = [s["value"] for s in snapshots]
        v0     = values[0] if values[0] != 0 else 1.0
        pcts   = [(v - v0) / v0 * 100 for v in values]

        up_color = POSITIVE if pcts[-1] >= 0 else NEGATIVE

        fig, ax = plt.subplots(figsize=(8, 2.4), dpi=110)
        fig.patch.set_facecolor(APP_BG)
        ax.set_facecolor(SURFACE_2)

        ax.axhline(0, color="#1E1E22", linewidth=1, linestyle="--")
        ax.fill_between(dates, pcts, alpha=0.18, color=up_color)
        ax.plot(dates, pcts, color=up_color, linewidth=2, solid_capstyle="round")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.tick_params(colors=TEXT_2, labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#1E1E22")
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.yaxis.grid(True, color="#1E1E22", linewidth=0.6, linestyle="--")
        ax.set_axisbelow(True)
        ax.xaxis.grid(False)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:+.1f}%"))

        fig.autofmt_xdate(rotation=0, ha="center")
        plt.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=APP_BG, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return b""


def render_comparison_chart(snapshots: list[dict], benchmark: str = "SPY") -> bytes:
    """
    Render portfolio vs benchmark overlay, both normalised to 100 (item 11).
    benchmark is fetched via yfinance (blocking — call via executor).
    Returns PNG bytes.
    """
    if len(snapshots) < 2 or not benchmark:
        return b""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
        import yfinance as yf

        snap_dates  = [datetime.strptime(s["date"], "%Y-%m-%d") for s in snapshots]
        snap_values = [s["value"] for s in snapshots]

        start = snap_dates[0].strftime("%Y-%m-%d")
        end   = snap_dates[-1].strftime("%Y-%m-%d")
        bm_hist = yf.Ticker(benchmark).history(start=start, end=end)

        # Build date→close dict for benchmark
        bm_dict: dict[str, float] = {}
        for idx, row in bm_hist.iterrows():
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            bm_dict[d] = float(row["Close"])

        # Inner join on dates
        common_dates, port_vals, bm_vals = [], [], []
        for s in snapshots:
            if s["date"] in bm_dict:
                common_dates.append(datetime.strptime(s["date"], "%Y-%m-%d"))
                port_vals.append(s["value"])
                bm_vals.append(bm_dict[s["date"]])

        if len(common_dates) < 2:
            return render_portfolio_chart(snapshots)

        # Normalise both to 100 at first common point
        p0 = port_vals[0] or 1.0
        b0 = bm_vals[0]   or 1.0
        port_norm = [v / p0 * 100 for v in port_vals]
        bm_norm   = [v / b0 * 100 for v in bm_vals]

        fig, ax = plt.subplots(figsize=(8, 2.4), dpi=110)
        fig.patch.set_facecolor(APP_BG)
        ax.set_facecolor(SURFACE_2)

        ax.plot(common_dates, port_norm, color=ACCENT, linewidth=2,
                solid_capstyle="round", label="Portfolio")
        ax.plot(common_dates, bm_norm, color=ACCENT_CYAN, linewidth=1.5,
                solid_capstyle="round", linestyle="--", label=benchmark)

        ax.legend(loc="upper left", framealpha=0, labelcolor=TEXT_2, fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.tick_params(colors=TEXT_2, labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor("#1E1E22")
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.yaxis.grid(True, color="#1E1E22", linewidth=0.6, linestyle="--")
        ax.set_axisbelow(True)
        ax.xaxis.grid(False)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}"))

        fig.autofmt_xdate(rotation=0, ha="center")
        plt.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=APP_BG, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return b""
