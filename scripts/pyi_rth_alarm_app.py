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

    # PyInstaller's FrozenImporter.toc maps every collected module name
    # (including submodules like core.classify) to archive locations.
    # Walk it and alias each one under alarm_app.xxx so that
    # ``from alarm_app.core.classify import X`` resolves correctly.
    try:
        import pyimod02_importers
        importer = getattr(pyimod02_importers, "FrozenImporter", None)
        toc = getattr(importer, "toc", None) if importer is not None else None
    except ImportError:
        toc = None

    if toc is not None and isinstance(toc, dict):
        module_names = list(toc.keys())
    else:
        # Fallback: eagerly import a known set of top-level modules
        module_names = [
            "logging_config", "versioning", "constants", "styles",
            "core", "data", "db", "bdt", "ui", "web", "llm_tools",
            "runtime",
        ]

    for mod_name in module_names:
        try:
            __import__(mod_name)
        except ImportError:
            pass

    # Alias every loaded module under alarm_app, including submodules.
    # e.g. core.classify → alarm_app.core.classify
    for name in sorted(sys.modules.keys()):
        if name.startswith(("_", "alarm_app")):
            continue
        if name in sys.builtin_module_names:
            continue
        alias = f"alarm_app.{name}"
        if alias not in sys.modules:
            sys.modules[alias] = sys.modules[name]


_register_alarm_app_namespace()


_register_alarm_app_namespace()
