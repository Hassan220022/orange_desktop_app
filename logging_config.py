"""Centralized logging configuration.

Log files are written to ~/.alarm_viewer/logs/:
  - app.log       — desktop app (UI, threads, state)
  - backend.log   — FastAPI server
  - db.log        — database operations (engine, repos, hashing)

Each log rotates at 5 MB, keeps 3 backups.
Console output is WARNING+ only to avoid flooding the terminal.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path.home() / ".alarm_viewer" / "logs"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3


def _file_handler(filename: str, level: int = logging.DEBUG) -> RotatingFileHandler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / filename,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    return handler


def _console_handler(level: int = logging.WARNING) -> logging.StreamHandler:
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    return handler


def setup_logging(*, console_level: int = logging.WARNING,
                  file_level: int = logging.DEBUG) -> None:
    """Configure logging for the entire application. Call once at startup."""

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on repeated calls
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    console = _console_handler(console_level)
    root.addHandler(console)

    # App log — everything from alarm_app.*
    app_handler = _file_handler("app.log", file_level)
    for name in ("alarm_app", "alarm_app.ui", "alarm_app.data", "alarm_app.core"):
        logger = logging.getLogger(name)
        logger.addHandler(app_handler)
        logger.setLevel(file_level)

    # DB log — engine, repos, hashing
    # propagate=False prevents duplicate lines in app.log
    db_handler = _file_handler("db.log", file_level)
    db_logger = logging.getLogger("alarm_app.db")
    db_logger.addHandler(db_handler)
    db_logger.setLevel(file_level)
    db_logger.propagate = False
    for name in ("alarm_app.db.engine", "alarm_app.db.repos",
                  "alarm_app.db.hashing"):
        logging.getLogger(name).setLevel(file_level)
    # SQLAlchemy engine logging is noisy at DEBUG — keep at WARNING
    sa_logger = logging.getLogger("sqlalchemy.engine")
    sa_logger.addHandler(db_handler)
    sa_logger.setLevel(logging.WARNING)
    sa_logger.propagate = False

    # Backend log — FastAPI/uvicorn
    backend_handler = _file_handler("backend.log", file_level)
    web_logger = logging.getLogger("alarm_app.web")
    web_logger.addHandler(backend_handler)
    web_logger.setLevel(file_level)
    web_logger.propagate = False
    # Uvicorn sub-loggers: attach handler only to the parent, and set
    # propagate=False on children so they don't double-emit.
    uv_parent = logging.getLogger("uvicorn")
    uv_parent.addHandler(backend_handler)
    uv_parent.setLevel(file_level)
    uv_parent.propagate = False
    for name in ("uvicorn.error", "uvicorn.access"):
        child = logging.getLogger(name)
        child.setLevel(file_level)
        # Children propagate to uvicorn parent which has the handler
        child.propagate = True
