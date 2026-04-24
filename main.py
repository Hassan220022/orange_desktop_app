#!/usr/bin/env python3
"""
Alarm Viewer — Telecom Alarm Data Explorer
Thin entry point.  All logic lives in the alarm_app package.
Starts the FastAPI backend in a child process and shuts it down on exit.
"""

import atexit
import argparse
import logging
import multiprocessing
import os
import signal
import sys
import types
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication


def _ensure_alarm_app_alias() -> None:
    """Provide an 'alarm_app' package alias for frozen/flat module layouts."""
    if "alarm_app" in sys.modules:
        return
    package_root = Path(__file__).resolve().parent
    pkg = types.ModuleType("alarm_app")
    pkg.__path__ = [str(package_root)]  # type: ignore[attr-defined]
    sys.modules["alarm_app"] = pkg


_ensure_alarm_app_alias()

try:
    from .constants import APP_NAME, APP_VERSION
    from .runtime.bootstrap import bootstrap_local_runtime
    from .ui.viewer import AlarmViewer
    from .logging_config import setup_logging
except ImportError:
    try:
        from alarm_app.constants import APP_NAME, APP_VERSION
        from alarm_app.runtime.bootstrap import bootstrap_local_runtime
        from alarm_app.ui.viewer import AlarmViewer
        from alarm_app.logging_config import setup_logging
    except ImportError:
        # PyInstaller flat-bundle: package root is on sys.path directly
        from constants import APP_NAME, APP_VERSION  # type: ignore[no-redef]
        from runtime.bootstrap import bootstrap_local_runtime  # type: ignore[no-redef]
        from ui.viewer import AlarmViewer  # type: ignore[no-redef]
        from logging_config import setup_logging  # type: ignore[no-redef]

_log = logging.getLogger(__name__)

_backend_process: multiprocessing.Process | None = None
BACKEND_HOST = os.environ.get("ALARM_BACKEND_HOST", "127.0.0.1")
try:
    BACKEND_PORT = int(os.environ.get("ALARM_BACKEND_PORT", "8787"))
except (ValueError, TypeError):
    BACKEND_PORT = 8787


def _run_backend():
    """Target for the backend child process."""
    bootstrap_local_runtime()
    # Child processes don't inherit logging config — set it up here too
    try:
        from alarm_app.logging_config import setup_logging
    except ImportError:
        from logging_config import setup_logging  # type: ignore[no-redef]
    setup_logging()

    import logging
    log = logging.getLogger(__name__)
    log.info("Backend process starting: host=%s port=%s", BACKEND_HOST, BACKEND_PORT)

    import uvicorn
    try:
        from alarm_app.web.app import create_app
    except ImportError:
        from web.app import create_app  # type: ignore[no-redef]

    app = create_app()
    log.info("Backend FastAPI app created, starting uvicorn")

    # log_config=None prevents uvicorn from overriding our logging setup;
    # uvicorn's own loggers then propagate to handlers attached via
    # setup_logging() (uvicorn, uvicorn.error, uvicorn.access → backend.log).
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT,
                log_config=None, log_level="info", access_log=True)


def _start_backend():
    """Start the FastAPI backend in a child process."""
    global _backend_process
    proc = multiprocessing.Process(target=_run_backend, daemon=True)
    proc.start()
    _backend_process = proc


def _stop_backend():
    """Shut down the backend child process."""
    global _backend_process
    if _backend_process is None or not _backend_process.is_alive():
        return
    _backend_process.terminate()
    _backend_process.join(timeout=3)
    if _backend_process.is_alive():
        _backend_process.kill()
        _backend_process.join(timeout=2)
    _backend_process = None


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(prog="AlarmViewer")
    parser.add_argument("--version", action="store_true", help="print app version and exit")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="bootstrap local runtime storage and exit",
    )
    parser.add_argument(
        "--mcp-server",
        action="store_true",
        help="run the local read-only MCP server over stdio and exit",
    )
    parser.add_argument(
        "--ask",
        nargs="+",
        help="ask the OpenRouter-backed local data agent and exit",
    )
    parser.add_argument(
        "--openrouter-model",
        default=os.environ.get("OPENROUTER_MODEL", ""),
        help="OpenRouter model id for --ask",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    args = _parse_args(argv)

    if args.version:
        print(APP_VERSION)
        return

    if args.mcp_server:
        try:
            from alarm_app.llm_tools.mcp_server import main as _mcp_main
        except ImportError:
            from llm_tools.mcp_server import main as _mcp_main  # type: ignore[no-redef]
        _mcp_main()
        return

    if args.ask:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            print("OPENROUTER_API_KEY is required", file=sys.stderr)
            return 2
        try:
            from alarm_app.llm_tools.openrouter_agent import OpenRouterAgent, DEFAULT_MODEL
        except ImportError:
            from llm_tools.openrouter_agent import OpenRouterAgent, DEFAULT_MODEL  # type: ignore[no-redef]
        model = args.openrouter_model or DEFAULT_MODEL
        prompt = " ".join(args.ask).strip()
        print(OpenRouterAgent(api_key=api_key, model=model).ask(prompt))
        return

    runtime_info = bootstrap_local_runtime()
    setup_logging()
    _log.info("Alarm Viewer %s starting", APP_VERSION)
    _log.info("Runtime bootstrap ready: %s", runtime_info)

    if args.smoke_test:
        print("bootstrap-ok")
        return

    # Windows / macOS High-DPI support
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")

    # Start backend server
    _log.info("Starting backend at %s:%s", BACKEND_HOST, BACKEND_PORT)
    _start_backend()
    atexit.register(_stop_backend)
    app.aboutToQuit.connect(_stop_backend)

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

    exit_code = app.exec_()
    _stop_backend()
    sys.exit(exit_code)


if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller on Windows
    raise SystemExit(main())
