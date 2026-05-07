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

    # Create the alarm_app namespace package.
    pkg = types.ModuleType("alarm_app")
    pkg.__path__ = []
    sys.modules["alarm_app"] = pkg

    # PyInstaller exposes its Table of Contents via the pyimod02_importers
    # module which records all frozen module names.  This is the canonical
    # source of truth for what was collected into the bundle.
    try:
        import pyimod02_importers
        toc = getattr(pyimod02_importers, "FrozenImporter", None)
        if toc is not None:
            toc = getattr(toc, "toc", None) or getattr(toc, "_toc", None)
    except ImportError:
        toc = None

    if toc is not None and isinstance(toc, dict):
        # toc maps module names to archive positions — alias them all
        names = list(toc.keys())
    else:
        # Fallback: eagerly import a known set of top-level modules
        names = [
            "logging_config", "versioning", "constants", "styles",
            "core", "data", "db", "bdt", "ui", "web", "llm_tools",
            "runtime",
        ]

    for mod_name in names:
        # Only alias top-level entries; dotted submodules are handled
        # by Python's regular import mechanism via the aliased parents.
        if "." in mod_name:
            continue
        try:
            __import__(mod_name)
        except ImportError:
            continue
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        alias = f"alarm_app.{mod_name}"
        if alias not in sys.modules:
            sys.modules[alias] = mod


_register_alarm_app_namespace()


_register_alarm_app_namespace()
