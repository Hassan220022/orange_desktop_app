"""
State persistence — save/restore UI state and DataFrame cache across sessions.

Backend: SQLite database via SQLAlchemy (migrated from flat JSON/Parquet files).
Legacy file-path constants remain for functions that still operate on disk
(device_id, file hashing) and for test fixture patching.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

_log = logging.getLogger(__name__)

import pandas as pd

try:
    from alarm_app.db.engine import (
        create_engine as _create_engine,
    )
    from alarm_app.db.engine import (
        get_session_factory as _get_session_factory,
    )
    from alarm_app.db.engine import (
        get_shared_session as _get_shared_session,
    )
    from alarm_app.db.engine import (
        init_app_db as _init_app_db,
    )
    from alarm_app.db.engine import (
        init_db as _init_db,
    )
except ImportError:
    from db.engine import (
        create_engine as _create_engine,
    )
    from db.engine import (
        get_session_factory as _get_session_factory,
    )
    from db.engine import (
        get_shared_session as _get_shared_session,
    )
    from db.engine import (
        init_app_db as _init_app_db,
    )
    from db.engine import (
        init_db as _init_db,
    )

STATE_DIR  = Path.home() / ".alarm_viewer"
STATE_FILE = STATE_DIR / "state.json"
REVIEW_LOG_FILE = STATE_DIR / "review_log.jsonl"
OUTBOX_FILE = STATE_DIR / "sync_outbox.jsonl"
SYNC_CHECKPOINT_FILE = STATE_DIR / "sync_checkpoint.json"
DEVICE_ID_FILE = STATE_DIR / "device_id.txt"
ALARM_IDS_FILE = STATE_DIR / "alarm_ids.json"
FEATURE_FLAG_KEYS = ("sync_on", "cloud_read_on", "bootstrap_on")
DEFAULT_FEATURE_FLAGS = {
    "sync_on": False,
    "cloud_read_on": False,
    "bootstrap_on": False,
}

_engine = None
_SessionFactory = None


def _get_session():
    try:
        _init_app_db()
    except Exception:
        pass
    try:
        return _get_shared_session()
    except Exception:
        pass
    # Fallback for test / bootstrapless environments
    global _engine, _SessionFactory
    if _engine is None:
        _engine = _create_engine()
        _init_db(_engine, include_alarm_records=False)
        _SessionFactory = _get_session_factory(_engine)
    return _SessionFactory()


def _state_repo_module():
    try:
        from alarm_app.db.repos import state_repo as _repo
    except ImportError:
        from db.repos import state_repo as _repo
    return _repo


def _sync_repo_module():
    try:
        from alarm_app.db.repos import sync_repo as _repo
    except ImportError:
        from db.repos import sync_repo as _repo
    return _repo


def _alarm_store_module():
    try:
        from alarm_app.data import alarm_store as _store
    except ImportError:
        from data import alarm_store as _store
    return _store


def _db_models_module():
    try:
        from alarm_app.db import models as _models
    except ImportError:
        from db import models as _models
    return _models


def _load_alarm_dataframe_from_sqlite() -> pd.DataFrame | None:
    """Best-effort legacy fallback: load alarms from SQLite alarm_records."""
    try:
        from sqlalchemy import inspect as sa_inspect

        try:
            from alarm_app.db.repos.alarm_repo import load_alarms_as_df as _load_alarm_df
        except ImportError:
            from db.repos.alarm_repo import load_alarms_as_df as _load_alarm_df
    except Exception:
        return None

    session = _get_session()
    try:
        if not sa_inspect(session.bind).has_table("alarm_records"):
            return None
        df = _load_alarm_df(session)
        if df is None or df.empty:
            return None
        _log.info("DataFrame loaded from SQLite alarm_records: row_count=%d", len(df))
        return df
    except Exception:
        _log.warning("SQLite alarm_records fallback read failed", exc_info=True)
        return None
    finally:
        session.close()


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def load_feature_flags(source: dict | None = None) -> dict[str, bool]:
    """Return normalized desktop feature flags from persisted state."""
    if isinstance(source, dict):
        data = source
    else:
        try:
            data = load_state() or {}
        except Exception:
            _log.warning("Feature flags read failed; using defaults", exc_info=True)
            data = {}
    out: dict[str, bool] = {}
    for key in FEATURE_FLAG_KEYS:
        out[key] = _coerce_bool(data.get(key, DEFAULT_FEATURE_FLAGS[key]))
    return out


def save_state(state_dict: dict):
    _save = _state_repo_module().save_state
    state_dict["saved_at"] = datetime.now().isoformat()
    session = _get_session()
    try:
        _save(session, state_dict)
        _log.info("State saved")
    finally:
        session.close()


def load_state() -> dict | None:
    _load = _state_repo_module().load_state
    session = _get_session()
    try:
        result = _load(session)
        _log.info("State loaded: found=%s", result is not None)
        return result
    finally:
        session.close()


ALARM_DB_FILE = STATE_DIR / "alarms.duckdb"
ALARM_DB_FALLBACK_FILE = STATE_DIR / "alarms.local.duckdb"


def _alarm_db_candidates() -> list[Path]:
    existing: list[Path] = []
    for path in (ALARM_DB_FILE, ALARM_DB_FALLBACK_FILE):
        if path.exists():
            existing.append(path)
    existing.sort(
        key=lambda path: (path.stat().st_mtime, 1 if path == ALARM_DB_FILE else 0),
        reverse=True,
    )
    return existing


def _set_alarm_store_path(path: Path) -> None:
    store = _alarm_store_module()
    if hasattr(store, "set_alarm_db_file"):
        store.set_alarm_db_file(path)


def has_alarm_cache() -> bool:
    candidates = _alarm_db_candidates()
    if candidates:
        _set_alarm_store_path(candidates[0])
        return True
    _set_alarm_store_path(ALARM_DB_FILE)
    return False

def save_dataframe(df: pd.DataFrame) -> str:
    """Persist alarm DataFrame for fast restore.

    Primary and only backend is DuckDB.
    Returns the backend used: "duckdb".
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for path in (ALARM_DB_FILE, ALARM_DB_FALLBACK_FILE):
        try:
            _set_alarm_store_path(path)
            _alarm_store_module().replace_alarm_table(df)
            if path == ALARM_DB_FILE:
                try:
                    ALARM_DB_FALLBACK_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
            _log.info("DataFrame saved to DuckDB: row_count=%d path=%s", len(df), path)
            return "duckdb"
        except Exception as exc:
            last_error = exc
            _log.warning("DuckDB save failed at %s (%s)", path, exc)
    if last_error is not None:
        raise last_error
    return "duckdb"


