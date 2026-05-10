"""Installed-app runtime bootstrap.

Creates the local storage layout expected by the desktop app so the packaged
application can run DB-first from first launch without depending on dev paths.
"""

from __future__ import annotations

from pathlib import Path


def bootstrap_local_runtime() -> dict[str, str]:
    try:
        from alarm_app.data import alarm_store
    except ImportError:
        from data import alarm_store
    try:
        from alarm_app.data import state as state_mod
    except ImportError:
        from data import state as state_mod
    try:
        from alarm_app.db import engine as db_engine
    except ImportError:
        from db import engine as db_engine
    try:
        from alarm_app.db.repos import blob_repo
    except ImportError:
        from db.repos import blob_repo
    try:
        from alarm_app.logging_config import LOG_DIR
    except ImportError:
        from logging_config import LOG_DIR

    state_dir = Path(state_mod.STATE_DIR)
    state_dir.mkdir(parents=True, exist_ok=True)
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(blob_repo.BLOB_DIR).mkdir(parents=True, exist_ok=True)

    engine = db_engine.create_engine()
    db_engine.init_db(engine, include_alarm_records=False)

    # Ensure the local DuckDB cache file exists even before the first import.
    # Skip the write-lock probe if another backend already owns the file —
    # that's a normal "second instance / sibling backend" situation, not an
    # error.  ``_safe_connect`` returns ``None`` in that case.
    if not alarm_store.ALARM_DB_FILE.exists():
        con = alarm_store._connect(read_only=False)
        con.close()
    else:
        con = alarm_store._safe_connect(read_only=False)
        if con is not None:
            con.close()

    device_id = state_mod.get_or_create_device_id()
    return {
        "state_dir": str(state_dir),
        "sqlite_db": str(db_engine.DB_PATH),
        "duckdb": str(state_mod.ALARM_DB_FILE),
        "blob_dir": str(blob_repo.BLOB_DIR),
        "logs_dir": str(LOG_DIR),
        "device_id": device_id,
    }
