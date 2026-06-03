"""Test configuration for desktop app imports."""

import sys
import types
from pathlib import Path

_package_root = Path(__file__).resolve().parent.parent

# Make project root importable so top-level packages (services/, db/, data/,
# core/, bdt/, ui/) are discoverable. The v1 codebase historically imports
# these as top-level (e.g. `from db.engine import create_engine`) when not
# installed as the `alarm_app` distribution. v2 adds `services/` at the
# project root, which also needs to be importable.
if str(_package_root) not in sys.path:
    sys.path.insert(0, str(_package_root))

if "alarm_app" not in sys.modules:
    pkg = types.ModuleType("alarm_app")
    pkg.__path__ = [str(_package_root)]
    sys.modules["alarm_app"] = pkg
