"""Installed-app runtime bootstrap.

Creates the local storage layout expected by the desktop app so the packaged
application can run DB-first from first launch without depending on dev paths.
"""

from __future__ import annotations

from pathlib import Path


def bootstrap_local_runtime() -> dict[str, str]:
    from alarm_app.data import state as state_mod
    from alarm_app.data import alarm_store
    from alarm_app.db import engine as db_engine
    from alarm_app.db.repos import blob_repo
    from alarm_app.logging_config import LOG_DIR

    state_dir = Path(state_mod.STATE_DIR)
    state_dir.mkdir(parents=True, exist_ok=True)
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    Path(blob_repo.BLOB_DIR).mkdir(parents=True, exist_ok=True)

    engine = db_engine.create_engine()
    db_engine.init_db(engine, include_alarm_records=False)

    # Ensure the local DuckDB cache file exists even before the first import.
    con = alarm_store._connect(read_only=False)
    try:
        con.close()
    finally:
        pass

    device_id = state_mod.get_or_create_device_id()
    return {
        "state_dir": str(state_dir),
        "sqlite_db": str(db_engine.DB_PATH),
        "duckdb": str(state_mod.ALARM_DB_FILE),
        "blob_dir": str(blob_repo.BLOB_DIR),
        "logs_dir": str(LOG_DIR),
        "device_id": device_id,
    }
