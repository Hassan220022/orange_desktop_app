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
        # Fallback: import all known alarm_app modules
        module_names = [
            "logging_config", "versioning", "constants", "styles", "main",
            "core", "core.backup_time", "core.classify", "core.duration", "core.filters",
            "data", "data.alarm_store", "data.bootstrap", "data.cloud_reader",
            "data.loaders", "data.site_report", "data.state", "data.sync",
            "data.sync_client", "data.sync_monitor",
            "db", "db.engine", "db.hashing", "db.models", "db.seed",
            "db.repos", "db.repos.alarm_repo", "db.repos.bdt_repo",
            "db.repos.blob_repo", "db.repos.file_repo", "db.repos.photo_service",
            "db.repos.pm_repo", "db.repos.state_repo", "db.repos.sync_repo",
            "bdt", "bdt.export", "bdt.history", "bdt.image_assigner",
            "bdt.models", "bdt.normalization", "bdt.ooxml_reader",
            "bdt.parser", "bdt.photo_auth", "bdt.rule_docs",
            "bdt.section_parser", "bdt.validator",
            "ui", "ui.bridge", "ui.dialogs", "ui.filter_state",
            "ui.flow_layout", "ui.model", "ui.state_manager", "ui.threads",
            "ui.viewer",
            "ui.panels", "ui.panels.bdt_detail_panel", "ui.panels.bdt_validation_panel",
            "ui.panels.bdt_workspace_panel", "ui.panels.chat_panel",
            "ui.panels.left_panel", "ui.panels.search_panel",
            "web", "web.app", "web.config", "web.deps", "web.schemas",
            "web.routers", "web.routers.alarms", "web.routers.pm", "web.routers.sync",
            "llm_tools", "llm_tools.mcp_server", "llm_tools.openrouter_agent",
            "llm_tools.openrouter_models", "llm_tools.service", "llm_tools.tools",
            "runtime", "runtime.bootstrap", "runtime.env",
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
