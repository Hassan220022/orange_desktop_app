# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys
import types

# Register alarm_app as a namespace package so PyInstaller's collect_submodules()
# can discover all subpackages during the analysis phase.
if "alarm_app" not in sys.modules:
    pkg = types.ModuleType("alarm_app")
    pkg.__path__ = ["."]
    sys.modules["alarm_app"] = pkg

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


# PyInstaller executes spec files without defining __file__.
# The repo scripts/workflows `cd` into the project root before invoking this spec.
ROOT = Path.cwd().resolve()
IS_MAC = sys.platform == "darwin"
ICON_PATH = ROOT / "assets" / ("app_icon.icns" if IS_MAC else "app_icon.ico")

datas = [
    (str(ROOT / "assets" / "app_icon.png"), "assets"),
    (str(ROOT / "VERSION"), "."),
]
datas += collect_data_files(
    "alarm_app.bdt.vendor_synthid",
    includes=["*.pkl"],
)

hiddenimports = [
    "pandas",
    "openpyxl",
    "xlrd",
    "pyarrow",
    "python_calamine",
    "duckdb",
    "sqlalchemy",
    "uvicorn",
    "fastapi",
    "requests",
    "imagehash",
    "cv2",
    "pywt",
    "sklearn",
    "scipy",
    "c2pa",
    # Root-level alarm_app packages (needed for Python to treat dirs as packages)
    "core", "data", "db", "db.repos",
    "bdt", "ui", "ui.panels",
    "web", "web.routers",
    "llm_tools", "runtime",
    # Root-level alarm_app modules (flat in PyInstaller bundle)
    "versioning",
    "constants",
    "styles",
    "logging_config",
    "main",
    # All subpackages and their modules (explicit — more reliable than collect_submodules)
    "core.backup_time", "core.classify", "core.duration", "core.filters",
    "data.alarm_store", "data.bootstrap", "data.cloud_reader", "data.loaders",
    "data.site_report", "data.state", "data.sync", "data.sync_client",
    "data.sync_monitor",
    "db.engine", "db.hashing", "db.models", "db.seed",
    "db.repos.alarm_repo", "db.repos.bdt_repo", "db.repos.blob_repo",
    "db.repos.file_repo", "db.repos.photo_service", "db.repos.pm_repo",
    "db.repos.state_repo", "db.repos.sync_repo",
    "bdt.export", "bdt.history", "bdt.image_assigner", "bdt.models",
    "bdt.normalization", "bdt.ooxml_reader", "bdt.parser", "bdt.photo_auth",
    "bdt.rule_docs", "bdt.section_parser", "bdt.validator",
    "ui.bridge", "ui.dialogs", "ui.filter_state", "ui.flow_layout",
    "ui.model", "ui.state_manager", "ui.threads", "ui.viewer",
    "ui.panels.bdt_detail_panel", "ui.panels.bdt_validation_panel",
    "ui.panels.bdt_workspace_panel", "ui.panels.chat_panel",
    "ui.panels.left_panel", "ui.panels.search_panel",
    "web.app", "web.config", "web.deps", "web.schemas",
    "web.routers.alarms", "web.routers.pm", "web.routers.sync",
    "llm_tools.mcp_server", "llm_tools.openrouter_agent",
    "llm_tools.openrouter_models", "llm_tools.service", "llm_tools.tools",
    "runtime.bootstrap", "runtime.env",
]


a = Analysis(
    ["scripts/pyinstaller_entry.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["scripts/pyi_rth_alarm_app.py"],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AlarmViewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ICON_PATH),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AlarmViewer",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="AlarmViewer.app",
        icon=str(ICON_PATH),
        bundle_identifier="com.orange.alarmviewer",
    )
