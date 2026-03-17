"""
StockX — System tray / toast notifications via plyer.
Falls back silently if plyer is unavailable or the platform doesn't support it.
"""
from __future__ import annotations


def notify(title: str, message: str) -> None:
    """Fire a native desktop notification. Never raises."""
    try:
        from plyer import notification  # type: ignore
        notification.notify(title=title, message=message, app_name="StockX", timeout=8)
    except Exception:
        pass
