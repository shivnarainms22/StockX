"""
StockX GUI — Desktop launcher.
Run with:  python run_gui.py
"""
import sys
import os

# Ensure the project root is on sys.path so all existing modules resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before any module reads os.environ
from dotenv import load_dotenv
load_dotenv()

import asyncio
import faulthandler
faulthandler.enable()
import qasync
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import qInstallMessageHandler


def _qt_message_handler(mode, context, message):
    print(f"Qt[{mode.name}]: {message}", flush=True)


qInstallMessageHandler(_qt_message_handler)

from gui.theme import get_stylesheet
from gui.app import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    _dark_mode = os.environ.get("APP_THEME", "dark") != "light"
    app.setStyleSheet(get_stylesheet(dark=_dark_mode))
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Python 3.13 + httpcore 1.0.9 bug: when an async generator is GC'd,
    # CPython calls gen_close() which throws GeneratorExit into httpcore's
    # PoolByteStream.__aiter__. That generator catches GeneratorExit and tries
    # to `await self.aclose()` inside the except block — Python forbids awaiting
    # during GeneratorExit, raises RuntimeError, which cascades into a segfault.
    # Fix: install a no-op asyncgen finalizer so GC'd generators are simply
    # discarded. httpx's async-with context managers close connections cleanly
    # before the generator can be GC'd, so this loses nothing.
    sys.set_asyncgen_hooks(finalizer=lambda ag: None)

    app.aboutToQuit.connect(lambda: os._exit(0))
    with loop:
        window = MainWindow()
        window.show()
        loop.run_forever()
