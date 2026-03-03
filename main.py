#!/usr/bin/env python3
"""
Alarm Viewer — Telecom Alarm Data Explorer
Thin entry point.  All logic lives in the alarm_app package.
"""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from .constants import APP_NAME, APP_VERSION
from .viewer import AlarmViewer


def main():
    # Windows / macOS High-DPI support
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")

    win = AlarmViewer()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
