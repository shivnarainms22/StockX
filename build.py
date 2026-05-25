"""Build the portable Windows one-folder distribution.

Steps: generate the branded exe icon, then run PyInstaller on stockx.spec.
Output: dist/StockX/StockX.exe  (data/, memory/, .env live next to the exe).

Usage:  python build.py
Requires the build extra:  pip install -e ".[build]"
"""
from __future__ import annotations

import subprocess
import sys


def main() -> None:
    subprocess.run([sys.executable, "tools/make_icon.py"], check=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "stockx.spec", "--noconfirm"],
        check=True,
    )
    print("\nBuild complete: dist/StockX/StockX.exe")
    print("Place a .env (with API keys) next to the exe; data/ and memory/ are "
          "created there on first run.")


if __name__ == "__main__":
    main()
