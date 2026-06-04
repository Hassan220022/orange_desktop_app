"""Services layer for Alarm Viewer v2.

Holds persistence and business-orchestration services. Pure Python, no Qt, no
SQL outside the persistence package itself. The QML/PySide6 adapters import
from here; nothing imports from `adapters/`, `qml/`, or `ui/` from inside
this package.
"""
