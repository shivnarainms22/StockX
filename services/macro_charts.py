"""
StockX — Macro-specific chart renderers.
Correlation heatmap for commodity/portfolio analysis.
"""
from __future__ import annotations

import io

POSITIVE = "#34D399"
NEGATIVE = "#FB7185"
TEXT_2   = "#87878F"


def render_correlation_heatmap(
    corr_values: list[list[float]],
    labels: list[str],
    width: float = 8.0,
    height: float = 6.5,
) -> bytes:
    """Render a correlation matrix heatmap. Returns PNG bytes.

    Args:
        corr_values: 2D list of correlation coefficients (-1 to 1).
        labels: axis labels matching the matrix dimensions.
    """
    if not corr_values or not labels:
        return b""

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        import numpy as np

        n = len(labels)
        data = np.array(corr_values)

        fig, ax = plt.subplots(figsize=(width, height), dpi=100)
        fig.patch.set_facecolor("#0C0C0E")
        ax.set_facecolor("#0C0C0E")

        # Diverging colormap: red (-1) -> dark gray (0) -> green (+1)
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "corr", [NEGATIVE, "#1A1A1D", POSITIVE], N=256
        )

        im = ax.imshow(data, cmap=cmap, vmin=-1, vmax=1, aspect="auto")

        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7, color=TEXT_2)
        ax.set_yticklabels(labels, fontsize=7, color=TEXT_2)

        # Annotate cells
        for i in range(n):
            for j in range(n):
                val = data[i, j]
                weight = "bold" if abs(val) > 0.7 else "normal"
                color = "#ECECF0" if abs(val) > 0.3 else "#87878F"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=6, color=color, fontweight=weight)

        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.tick_params(length=0)
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Correlation")
        cbar.ax.yaxis.label.set_color(TEXT_2)
        cbar.ax.tick_params(colors=TEXT_2)

        plt.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor(),
                    bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception:
        return b""
