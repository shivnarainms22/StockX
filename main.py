from dotenv import load_dotenv
load_dotenv()

import sys

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    import asyncio
    import qasync
    from PyQt6.QtWidgets import QApplication
    from gui.theme import STYLESHEET
    from gui.app import MainWindow

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    with loop:
        window = MainWindow()
        window.show()
        loop.run_forever()


if __name__ == "__main__":
    main()
