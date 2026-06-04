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


def _get_app_engine_for_test():
    """Test hook: lazy import so tests don't pay the cost in production.

    Re-exposes the shared app engine without making it part of the public
    API. Used by tests that need to ``init_db()`` the schema in a temp HOME.
    """
    from .engine import get_app_engine
    return get_app_engine()


def _get_shared_session_for_test():
    """Test hook: re-expose ``engine.get_shared_session`` for tests that
    pre-seed and post-assert against the SQLite tables in a temp HOME.
    """
    from .engine import get_shared_session
    return get_shared_session()


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


# Tables whose rows are derived from source files and safe to wipe on
# "clear cached data". Anything NOT in this set (uploaded_files, ui_state,
# site_metadata_catalog, sync_*, review_events, pm_rule_catalog,
# pm_rule_parameter_sets) is a dedup helper, user preference, or audit log
# and is preserved so the user does not lose work.
#
# DELETE ORDER MATTERS — child tables must be removed before their parents
# because the engine enables PRAGMA foreign_keys=ON. The order is the same
# as a topological sort of the FK dependency graph:
#
#   pm_rule_results  ← pm_validation_runs  ← bdt_tests
#                                              ↑
#                                          bdt_photos, bdt_summary_catalog
#   bdt_photos  ←── bdt_tests
#   alarm_records.file_id  ──>  uploaded_files   (parent preserved, OK to delete)
#   blob_assets   (no FK children in this set)
_CLEAR_ORDER: tuple[str, ...] = (
    "pm_rule_results",       # child of pm_validation_runs
    "bdt_photos",            # child of bdt_tests
    "pm_validation_runs",    # child of bdt_tests
    "blob_assets",           # no FK children
    "bdt_tests",             # parent of bdt_photos, pm_validation_runs
    "alarm_records",         # FK to uploaded_files (preserved) — safe to delete
    "bdt_summary_catalog",   # standalone (no FKs to other clearable tables)
)


def _clear_bdt_history_dir() -> int:
    """Delete the per-site BDT history JSON files used for previous-test
    comparison. Returns the count of files removed.
    """
    try:
        from bdt.history import HISTORY_DIR  # type: ignore
    except ImportError:
        try:
            from alarm_app.bdt.history import HISTORY_DIR  # type: ignore
        except ImportError:
            return 0
    if not HISTORY_DIR.exists():
        return 0
    removed = 0
    for path in HISTORY_DIR.rglob("*"):
        if path.is_file():
            try:
                path.unlink()
                removed += 1
            except OSError:
                _log.warning("Could not delete BDT history file: %s", path, exc_info=True)
    return removed


def clear_all_caches() -> dict[str, int]:
    """Wipe every cache that is derived from source files.

    Removes:
      * ``alarms.duckdb`` and ``alarms.local.duckdb`` (DuckDB alarm cache)
      * Rows in the ``alarm_records`` table (the legacy SQLite alarm copy)
      * BDT parsed tests, photos, blob assets, validation runs, rule results,
        and BDT summary catalog rows
      * Per-site BDT history JSON files under ``~/.alarm_viewer/bdt_history/``

    Returns a summary dict mapping table name (or 'alarm_duckdb_files',
    'bdt_history_files') to the number of rows / files removed. Tables or
    files that did not exist (count = 0) are still listed for visibility.

    Deliberately PRESERVED (dedup helpers, user prefs, audit trail):
      * ``uploaded_files`` — SHA-256 dedup index; clearing it would force
        re-hashing on the next load
      * ``ui_state`` — UI preferences (theme, last directory, page size, ...)
      * ``site_metadata_catalog`` — site catalog
      * ``pm_rule_catalog``, ``pm_rule_parameter_sets`` — rule definitions
      * ``sync_outbox``, ``sync_checkpoints`` — sync queue state
      * ``review_events`` — daily-review audit log
      * Photo files under ``~/.alarm_viewer/blobs/`` — re-linked by SHA-256
        dedup on next BDT workbook load; deleting them is wasted I/O
    """
    summary: dict[str, int] = {}

    # 1) DuckDB alarm cache files
    duckdb_removed = 0
    for f in (_alarm_db_file(), _alarm_db_fallback_file()):
        try:
            if f.exists():
                f.unlink()
                duckdb_removed += 1
        except OSError:
            _log.warning("Could not delete alarm cache file: %s", f, exc_info=True)
    summary["alarm_duckdb_files"] = duckdb_removed

    # 2) BDT per-site history JSON files
    summary["bdt_history_files"] = _clear_bdt_history_dir()

    # 3) SQLite derived tables — use the shared app engine so we go through
    #    SQLAlchemy (and the WAL pragma is in effect). Wrap each DELETE in
    #    its own try/except so a single table failure does not abort the
    #    rest of the cleanup.
    try:
        from .engine import get_shared_session
        from .models import (
            AlarmRecord,
            BDTTest,
            BDTPhoto,
            BlobAsset,
            PMValidationRun,
            PMRuleResult,
            BDTSummaryCatalog,
        )
    except Exception as exc:
        _log.error("Could not import persistence models for clear_all_caches: %s", exc)
        return summary

    table_to_model = {
        "alarm_records": AlarmRecord,
        "bdt_tests": BDTTest,
        "bdt_photos": BDTPhoto,
        "blob_assets": BlobAsset,
        "pm_validation_runs": PMValidationRun,
        "pm_rule_results": PMRuleResult,
        "bdt_summary_catalog": BDTSummaryCatalog,
    }
    for table_name in _CLEAR_ORDER:
        if table_name not in table_to_model:
            continue
        model = table_to_model[table_name]
        session = None
        try:
            session = get_shared_session()
            count = session.query(model).delete(synchronize_session=False)
            session.commit()
            summary[table_name] = int(count or 0)
            _log.info("Cleared %d rows from %s", int(count or 0), table_name)
        except Exception as exc:
            _log.error("Failed to clear %s: %s", table_name, exc, exc_info=True)
            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass
            summary[table_name] = -1  # marker: error
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

    return summary