def load_dataframe() -> pd.DataFrame | None:
    """Load alarm DataFrame from DuckDB (or cloud API if enabled)."""
    try:
        flags = load_feature_flags()
    except Exception:
        _log.warning("Feature flags unavailable; using local DuckDB only", exc_info=True)
        flags = dict(DEFAULT_FEATURE_FLAGS)
    if flags.get("cloud_read_on"):
        try:
            from alarm_app.data.cloud_reader import fetch_alarms_from_api
        except ImportError:
            from data.cloud_reader import fetch_alarms_from_api
        cloud_df = fetch_alarms_from_api()
        if cloud_df is not None and not cloud_df.empty:
            _log.info("DataFrame loaded from cloud: row_count=%d", len(cloud_df))
            return cloud_df
        _log.warning("Cloud read failed or empty, falling back to local DuckDB")

    candidates = _alarm_db_candidates()
    if candidates:
        for path in candidates:
            try:
                _set_alarm_store_path(path)
                df = _alarm_store_module().load_all_alarms()
                if not df.empty:
                    _log.info("DataFrame loaded from DuckDB: row_count=%d path=%s", len(df), path)
                    return df
                _log.info("DuckDB alarm cache table is empty at %s", path)
            except Exception:
                _log.warning("DuckDB alarm cache read failed at %s", path, exc_info=True)
    else:
        _log.info("No DuckDB alarm cache found")

    sqlite_df = _load_alarm_dataframe_from_sqlite()
    if sqlite_df is not None and not sqlite_df.empty:
        try:
            backend = save_dataframe(sqlite_df)
            _log.info("Rehydrated local DuckDB cache from SQLite fallback using %s backend", backend)
        except Exception:
            _log.warning("Failed to rehydrate local cache after SQLite fallback", exc_info=True)
        return sqlite_df

    return None


