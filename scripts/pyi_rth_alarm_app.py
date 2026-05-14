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

    # Eagerly import all modules in dependency order so they appear in
    # sys.modules and can be aliased under alarm_app.
    # Import order: leaf modules first (no alarm_app deps), then modules
    # that depend on other alarm_app modules.
    _IMPORT_ORDER = [
        # Tier 0: no internal deps
        "versioning", "logging_config", "styles",
        # Tier 1: depends on versioning only
        "constants",
        # Tier 2: depends on constants
        "core.filters", "core.classify", "core.duration", "core.backup_time",
        # Tier 3: depends on core
        "data.sync_monitor", "data.cloud_reader", "data.site_report",
        "data.sync_client", "data.sync", "data.loaders", "data.state",
        "data.alarm_store", "data.bootstrap",
        # Tier 4: db, depends on nothing internal
        "db.hashing", "db.models", "db.engine", "db.seed",
        "db.repos.alarm_repo", "db.repos.bdt_repo", "db.repos.blob_repo",
        "db.repos.file_repo", "db.repos.photo_service", "db.repos.pm_repo",
        "db.repos.state_repo", "db.repos.sync_repo",
        # Tier 5: bdt, depends on data/constants
        "bdt.normalization", "bdt.ooxml_reader", "bdt.models",
        "bdt.section_parser", "bdt.image_assigner", "bdt.parser",
        "bdt.validator", "bdt.rule_docs", "bdt.export", "bdt.history",
        "bdt.photo_auth",
        # Tier 6: runtime helpers used by ui.dialogs
        "runtime.env", "runtime.bootstrap", "runtime.tunnels", "runtime.chatgpt_connector",
        # Tier 7: ui, depends on everything above
        "ui.flow_layout", "ui.model", "ui.bridge", "ui.filter_state",
        "ui.state_manager", "ui.threads", "ui.dialogs",
        "ui.panels.left_panel", "ui.panels.search_panel",
        "ui.panels.bdt_workspace_panel", "ui.panels.bdt_validation_panel",
        "ui.panels.bdt_detail_panel", "ui.panels.chat_panel", "ui.viewer",
        # Tier 8: web and llm_tools
        "web.config", "web.deps", "web.schemas",
        "web.routers.alarms", "web.routers.mcp", "web.routers.pm", "web.routers.sync",
        "web.app",
        "llm_tools.openrouter_models", "llm_tools.service",
        "llm_tools.tools", "llm_tools.openrouter_agent",
        "llm_tools.mcp_server",
        "main",
    ]

    for mod_name in _IMPORT_ORDER:
        try:
            __import__(mod_name)
        except Exception:
            pass

    # Alias every loaded module under alarm_app, including submodules.
    for name in sorted(sys.modules.keys()):
        if name.startswith(("_", "pyimod", "PyInstaller")):
            continue
        if name == "alarm_app" or name.startswith("alarm_app."):
            continue
        if name in sys.builtin_module_names:
            continue
        alias = f"alarm_app.{name}"
        if alias not in sys.modules:
            sys.modules[alias] = sys.modules[name]


_register_alarm_app_namespace()


_register_alarm_app_namespace()
