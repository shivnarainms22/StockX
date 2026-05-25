"""StockX — filesystem path resolution (dev vs frozen/PyInstaller).

Frozen: writable data lives next to the executable (portable). Dev: repo root,
matching the pre-packaging layout so behaviour is unchanged during development.
"""
from __future__ import annotations

import sys
from pathlib import Path


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_dir() -> Path:
    return _ensure(base_dir() / "data")


def memory_dir() -> Path:
    return _ensure(base_dir() / "memory")


def exports_dir() -> Path:
    return _ensure(data_dir() / "exports")


def dotenv_path() -> Path:
    return base_dir() / ".env"


def icon_path() -> Path:
    return data_dir() / "icon.ico"