def clear_cache():
    """Remove cached data files and clear DB UI state."""
    for f in (STATE_FILE, ALARM_DB_FILE, ALARM_DB_FALLBACK_FILE):
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass
    # Also clear UI state in DB
    try:
        UIState = _db_models_module().UIState
        session = _get_session()
        try:
            session.query(UIState).delete()
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception:
        pass


# ── Review log / daily report ──────────────────────────────
def append_review_event(
    *,
    username: str,
    filename: str,
    site_code: str,
    test_date: str,
    verdict: str,
    reviewed_at: str | None = None,
) -> None:
    ReviewEvent = _db_models_module().ReviewEvent
    from datetime import date as _date

    # Convert string date to Python date object for SQLite Date column
    parsed_test_date = None
    if test_date:
        try:
            parsed_test_date = _date.fromisoformat(str(test_date).strip()[:10])
        except (ValueError, TypeError):
            pass

    # Convert reviewed_at string to datetime object for SQLite DateTime column
    raw_reviewed_at = reviewed_at or datetime.now().isoformat()
    parsed_reviewed_at = None
    try:
        parsed_reviewed_at = datetime.fromisoformat(str(raw_reviewed_at))
    except (ValueError, TypeError):
        parsed_reviewed_at = datetime.now()

    session = _get_session()
    try:
        session.add(ReviewEvent(
            event_type="review",
            site_code=str(site_code or ""),
            test_date=parsed_test_date,
            reviewer=str(username or "").strip(),
            filename=str(filename or ""),
            verdict=str(verdict or ""),
            reviewed_at=parsed_reviewed_at,
        ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_review_events() -> list[dict]:
    ReviewEvent = _db_models_module().ReviewEvent
    session = _get_session()
    try:
        rows = session.query(ReviewEvent).order_by(ReviewEvent.id).all()
        return [
            {
                "username": r.reviewer or "",
                "filename": r.filename or "",
                "site_code": r.site_code or "",
                "test_date": str(r.test_date) if r.test_date else "",
                "verdict": r.verdict or "",
                "reviewed_at": str(r.reviewed_at) if r.reviewed_at else "",
            }
            for r in rows
        ]
    finally:
        session.close()


def summarize_review_events_by_day(events: list[dict] | None = None) -> list[dict]:
    rows = events if events is not None else load_review_events()
    buckets: dict[str, dict] = {}
    for event in rows:
        raw_ts = str(event.get("reviewed_at", "") or "")
        day = raw_ts[:10] if len(raw_ts) >= 10 else ""
        if not day:
            continue
        bucket = buckets.setdefault(
            day,
            {
                "date": day,
                "tests_reviewed": 0,
                "Accepted": 0,
                "Rejected": 0,
                "Revise": 0,
                "N/A": 0,
                "users": set(),
            },
        )
        bucket["tests_reviewed"] += 1
        verdict = str(event.get("verdict", "") or "")
        if verdict in ("Accepted", "Rejected", "Revise", "N/A"):
            bucket[verdict] += 1
        user = str(event.get("username", "") or "").strip()
        if user:
            bucket["users"].add(user)
    out = []
    for day in sorted(buckets.keys(), reverse=True):
        bucket = buckets[day]
        bucket["users"] = ", ".join(sorted(bucket["users"], key=str.lower))
        out.append(bucket)
    return out


# ── Alarm ID configuration ────────────────────────────────
def load_alarm_ids() -> dict:
    """Return {"power": [...], "down": [...], "door": [...]} from config."""
    get_value = _state_repo_module().get_value
    session = _get_session()
    try:
        data = get_value(session, "alarm_ids")
        if isinstance(data, dict):
            result = {
                "power": [str(x).strip() for x in data.get("power", [])],
                "down":  [str(x).strip() for x in data.get("down", [])],
                "door":  [str(x).strip() for x in data.get("door", [])],
            }
            _log.debug("Alarm IDs loaded: power=%d, down=%d, door=%d",
                       len(result["power"]), len(result["down"]), len(result["door"]))
            return result
    except Exception:
        pass
    finally:
        session.close()
    return {"power": [], "down": [], "door": []}


def save_alarm_ids(ids: dict):
    set_value = _state_repo_module().set_value
    session = _get_session()
    try:
        set_value(session, "alarm_ids", ids)
        _log.debug("Alarm IDs saved: power=%d, down=%d, door=%d",
                   len(ids.get("power", [])), len(ids.get("down", [])), len(ids.get("door", [])))
    finally:
        session.close()


# ── File hash change detection ───────────────────────────
def compute_file_hashes(file_paths: list[str]) -> dict[str, str]:
    """Return {path: sha256_hex} for each file that exists."""
    hashes = {}
    for fp in file_paths:
        try:
            if os.path.isfile(fp):
                h = hashlib.sha256()
                with open(fp, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                hashes[fp] = h.hexdigest()
        except Exception:
            pass
    return hashes


def files_changed(saved_hashes: dict[str, str],
                  file_paths: list[str]) -> bool:
    """Return True if any source file was added, removed, or modified."""
    if not saved_hashes:
        return True
    if set(saved_hashes.keys()) != set(file_paths):
        return True
    current = compute_file_hashes(file_paths)
    return current != saved_hashes


def get_or_create_device_id() -> str:
    """Return stable local device ID used for sync event provenance."""
    try:
        if DEVICE_ID_FILE.exists():
            existing = DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
    except Exception:
        pass

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    device_id = str(uuid4())
    try:
        DEVICE_ID_FILE.write_text(device_id, encoding="utf-8")
    except Exception:
        pass
    return device_id


def append_outbox_event(
    *,
    entity_type: str,
    entity_local_id: str,
    op: str,
    entity_hash: str,
    payload: dict,
    origin_device_id: str | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Append one sync event to durable local outbox journal."""
    _append = _sync_repo_module().append_outbox_event
    resolved_event_id = event_id or str(uuid4())
    resolved_device_id = origin_device_id or get_or_create_device_id()
    session = _get_session()
    try:
        evt = _append(
            session,
            entity_type=str(entity_type or ""),
            entity_local_id=str(entity_local_id or ""),
            op=str(op or "upsert"),
            entity_hash=str(entity_hash or ""),
            payload=payload or {},
            origin_device_id=resolved_device_id,
            event_id=resolved_event_id,
        )
        return {
            "event_id": evt.event_id,
            "origin_device_id": evt.origin_device_id,
            "entity_type": evt.entity_type,
            "entity_local_id": evt.entity_local_id,
            "op": evt.op,
            "entity_hash": evt.entity_hash,
            "payload": json.loads(evt.payload_json) if evt.payload_json else {},
            "created_at": evt.created_at.isoformat() if evt.created_at else (created_at or datetime.now().isoformat()),
        }
    finally:
        session.close()


def append_outbox_events(events: list[dict]) -> int:
    """Append multiple sync events to durable local outbox journal."""
    _append_many = _sync_repo_module().append_outbox_events
    if not events:
        return 0
    session = _get_session()
    try:
        normalized = []
        for event in events:
            normalized.append({
                "event_id": str(event.get("event_id") or uuid4()),
                "origin_device_id": str(event.get("origin_device_id") or get_or_create_device_id()),
                "entity_type": str(event.get("entity_type") or ""),
                "entity_local_id": str(event.get("entity_local_id") or ""),
                "op": str(event.get("op") or "upsert"),
                "entity_hash": str(event.get("entity_hash") or ""),
                "payload": event.get("payload") or {},
            })
        return _append_many(session, normalized)
    finally:
        session.close()


def load_pending_outbox(limit: int | None = None) -> list[dict]:
    """Return pending outbox events that are not yet marked synced."""
    _load = _sync_repo_module().load_pending_outbox
    session = _get_session()
    try:
        return _load(session, limit=limit)
    finally:
        session.close()


def save_sync_checkpoint(cursor: str, last_ack_at: str | None = None) -> None:
    """Persist durable sync checkpoint cursor."""
    _save = _sync_repo_module().save_sync_checkpoint
    session = _get_session()
    try:
        _save(session, cursor=str(cursor or ""))
    finally:
        session.close()


def load_sync_checkpoint() -> dict | None:
    """Load durable sync checkpoint cursor metadata."""
    _load = _sync_repo_module().load_sync_checkpoint
    session = _get_session()
    try:
        return _load(session)
    finally:
        session.close()


def mark_outbox_synced(event_ids: list[str], checkpoint_cursor: str | None = None) -> int:
    """Mark matching outbox events as synced and optionally advance checkpoint."""
    _mark = _sync_repo_module().mark_outbox_synced
    if not event_ids:
        return 0
    session = _get_session()
    try:
        return _mark(session, event_ids, checkpoint_cursor=checkpoint_cursor)
    finally:
        session.close()
