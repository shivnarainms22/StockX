"""Generate assets/icon.ico (branded bar-chart) for the PyInstaller exe icon.

Build-time tool. The drawing mirrors gui/app.py::_make_window_icon (runtime
window icon); kept standalone so the build doesn't import the full GUI stack.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication


def main() -> None:
    app = QApplication([])  # required for QPixmap rendering
    size = 256
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor("#0B0F1A")))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 40, 40)

    accent = QColor("#00C896")
    p.setBrush(QBrush(accent))
    bars = [(28, 42, 76), (84, 42, 118), (140, 42, 158), (196, 42, 200)]
    for bx, bw, bh in bars:
        p.drawRoundedRect(bx, size - bh - 18, bw, bh, 7, 7)

    pen = QPen(accent, 7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    points = [QPoint(bx + bw // 2, size - bh - 18) for bx, bw, bh in bars]
    for i in range(len(points) - 1):
        p.drawLine(points[i], points[i + 1])
    p.end()

    out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out), "ICO")
    print(f"wrote {out}")
    app.quit()


if __name__ == "__main__":
    main()
