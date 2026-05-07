"""PyInstaller runtime hook: alias flat modules under the alarm_app namespace.

In the PyInstaller frozen bundle, all modules are stored flat (core,
data, ui, etc.) without the alarm_app parent package.  This hook runs
before the main script and registers aliases so that ``from alarm_app.X
import Y`` resolves to the flat ``X.Y`` module that PyInstaller collected.
"""

import sys
import types


def _register_alarm_app_namespace():
    if "alarm_app" in sys.modules:
        return

    # Create the alarm_app namespace package so Python can resolve
    # alarm_app.<anything> via submodule lookup.
    pkg = types.ModuleType("alarm_app")
    pkg.__path__ = []
    sys.modules["alarm_app"] = pkg

    # Walk all loaded modules (stdlib + PyInstaller frozen) and alias
    # every top-level name under alarm_app so that ``alarm_app.core``
    # resolves to the ``core`` package collected by PyInstaller.
    for name, mod in sorted(sys.modules.items()):
        if name.startswith("_") or "." in name or name == "alarm_app":
            continue
        # Skip built-in and stdlib modules to avoid interfering with
        # Python internals.
        if name in sys.builtin_module_names:
            continue
        alias = f"alarm_app.{name}"
        if alias not in sys.modules:
            sys.modules[alias] = mod


_register_alarm_app_namespace()
