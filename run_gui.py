"""
StockX GUI — Desktop launcher.
Run with:  python run_gui.py
"""
import sys
import os

# Ensure the project root is on sys.path so all existing modules resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths

# In a windowed PyInstaller build, sys.stdout/stderr are None — faulthandler and
# the app's print() calls would raise and crash at startup. Redirect them to a
# log file next to the exe so they are always valid streams.
if sys.stdout is None or sys.stderr is None:
    _log_stream = open(paths.data_dir() / "stockx.log", "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _log_stream
    if sys.stderr is None:
        sys.stderr = _log_stream

# Load .env before any module reads os.environ (next to the exe when frozen)
from dotenv import load_dotenv
load_dotenv(paths.dotenv_path())

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
from gui.app import MainWindow, _make_window_icon

if __name__ == "__main__":
    # Must be set before QApplication so Windows gives us our own taskbar group
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StockX.App")

    app = QApplication(sys.argv)
    _dark_mode = os.environ.get("APP_THEME", "dark") != "light"
    app.setStyleSheet(get_stylesheet(dark=_dark_mode))
    app.setWindowIcon(_make_window_icon())
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

        # Force the taskbar to use our custom icon by setting the Win32 HICON directly.
        # processEvents() ensures the window's taskbar button is created before we set the icon.
        if sys.platform == "win32":
            import ctypes
            QApplication.processEvents()   # let Qt create the native window + taskbar button
            ico_path = paths.icon_path()
            if ico_path.exists():
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x00000010
                hicon_large = ctypes.windll.user32.LoadImageW(
                    None, str(ico_path), IMAGE_ICON, 256, 256, LR_LOADFROMFILE
                )
                hicon_small = ctypes.windll.user32.LoadImageW(
                    None, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
                )
                WM_SETICON = 0x0080
                hwnd = int(window.winId())
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_large)  # ICON_BIG
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)  # ICON_SMALL

        loop.run_forever()
