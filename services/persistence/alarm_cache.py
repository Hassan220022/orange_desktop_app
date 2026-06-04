"""DuckDB-backed alarm DataFrame cache.

The desktop app's primary runtime storage for the alarm DataFrame. Lives here
in the persistence layer so services can save/load without depending on
``data/``. v1's equivalent lives in ``data/state.py`` (mixed with other
state concerns); v2 keeps the alarm-cache logic focused.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .exceptions import AlarmCacheError

_log = logging.getLogger(__name__)

STATE_DIR: Path = Path.home() / ".alarm_viewer"
_ALARM_DB_FILENAME = "alarms.duckdb"
_ALARM_DB_FALLBACK_FILENAME = "alarms.local.duckdb"


def _alarm_db_file() -> Path:
    return STATE_DIR / _ALARM_DB_FILENAME


def _alarm_db_fallback_file() -> Path:
    return STATE_DIR / _ALARM_DB_FALLBACK_FILENAME


def _alarm_store_module() -> Any:
    """Import the alarm_store module without a hard dependency on data/.

    v1 stores the DuckDB backend at ``data/alarm_store.py``. v2 does not
    own that file yet (it lives in v1 until cutover), so we look it up
    first as a top-level package and then as ``alarm_app.data`` subpackage.
    """
    try:
        from data import alarm_store as _store  # type: ignore
    except ImportError:
        from alarm_app.data import alarm_store as _store  # type: ignore
    return _store


def _alarm_db_candidates() -> list[Path]:
    primary = _alarm_db_file()
    fallback = _alarm_db_fallback_file()
    existing: list[Path] = []
    for path in (primary, fallback):
        if path.exists():
            existing.append(path)
    existing.sort(
        key=lambda path: (path.stat().st_mtime, 1 if path == primary else 0),
        reverse=True,
    )
    return existing


def _set_alarm_store_path(path: Path) -> None:
    store = _alarm_store_module()
    if hasattr(store, "set_alarm_db_file"):
        store.set_alarm_db_file(path)


def has_alarm_cache() -> bool:
    """Return True if a DuckDB alarm cache file exists on disk."""
    candidates = _alarm_db_candidates()
    if candidates:
        _set_alarm_store_path(candidates[0])
        return True
    _set_alarm_store_path(_alarm_db_file())
    return False


def save_dataframe(df: pd.DataFrame) -> str:
    """Persist alarm DataFrame for fast restore. Returns 'duckdb'.

    Raises AlarmCacheError if both primary and fallback paths fail.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    primary = _alarm_db_file()
    fallback = _alarm_db_fallback_file()
    last_error: Exception | None = None
    for path in (primary, fallback):
        try:
            _set_alarm_store_path(path)
            _alarm_store_module().replace_alarm_table(df)
            if path == primary:
                try:
                    fallback.unlink(missing_ok=True)
                except OSError:
                    pass
            _log.info("DataFrame saved to DuckDB: row_count=%d path=%s", len(df), path)
            return "duckdb"
        except Exception as exc:
            last_error = exc
            _log.warning("DuckDB save failed at %s (%s)", path, exc)
    if last_error is not None:
        raise AlarmCacheError(
            f"Failed to save alarm DataFrame: {last_error}"
        ) from last_error
    return "duckdb"


def load_dataframe() -> pd.DataFrame | None:
    """Load alarm DataFrame from DuckDB. Returns None if no cache exists."""
    candidates = _alarm_db_candidates()
    if candidates:
        for path in candidates:
            try:
                _set_alarm_store_path(path)
                df = _alarm_store_module().load_all_alarms()
                if not df.empty:
                    _log.info(
                        "DataFrame loaded from DuckDB: row_count=%d path=%s",
                        len(df), path,
                    )
                    return df
            except Exception:
                _log.warning("DuckDB alarm cache read failed at %s", path, exc_info=True)
    return None


def clear_cache() -> None:
    """Remove both alarm-cache DuckDB files from disk."""
    for f in (_alarm_db_file(), _alarm_db_fallback_file()):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
