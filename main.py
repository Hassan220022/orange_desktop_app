#!/usr/bin/env python3
"""
Alarm Viewer — Telecom Alarm Data Explorer
Thin entry point.  All logic lives in the alarm_app package.
"""

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

try:
    from .constants import APP_NAME, APP_VERSION
    from .ui.viewer import AlarmViewer
except ImportError:  # PyInstaller flat-module runtime fallback
    from constants import APP_NAME, APP_VERSION
    from alarm_app.ui.viewer import AlarmViewer


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

    icon_candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        icon_candidates.append(Path(bundle_root) / "assets" / "app_icon.png")
    icon_candidates.append(Path(__file__).resolve().parent / "assets" / "app_icon.png")

    app_icon = None
    for icon_path in icon_candidates:
        if icon_path.exists():
            app_icon = QIcon(str(icon_path))
            if not app_icon.isNull():
                app.setWindowIcon(app_icon)
                break

    win = AlarmViewer()
    if app_icon is not None and not app_icon.isNull():
        win.setWindowIcon(app_icon)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
