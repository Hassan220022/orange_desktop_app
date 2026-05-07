"""Test configuration for desktop app imports."""

import sys
import types
from pathlib import Path

_package_root = Path(__file__).resolve().parent.parent
if "alarm_app" not in sys.modules:
    pkg = types.ModuleType("alarm_app")
    pkg.__path__ = [str(_package_root)]
    sys.modules["alarm_app"] = pkg
