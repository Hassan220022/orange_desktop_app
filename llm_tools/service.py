"""Guarded local data access for MCP/OpenRouter agents."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, is_dataclass, replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func
from sqlalchemy import inspect as sa_inspect

try:
    from alarm_app.bdt.export import build_bdt_export_sheets
    from alarm_app.core.backup_time import compute_backup_times
    from alarm_app.core.temp_alarm import (
        DEFAULT_HT_HISTORY_START_WEEK,
        _compute_ht_meet_frames,
        _filter_source_from_week,
        build_temp_alarm_summary,
        compute_ht_meet_rows,
    )
    from alarm_app.data import alarm_store, catalog_store, state
    from alarm_app.data.site_report import (
        build_pm_accept_report,
        build_site_alarm_report,
        collect_site_sheet_keys,
        infer_site_id_column,
        normalize_site_key,
        read_pm_accept_sheet,
    )
    from alarm_app.db import engine as db_engine
    from alarm_app.db.models import (
        BDTPhoto,
        BDTTest,
        BlobAsset,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
        ReviewEvent,
        UploadedFile,
    )
    from alarm_app.db.repos import blob_repo
    from alarm_app.db.repos.pm_repo import load_all_validation_results
except ImportError:
    from bdt.export import build_bdt_export_sheets
    from core.backup_time import compute_backup_times
    from core.temp_alarm import (
        DEFAULT_HT_HISTORY_START_WEEK,
        _compute_ht_meet_frames,
        _filter_source_from_week,
        build_temp_alarm_summary,
        compute_ht_meet_rows,
    )
    from data import alarm_store, catalog_store, state
    from data.site_report import (
        build_pm_accept_report,
        build_site_alarm_report,
        collect_site_sheet_keys,
        infer_site_id_column,
        normalize_site_key,
        read_pm_accept_sheet,
    )
    from db import engine as db_engine
    from db.models import (
        BDTPhoto,
        BDTTest,
        BlobAsset,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
        ReviewEvent,
        UploadedFile,
    )
    from db.repos import blob_repo
    from db.repos.pm_repo import load_all_validation_results

MAX_QUERY_LIMIT = 500
MAX_BLOB_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
EXPORT_DIR = Path.home() / ".alarm_viewer" / "exports"
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xls", ".xlsx"}
MCP_DEFAULT_PAGE_LIMIT = 500
MCP_MAX_PAGE_LIMIT = 1000
_FIELD_ALIASES = {
    "site_name": ("site_name", "sitename", "name"),
    "area": ("area", "orange_area", "orangearea"),
    "contractor": ("contractor",),
    "subcontractor": ("subcontractor", "sub_contractor", "subcontractor_name", "contractor"),
    "backup_status": ("backup_status", "backupstatus"),
    "battery_status": ("battery_status", "batterystatus"),
}
_RAW_JSON_FIELDS = {"raw_data_json", "original_headers_json", "evidence_json", "payload_json"}
_PATH_FIELD_NAMES = {"path", "local_path", "original_path", "source_path", "file_path"}
_LOCAL_PATH_REDACTED = "[local path redacted]"
_LOCAL_PATH_ROOTS = r"Users|private|var|tmp|Volumes|home|opt|usr|etc"
_LOCAL_PATH_EXTENSION_CHAIN = r"[A-Za-z0-9]{1,12}(?:\.[A-Za-z0-9]{1,12})*"
_LOCAL_PATH_TOKEN = r"[^\s\"'\n\r\t\f\v,;:)\]}]+"
_LOCAL_PATH_SPACE_WORD = r"[^\s\"'\n\r\t\f\v,;:)\]}\\/]+"
_LOCAL_PATH_PROSE_LEADERS = r"with|for|during|before|after|while|and|or|but|then|when|from|to|in|on|at|ratio|backup"
_LOCAL_PATH_SPACE_LEADER = rf"(?!(?i:{_LOCAL_PATH_PROSE_LEADERS})\b){_LOCAL_PATH_SPACE_WORD}"
_LOCAL_PATH_SPACE_CONTINUATION = (
    rf"(?: {_LOCAL_PATH_SPACE_LEADER}(?: {_LOCAL_PATH_SPACE_WORD})*[\\/]{_LOCAL_PATH_TOKEN})*"
)
_LOCAL_PATH_VALUE_PATTERN = re.compile(
    rf"(?<![\w:])(?:"
    rf"(?:/(?:{_LOCAL_PATH_ROOTS})(?:/[^\"'\n\r\t\f\v]+)*)"
    r"|"
    r"(?:[A-Za-z]:[\\/][^\"'\n\r\t\f\v]+)"
    r"|"
    r"(?:\\\\[^\"'\n\r\t\f\v]+)"
    r")"
)
_LOCAL_PATH_QUOTED_PATTERN = re.compile(
    rf"(?P<quote>[\"'])(?P<path>(?:/(?:{_LOCAL_PATH_ROOTS})(?:/[^\"'\n\r\t\f\v]+)*"
    r"|"
    r"[A-Za-z]:[\\/][^\"'\n\r\t\f\v]+"
    r"|"
    r"\\\\[^\"'\n\r\t\f\v]+))(?P=quote)"
)
_LOCAL_PATH_WITH_EXTENSION_PATTERN = re.compile(
    rf"(?<![\w:])(?:"
    rf"(?:/(?:{_LOCAL_PATH_ROOTS})(?:/[^\"'\n\r\t\f\v]+?)+\.(?:{_LOCAL_PATH_EXTENSION_CHAIN}))"
    r"|"
    rf"(?:[A-Za-z]:[\\/][^\"'\n\r\t\f\v]+?\.(?:{_LOCAL_PATH_EXTENSION_CHAIN}))"
    r"|"
    rf"(?:\\\\[^\"'\n\r\t\f\v]+?\.(?:{_LOCAL_PATH_EXTENSION_CHAIN}))"
    r")"
    r"(?=$|[\s,.;:)\]}\"'])"
)
_LOCAL_PATH_PATTERN = re.compile(
    rf"(?<![\w:])(?:"
    rf"(?:/(?:{_LOCAL_PATH_ROOTS})(?:/{_LOCAL_PATH_TOKEN})+)"
    r"|"
    rf"(?:[A-Za-z]:[\\/]{_LOCAL_PATH_TOKEN})"
    r"|"
    rf"(?:\\\\{_LOCAL_PATH_TOKEN})"
    r")"
    rf"{_LOCAL_PATH_SPACE_CONTINUATION}"
)


def _jsonable(value: Any) -> Any:
    if value is pd.NaT:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if value is not None and not isinstance(value, (list, dict, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def _is_path_like_field(field: Any) -> bool:
    key_text = str(field)
    lowered = key_text.lower()
    if lowered in _PATH_FIELD_NAMES:
        return True
    if lowered.endswith("_path"):
        return True
    if "file_path" in lowered:
        return True
    return " " in key_text and "path" in lowered


def _looks_like_local_path(value: str) -> bool:
    value_text = value.strip()
    if not value_text:
        return False
    if not _LOCAL_PATH_VALUE_PATTERN.fullmatch(value_text):
        return False
    return "/" in value_text or "\\" in value_text


def _sanitize_local_paths_in_text(value: str) -> str:
    text = _LOCAL_PATH_QUOTED_PATTERN.sub(
        lambda match: f"{match.group('quote')}{_LOCAL_PATH_REDACTED}{match.group('quote')}",
        str(value),
    )
    text = _LOCAL_PATH_WITH_EXTENSION_PATTERN.sub(_LOCAL_PATH_REDACTED, text)
    return _LOCAL_PATH_PATTERN.sub(_LOCAL_PATH_REDACTED, text)


def _sanitize_mcp_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(_sanitize_key): _sanitize_mcp_value(v) for _sanitize_key, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_mcp_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_mcp_value(v) for v in value)
    if isinstance(value, set):
        return [_sanitize_mcp_value(v) for v in value]
    if isinstance(value, str):
        if _looks_like_local_path(value):
            return _LOCAL_PATH_REDACTED
        return _sanitize_local_paths_in_text(value)
    return _jsonable(value)


def _max_timestamp(*values: Any) -> Any:
    latest: pd.Timestamp | None = None
    for value in values:
        candidate = pd.to_datetime(value, errors="coerce") if value is not None else pd.NaT
        if pd.isna(candidate):
            continue
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def _sanitize_raw_json(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None

    return json.dumps(_sanitize_mcp_value(parsed))


def _first_non_empty(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    return value


def _metadata_value_for_field(row: dict[str, Any], raw_rows: dict[str, Any], field: str) -> Any:
    aliases = _FIELD_ALIASES.get(field, (field,))
    for alias in aliases:
        if alias in row:
            value = _first_non_empty(row.get(alias))
            if value is not None:
                return value
    for alias in aliases:
        if alias in raw_rows:
            value = _first_non_empty(raw_rows.get(alias))
            if value is not None:
                return value
    return None


def _sanitize_source_errors(errors_by_source: dict[str, list[str]]) -> dict[str, list[str]]:
    def _sanitize(err: Any) -> str:
        if err is None:
            return ""
        if not isinstance(err, str):
            return _sanitize_mcp_value(str(err))
        sanitized = _sanitize_mcp_value(err)
        return str(sanitized)

    return {
        source: [
            _sanitize(err)
            for err in errors
        ]
        for source, errors in errors_by_source.items()
        if errors
    }


def _limit(value: Any, default: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MAX_QUERY_LIMIT))


def _mcp_limit(value: Any, default: int = MCP_DEFAULT_PAGE_LIMIT) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MCP_MAX_PAGE_LIMIT))


def _mcp_offset(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    return max(parsed, 0)


def _sanitize_mcp_record(record: dict[str, Any], *, include_raw_json: bool = False) -> dict[str, Any]:
    expanded: dict[str, Any] = dict(record)
    raw_rows: dict[str, Any] | None = None
    raw_rows_sanitized: dict[str, Any] | None = None

    raw_value = expanded.get("raw_data_json")
    if isinstance(raw_value, str) and raw_value.strip():
        sanitized_raw_json = _sanitize_raw_json(raw_value)
        if sanitized_raw_json is not None and include_raw_json:
            expanded["raw_data_json"] = sanitized_raw_json
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            raw_rows = parsed
            sanitized_raw_rows = _sanitize_mcp_value(parsed)
            raw_rows_sanitized = sanitized_raw_rows if isinstance(sanitized_raw_rows, dict) else None
            for key, value in parsed.items():
                expanded.setdefault(str(key), value)

    for field in ("evidence_json", "payload_json"):
        raw_value = expanded.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            sanitized_raw_json = _sanitize_raw_json(raw_value)
            if sanitized_raw_json is not None and include_raw_json:
                expanded[field] = sanitized_raw_json
            try:
                parsed = json.loads(raw_value)
            except (TypeError, json.JSONDecodeError):
                parsed = None
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    expanded.setdefault(str(key), value)

    headers_json = expanded.get("original_headers_json")
    if isinstance(headers_json, str) and headers_json.strip():
        try:
            headers = json.loads(headers_json)
        except (TypeError, json.JSONDecodeError):
            headers = None
        if isinstance(headers, dict) and raw_rows:
            for original_field, normalized_key in headers.items():
                key_text = str(original_field)
                source_key = str(normalized_key)
                if source_key in raw_rows:
                    expanded[key_text] = raw_rows[source_key]

    if "raw_data_json" in expanded and not include_raw_json:
        expanded.pop("raw_data_json", None)
    if "original_headers_json" in expanded and not include_raw_json:
        expanded.pop("original_headers_json", None)

    if "evidence_json" in expanded and not include_raw_json:
        expanded.pop("evidence_json", None)
    if "payload_json" in expanded and not include_raw_json:
        expanded.pop("payload_json", None)

    sanitized: dict[str, Any] = {}
    for key, value in expanded.items():
        key_text = str(key)
        if _is_path_like_field(key_text):
            continue
        if key_text in _RAW_JSON_FIELDS and isinstance(value, str) and include_raw_json:
            sanitized[key_text] = _sanitize_raw_json(value) or _sanitize_mcp_value(value)
            continue
        sanitized[key_text] = _sanitize_mcp_value(value)

    if include_raw_json and raw_rows_sanitized and isinstance(raw_rows_sanitized, dict):
        # keep normalized raw data sanitized if callers consume it via flattened keys too
        for key_text in list(sanitized.keys()):
            if key_text in raw_rows_sanitized:
                sanitized[key_text] = raw_rows_sanitized[key_text]
    return sanitized


def _sanitize_mcp_records(records: list[dict[str, Any]], *, include_raw_json: bool = False) -> list[dict[str, Any]]:
    return [
        _sanitize_mcp_record(record, include_raw_json=include_raw_json)
        for record in records
    ]


def _page_records(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    total: int | None = None,
) -> dict[str, Any]:
    if limit <= 0:
        page = []
    else:
        page = rows[offset:offset + limit]
    payload: dict[str, Any] = {
        "rows": page,
        "returned": len(page),
        "limit": limit,
        "offset": offset,
        "has_more": limit > 0 and (offset + len(page)) < (total if total is not None else len(rows)),
    }
    if total is not None:
        payload["total"] = total
    return payload


def _paged_payload_from_page(
    rows: list[dict[str, Any]],
    *,
    total: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    returned = len(rows)
    return {
        "rows": rows,
        "returned": returned,
        "limit": limit,
        "offset": offset,
        "has_more": limit > 0 and offset + returned < total,
        "total": total,
    }


def _date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).date()


def _datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).to_pydatetime()


def _safe_export_path(base_dir: Path, name: str, suffix: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "export")).strip("._")
    if not stem:
        stem = "export"
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    stem = stem[:80]
    path = base_dir / f"{stem}{suffix}"
    index = 1
    while path.exists():
        path = base_dir / f"{stem}_{index}{suffix}"
        index += 1
    return path


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_allowlisted_source_file(upload: dict[str, Any]) -> tuple[Path | None, str | None]:
    path_value = str(upload.get("path") or "").strip()
    expected_suffix = str(upload.get("suffix") or "").lower()
    expected_sha = str(upload.get("sha256") or "").strip().lower()
    expected_size = upload.get("size")
    if not path_value or not expected_suffix or expected_size in (None, "") or not expected_sha:
        return None, "uploaded file integrity metadata is missing"
    try:
        expected_size_int = int(expected_size)
    except (TypeError, ValueError):
        return None, "uploaded file integrity metadata is missing"

    path = Path(path_value).expanduser()
    if not path.is_file():
        return None, "uploaded file is no longer available"
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return None, "uploaded file type is not allowed"
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return None, "uploaded file is too large"
    if size != expected_size_int:
        return None, "uploaded file changed after upload"

    if expected_suffix != suffix:
        return None, "uploaded file changed after upload"
    if _file_sha256(path) != expected_sha:
        return None, "uploaded file changed after upload"
    return path, None


def _validate_uploaded_file_record(upload: UploadedFile | Any) -> tuple[Path | None, str | None]:
    if upload is None:
        return None, "uploaded file is not available"

    original_path = str(getattr(upload, "original_path", "") or "").strip()
    if not original_path:
        return None, "uploaded file is not available"

    path = Path(original_path).expanduser()
    if not path.is_file():
        return None, "uploaded file is no longer available"

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return None, "uploaded file type is not allowed"

    expected_size = getattr(upload, "file_size", None)
    expected_sha = str(getattr(upload, "file_sha256", "") or "").strip().lower()
    if expected_size in (None, "") or not expected_sha:
        return None, "uploaded file integrity metadata is missing"
    try:
        expected_size_int = int(expected_size)
    except (TypeError, ValueError):
        return None, "uploaded file integrity metadata is missing"
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None:
        return None, "uploaded file integrity metadata is missing"

    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return None, "uploaded file is too large"
    if size != expected_size_int:
        return None, "uploaded file changed after upload"

    if _file_sha256(path) != expected_sha:
        return None, "uploaded file changed after upload"

    return path, None


def _build_uploaded_file_session_query(session, source_file_id: str) -> UploadedFile | None:
    try:
        file_id = int(source_file_id)
    except (TypeError, ValueError):
        file_id = None

    query = session.query(UploadedFile)
    if file_id is not None:
        record = query.filter(UploadedFile.id == file_id).first()
        if record is not None:
            return record

    return query.filter(UploadedFile.file_sha256 == source_file_id.lower()).first()


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].apply(lambda v: None if pd.isna(v) else pd.Timestamp(v).isoformat())
    return [_jsonable(row) for row in safe.to_dict(orient="records")]


class LocalDataService:
    """Read-only app-data facade with controlled export actions."""

    def __init__(self, *, export_dir: Path | None = None, upload_allowlist: dict[str, Any] | None = None):
        self.export_dir = Path(export_dir) if export_dir else EXPORT_DIR
        self.upload_allowlist: dict[str, dict[str, Any]] = {}
        for upload_id, upload in (upload_allowlist or {}).items():
            clean_id = str(upload_id or "").strip()
            if not clean_id:
                continue
            if isinstance(upload, dict):
                path = str(upload.get("path") or "").strip()
                name = str(upload.get("name") or "").strip()
                clean_upload: dict[str, Any] = {"path": path, "name": name}
                if "size" in upload:
                    clean_upload["size"] = upload.get("size")
                if "suffix" in upload:
                    clean_upload["suffix"] = str(upload.get("suffix") or "").lower()
                if "sha256" in upload:
                    clean_upload["sha256"] = str(upload.get("sha256") or "").lower()
            else:
                path = str(upload or "").strip()
                name = ""
                clean_upload = {"path": path, "name": name}
            if path:
                self.upload_allowlist[clean_id] = clean_upload

    def list_data_sources(self) -> dict[str, Any]:
        sqlite_tables: list[dict[str, Any]] = []
        sqlite_error = None
        try:
            engine = db_engine.create_engine()
            with engine.connect() as conn:
                inspector = sa_inspect(conn)
                for table in inspector.get_table_names():
                    try:
                        count = conn.exec_driver_sql(f'SELECT COUNT(*) FROM "{table}"').scalar()
                    except Exception:
                        count = None
                    sqlite_tables.append({"name": table, "rows": count})
        except Exception as exc:
            sqlite_error = str(exc)

        alarm_paths = [state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE]
        duckdb_sources = []
        for path in alarm_paths:
            exists = Path(path).exists()
            row_count = 0
            duckdb_error = None
            if exists:
                previous = alarm_store.ALARM_DB_FILE
                try:
                    alarm_store.set_alarm_db_file(path)
                    row_count = alarm_store.count_alarms(alarm_store.AlarmQuery())
                except Exception as exc:
                    row_count = None
                    duckdb_error = str(exc)
                finally:
                    alarm_store.set_alarm_db_file(previous)
            duckdb_sources.append({
                "path": str(path),
                "exists": exists,
                "rows": row_count,
                "error": duckdb_error,
                "modified": datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat() if exists else None,
            })

        return {
            "sqlite": {
                "path": str(db_engine.DB_PATH),
                "exists": Path(db_engine.DB_PATH).exists(),
                "tables": sqlite_tables,
                "error": sqlite_error,
            },
            "duckdb": duckdb_sources,
            "blob_storage": {
                "path": str(blob_repo.BLOB_DIR),
                "exists": Path(blob_repo.BLOB_DIR).exists(),
            },
            "exports": str(self.export_dir),
        }

    def get_current_time(self) -> dict[str, Any]:
        local_now = datetime.now().astimezone()
        utc_now = datetime.now(timezone.utc)
        return {
            "local_time": local_now.isoformat(timespec="seconds"),
            "utc_time": utc_now.isoformat(timespec="seconds"),
            "timezone": local_now.tzname() or "local",
        }

    def _with_alarm_source(self, fn):
        previous = alarm_store.ALARM_DB_FILE
        last_result = None
        last_error: Exception | None = None
        for path in (state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE):
            if not Path(path).exists():
                continue
            try:
                alarm_store.set_alarm_db_file(path)
                result = fn()
                last_result = result
                if isinstance(result, pd.DataFrame):
                    if not result.empty:
                        return result
                elif isinstance(result, dict):
                    if int(result.get("total") or result.get("row_count") or 0) > 0:
                        return result
                elif result:
                    return result
            except Exception as exc:
                last_error = exc
                continue
            finally:
                alarm_store.set_alarm_db_file(previous)
        if last_result is not None:
            return last_result
        try:
            return fn()
        except Exception:
            if last_error is not None:
                raise last_error from None
            raise

    def query_alarms(self, **kwargs) -> dict[str, Any]:
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_id") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
            sort_by=str(kwargs.get("sort_by") or "occurred_on"),
            sort_desc=bool(kwargs.get("sort_desc", False)),
            limit=_limit(kwargs.get("limit"), default=100),
            offset=max(int(kwargs.get("offset") or 0), 0),
        )
        df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
        return {"rows": _df_records(df), "row_count": len(df)}

    def query_alarm_events(self, **kwargs) -> dict[str, Any]:
        sort_direction = str(kwargs.get("sort_direction") or "").strip().lower()
        sort_by = str(kwargs.get("sort_by") or "occurred_on").strip() or "occurred_on"
        sort_desc = bool(kwargs.get("sort_desc", False))
        if sort_direction in {"asc", "desc"}:
            sort_desc = sort_direction == "desc"

        site_raw = (
            str(kwargs.get("site_code") or "")
            if str(kwargs.get("site_code") or "")
            else str(kwargs.get("site_id") or "")
        ).strip()
        site_text = str(kwargs.get("site_text") or "").strip()
        site_scope_keys = [site_raw] if site_raw else None
        if site_scope_keys:
            site_text = ""

        q = alarm_store.AlarmQuery(
            site_text=site_text,
            site_scope_keys=site_scope_keys,
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
            sort_by=sort_by,
            sort_desc=sort_desc,
            limit=_mcp_limit(kwargs.get("limit")),
            offset=_mcp_offset(kwargs.get("offset")),
        )

        try:
            count_q = replace(q, limit=None, offset=0)

            def run_query():
                rows = _sanitize_mcp_records(_df_records(alarm_store.query_alarms(q)))
                total = alarm_store.count_alarms(count_q)
                return {
                    "rows": rows,
                    "returned": len(rows),
                    "limit": q.limit or 0,
                    "offset": q.offset,
                    "has_more": (q.limit or 0) > 0 and (q.offset + len(rows)) < total,
                    "total": total,
                }

            return self._with_alarm_source(run_query)
        except Exception as exc:
            return {
                "rows": [],
                "returned": 0,
                "limit": q.limit or 0,
                "offset": q.offset,
                "has_more": False,
                "total": 0,
                "error": _sanitize_mcp_value(str(exc)),
            }

    def query_backup_times(self, **kwargs) -> dict[str, Any]:
        min_minutes = float(kwargs.get("min_minutes") or 0)
        limit = _limit(kwargs.get("limit"), default=100)
        offset = max(int(kwargs.get("offset") or 0), 0)
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_id") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
            both_pd=True,
            sort_by="occurred_on",
            sort_desc=False,
            limit=None,
            offset=0,
        )

        def _run():
            df = alarm_store.query_alarms(q)
            result, err = compute_backup_times(df)
            if err or result is None or result.empty:
                return {
                    "rows": [],
                    "row_count": 0,
                    "total_count": 0,
                    "site_count": 0,
                    "site_ids": [],
                    "min_minutes": min_minutes,
                    "threshold_minutes": min_minutes,
                }

            working = result.copy()
            working["_backup_td"] = pd.to_timedelta(working["backup_time"], errors="coerce")
            working = working[working["_backup_td"].notna()].copy()
            if min_minutes > 0:
                working = working[working["_backup_td"] > pd.Timedelta(minutes=min_minutes)].copy()
            if working.empty:
                return {
                    "rows": [],
                    "row_count": 0,
                    "total_count": 0,
                    "site_count": 0,
                    "site_ids": [],
                    "min_minutes": min_minutes,
                    "threshold_minutes": min_minutes,
                }

            working = working.sort_values("_backup_td", ascending=False).reset_index(drop=True)
            grouped_rows: list[dict[str, Any]] = []
            for _site_id, group in working.groupby("site_id", sort=False):
                top = group.iloc[0]
                backup_td = top["_backup_td"]
                grouped_rows.append({
                    "site_id": top.get("site_id"),
                    "network_type": top.get("network_type"),
                    "vendor": top.get("vendor"),
                    "max_backup_time": top.get("backup_time"),
                    "max_backup_minutes": round(float(backup_td.total_seconds() / 60.0), 2) if pd.notna(backup_td) else None,
                    "incident_count": int(len(group)),
                    "power_time": top.get("power_time"),
                    "power_cleared": top.get("power_cleared"),
                    "down_time": top.get("down_time"),
                    "end_event_type": top.get("end_event_type"),
                })

            total_count = len(grouped_rows)
            site_rows = grouped_rows[offset:offset + limit] if limit > 0 else []
            site_ids = [str(row.get("site_id") or "") for row in site_rows if str(row.get("site_id") or "").strip()]
            return {
                "rows": _jsonable(site_rows),
                "row_count": len(site_rows),
                "total_count": total_count,
                "site_count": total_count,
                "site_ids": site_ids,
                "min_minutes": min_minutes,
                "threshold_minutes": min_minutes,
            }

        return self._with_alarm_source(_run)

    def _query_all_bdt_rows(
        self,
        *,
        site_code: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        all_rows: list[dict[str, Any]] = []
        page_limit = MAX_QUERY_LIMIT
        offset = 0
        total: int | None = None

        while True:
            payload = self.query_bdt_results(
                site_code=site_code,
                date_from=date_from,
                date_to=date_to,
                limit=page_limit,
                offset=offset,
            )
            page = payload.get("rows") if isinstance(payload, dict) else []
            if not isinstance(page, list):
                break

            row_count = 0
            for row in page:
                if isinstance(row, dict):
                    all_rows.append(row)
                    row_count += 1

            if total is None:
                total = int(payload.get("total") or 0)

            if row_count < page_limit:
                break
            if total is not None and total <= len(all_rows):
                break

            offset += page_limit
            if offset > (total or (offset + row_count)):
                break

        return all_rows

    @staticmethod
    def _chart_page_payload(
        series: list[dict[str, Any]],
        *,
        total: int,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        page = series[offset:offset + limit] if limit > 0 else []
        return {
            "points": total,
            "labels": [point.get("label") for point in page],
            "values": [point.get("value") for point in page],
            "series": page,
            "returned": len(page),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(page)) < total,
            "total": total,
        }

    @staticmethod
    def _bdt_graph_series(rows: list[dict[str, Any]], graph_type: str) -> tuple[list[str], list[float]]:
        if graph_type == "bdt_verdict_counts":
            verdict_values = [row.get("overall_verdict") for row in rows if isinstance(row, dict)]
            counts = pd.Series(verdict_values).fillna("Unknown").value_counts()
            return counts.index.astype(str).tolist(), counts.astype(float).tolist()

        if graph_type == "bdt_duration_trend":
            trend_rows = [row for row in rows if isinstance(row, dict)]
            sorted_rows = sorted(trend_rows, key=lambda row: str(row.get("test_date") or ""))
            labels: list[str] = []
            values: list[float] = []
            for row in sorted_rows:
                value = row.get("discharge_minutes")
                if value is None:
                    continue
                labels.append(str(row.get("test_date") or "")[:10])
                values.append(float(value))
            return labels, values

        return [], []

    def alarm_stats(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        site_text = str(kwargs.get("site_text") or "").strip()
        site_scope_keys: list[str] | None = None
        if site_raw and not site_text:
            normalized = catalog_store._normalize_site_id(site_raw)
            normalized_candidates = {site_raw, site_raw.upper()}
            if normalized:
                normalized_candidates.add(normalized)
                normalized_candidates.add(str(normalized).replace("-", ""))
            site_scope_keys = [value for value in normalized_candidates if value]

        q = alarm_store.AlarmQuery(
            site_text=site_text,
            site_scope_keys=site_scope_keys,
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        return self._with_alarm_source(lambda: alarm_store.stats(q)) or alarm_store.stats(q)

    def query_bdt_results(self, **kwargs) -> dict[str, Any]:
        limit = _limit(kwargs.get("limit"), default=100)
        offset = max(int(kwargs.get("offset") or 0), 0)
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        overall = str(kwargs.get("overall") or "").strip()
        rule_id = str(kwargs.get("rule_id") or "").strip().upper()
        rule_verdict = str(kwargs.get("rule_verdict") or "").strip()
        date_from = _date_value(kwargs.get("date_from"))
        date_to = _date_value(kwargs.get("date_to"))

        session = db_engine.get_session()
        try:
            query = (
                session.query(PMValidationRun, BDTTest)
                .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
                .order_by(PMValidationRun.run_at.desc())
            )
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            if overall:
                query = query.filter(PMValidationRun.overall_verdict == overall)
            if date_from:
                query = query.filter(BDTTest.test_date >= date_from)
            if date_to:
                query = query.filter(BDTTest.test_date <= date_to)
            if rule_id or rule_verdict:
                query = query.join(PMRuleResult, PMRuleResult.validation_run_id == PMValidationRun.id)
                if rule_id:
                    query = query.join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                    query = query.filter(PMRuleCatalog.rule_code == rule_id)
                if rule_verdict:
                    query = query.filter(PMRuleResult.verdict == rule_verdict)

            total = query.count()
            rows = []
            for run, bdt in query.offset(offset).limit(limit).all():
                rows.append({
                    "validation_run_id": run.id,
                    "bdt_test_id": bdt.id,
                    "site_code": bdt.site_code,
                    "test_date": bdt.test_date,
                    "filename": self._filename_for_bdt(session, bdt),
                    "overall_verdict": run.overall_verdict,
                    "run_at": run.run_at,
                    "discharge_minutes": bdt.discharge_minutes,
                    "battery_brand": bdt.battery_brand,
                    "num_strings": bdt.num_strings,
                    "end_voltage": bdt.end_voltage,
                })
            return {"total": total, "rows": _jsonable(rows)}
        finally:
            session.close()

    def get_bdt_detail(self, **kwargs) -> dict[str, Any]:
        run_id = kwargs.get("validation_run_id")
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        test_date = _date_value(kwargs.get("test_date"))
        session = db_engine.get_session()
        try:
            query = session.query(PMValidationRun, BDTTest).join(
                BDTTest,
                PMValidationRun.bdt_test_id == BDTTest.id,
            )
            if run_id:
                query = query.filter(PMValidationRun.id == int(run_id))
            elif site_code:
                query = query.filter(BDTTest.site_code == site_code)
                if test_date:
                    query = query.filter(BDTTest.test_date == test_date)
            else:
                return {"error": "validation_run_id or site_code is required"}
            run, bdt = query.order_by(PMValidationRun.run_at.desc()).first() or (None, None)
            if not run or not bdt:
                return {"error": "BDT validation result not found"}

            rules = []
            for rr, catalog in (
                session.query(PMRuleResult, PMRuleCatalog)
                .join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                .filter(PMRuleResult.validation_run_id == run.id)
                .order_by(PMRuleCatalog.rule_code.asc())
                .all()
            ):
                detail = rr.evidence_json
                try:
                    detail = json.loads(detail) if detail else ""
                except (TypeError, json.JSONDecodeError):
                    pass
                rules.append({
                    "rule_code": catalog.rule_code,
                    "rule_name": catalog.name,
                    "verdict": rr.verdict,
                    "detail": detail,
                })

            return _jsonable({
                "validation_run_id": run.id,
                "overall_verdict": run.overall_verdict,
                "run_at": run.run_at,
                "bdt": {
                    "id": bdt.id,
                    "filename": self._filename_for_bdt(session, bdt),
                    "site_code": bdt.site_code,
                    "site_name": bdt.site_name,
                    "test_date": bdt.test_date,
                    "time_in": bdt.time_in,
                    "time_out": bdt.time_out,
                    "battery_brand": bdt.battery_brand,
                    "battery_ah": bdt.battery_ah,
                    "battery_voltage": bdt.battery_voltage,
                    "num_strings": bdt.num_strings,
                    "num_batteries": bdt.num_batteries,
                    "num_modules": bdt.num_modules,
                    "start_voltage": bdt.start_voltage,
                    "end_voltage": bdt.end_voltage,
                    "discharge_minutes": bdt.discharge_minutes,
                    "discharge_readings": json.loads(bdt.discharge_readings_json or "[]"),
                    "string_discharge_readings": json.loads(bdt.string_discharge_readings_json or "[]"),
                },
                "rules": rules,
                "photos": self._photo_rows_for_bdt(session, bdt.id),
            })
        finally:
            session.close()

    def get_photo_metadata(self, **kwargs) -> dict[str, Any]:
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        bdt_test_id = kwargs.get("bdt_test_id")
        limit = _limit(kwargs.get("limit"), default=100)
        session = db_engine.get_session()
        try:
            query = (
                session.query(BDTPhoto, BDTTest, BlobAsset)
                .join(BDTTest, BDTPhoto.bdt_test_id == BDTTest.id)
                .outerjoin(BlobAsset, BDTPhoto.blob_asset_id == BlobAsset.id)
            )
            if bdt_test_id:
                query = query.filter(BDTPhoto.bdt_test_id == int(bdt_test_id))
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            rows = []
            for photo, bdt, blob in query.order_by(BDTTest.test_date.desc(), BDTPhoto.slot_index.asc()).limit(limit).all():
                rows.append(self._photo_row(photo, bdt, blob))
            return {"rows": _jsonable(rows), "row_count": len(rows)}
        finally:
            session.close()

    def read_photo_blob(self, **kwargs) -> dict[str, Any]:
        sha256 = str(kwargs.get("sha256") or "").strip().lower()
        if not sha256:
            return {"error": "sha256 is required"}
        session = db_engine.get_session()
        try:
            blob = session.query(BlobAsset).filter(BlobAsset.sha256 == sha256).first()
            if not blob:
                return {"error": "blob not found"}
            local_path = str(blob.local_path or "").strip()
            if not local_path:
                return {"error": "blob not found"}
            path = Path(local_path).expanduser().resolve(strict=False)
            blob_dir = Path(blob_repo.BLOB_DIR).expanduser().resolve(strict=False)
            if not path.is_relative_to(blob_dir):
                return {"error": "blob file is outside blob storage"}
            if not path.is_file():
                return {"error": "blob file missing"}
            mime_type = str(blob.mime_type or "").strip()
            if not mime_type:
                return {"error": "blob mime type is required"}
            if not mime_type.lower().startswith("image/"):
                return {"error": "blob mime type is not an image"}
            if path.stat().st_size > MAX_BLOB_BYTES:
                return {"error": f"blob too large; max {MAX_BLOB_BYTES} bytes"}
            content = path.read_bytes()
            if len(content) > MAX_BLOB_BYTES:
                return {"error": f"blob too large; max {MAX_BLOB_BYTES} bytes"}
            actual_sha = hashlib.sha256(content).hexdigest()
            stored_sha = str(blob.sha256 or "").strip().lower()
            if actual_sha != sha256 or actual_sha != stored_sha:
                return {"error": "blob hash mismatch"}
            try:
                Image.open(BytesIO(content)).verify()
            except Exception:
                return {"error": "blob content is not a valid image"}
            return {
                "sha256": stored_sha,
                "mime_type": mime_type,
                "base64": base64.b64encode(content).decode("ascii"),
            }
        finally:
            session.close()

    def get_site_dossier(self, **kwargs) -> dict[str, Any]:
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        if not site_code:
            return {"error": "site_code is required"}
        alarm_df = self._alarm_rows_for_sites(
            {site_code},
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        bdt_payload = self.query_bdt_results(
            site_code=site_code,
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            limit=MAX_QUERY_LIMIT,
        )
        bdt_rows = bdt_payload.get("rows", []) if isinstance(bdt_payload, dict) else []
        bdt_details = []
        for row in bdt_rows[:_limit(kwargs.get("bdt_detail_limit"), default=MAX_QUERY_LIMIT)]:
            if isinstance(row, dict) and row.get("validation_run_id"):
                bdt_details.append(self.get_bdt_detail(validation_run_id=row["validation_run_id"]))

        export_path = self._export_site_dossier_workbook(
            site_code=site_code,
            alarm_df=alarm_df,
            bdt_rows=[row for row in bdt_rows if isinstance(row, dict)],
            bdt_details=[detail for detail in bdt_details if isinstance(detail, dict) and "error" not in detail],
        )

        return {
            "site_code": site_code,
            "alarm_total": len(alarm_df),
            "alarm_stats": self._site_alarm_summary(alarm_df),
            "alarm_rows": _df_records(alarm_df.head(_limit(kwargs.get("alarm_preview_limit"), default=50))),
            "bdt_total": int(bdt_payload.get("total") or len(bdt_rows)) if isinstance(bdt_payload, dict) else len(bdt_rows),
            "bdt_rows": _jsonable(bdt_rows[:_limit(kwargs.get("bdt_preview_limit"), default=50)]),
            "bdt_details": _jsonable(bdt_details),
            "export_path": str(export_path),
        }

    def generate_graph(self, **kwargs) -> dict[str, Any]:
        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        title = str(kwargs.get("title") or graph_type.replace("_", " ").title())
        if graph_type.startswith("alarm_"):
            alarm_df = self._alarm_rows_for_sites(
                {site_code} if site_code else set(self._alarm_reference_df()["site_id"].map(normalize_site_key).dropna()),
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
            ) if site_code else self._with_alarm_source(lambda: alarm_store.query_alarms(alarm_store.AlarmQuery(
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
                limit=None,
                offset=0,
            )))
            labels, values = self._alarm_graph_series(alarm_df, graph_type)
        elif graph_type in {"bdt_verdict_counts", "bdt_duration_trend"}:
            rows = self._query_all_bdt_rows(
                site_code=site_code,
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
            )
            labels, values = self._bdt_graph_series(rows, graph_type)
        else:
            return {"error": f"unsupported graph_type: {graph_type}"}

        path = _safe_export_path(self.export_dir / "charts", f"{title}_{site_code or 'all'}", "png")
        self._draw_bar_chart(path, title, labels, values)
        return {
            "path": str(path),
            "graph_type": graph_type,
            "site_code": site_code,
            "points": len(values),
            "labels": labels,
            "values": values,
        }

    def get_computed_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "").strip().lower()
        if report_type.startswith("chart:"):
            report_type = report_type[len("chart:"):].strip()

        include_raw_json = bool(kwargs.get("include_raw_json", False))
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        site_code = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        site_text = str(kwargs.get("site_text") or "").strip()
        date_from = _date_value(kwargs.get("date_from"))
        date_to = _date_value(kwargs.get("date_to"))
        category = str(kwargs.get("category") or "All")
        vendor = str(kwargs.get("vendor") or "All")
        network_type = str(kwargs.get("network_type") or "All")
        export_week = str(kwargs.get("export_week") or "").strip()
        week_label = str(kwargs.get("week_label") or "").strip()
        source_file_id = str(kwargs.get("source_file_id") or "").strip()
        section = str(kwargs.get("section") or "").strip()

        def _missing_inputs_error(required_fields: list[str], action: str) -> dict[str, Any]:
            return {
                "error": f"missing required fields: {', '.join(required_fields)}",
                "required": required_fields,
                "action": action,
                "report_type": report_type,
            }

        required_week = export_week or week_label

        if report_type == "backup_times":
            backup_limit = min(limit, MAX_QUERY_LIMIT)
            payload = self.query_backup_times(
                site_text=(site_text or site_code or ""),
                category=category,
                vendor=vendor,
                network_type=network_type,
                date_from=kwargs.get("date_from"),
                date_to=kwargs.get("date_to"),
                min_minutes=kwargs.get("min_minutes"),
                limit=backup_limit,
                offset=offset,
            )
            rows = _sanitize_mcp_records(payload.get("rows") if isinstance(payload, dict) else [], include_raw_json=include_raw_json)
            total = int((payload.get("total_count") if isinstance(payload, dict) else 0) or 0)
            if total <= 0:
                total = int((payload.get("row_count") if isinstance(payload, dict) else 0) or 0)
            if total <= 0:
                total = len(rows)
            return {
                "report_type": "backup_times",
                "rows": rows,
                "returned": len(rows),
                "limit": backup_limit,
                "offset": offset,
                "has_more": (offset + len(rows)) < total,
                "total": total,
                "row_count": len(rows),
                "total_count": int(payload.get("total_count") or 0) if isinstance(payload, dict) else 0,
                "site_count": int(payload.get("site_count") or len(rows)) if isinstance(payload, dict) else len(rows),
                "site_ids": payload.get("site_ids", []) if isinstance(payload, dict) else [],
                "min_minutes": payload.get("min_minutes") if isinstance(payload, dict) else None,
                "threshold_minutes": payload.get("threshold_minutes") if isinstance(payload, dict) else None,
                "error": payload.get("error") if isinstance(payload, dict) else None,
            }

        alarm_chart_types = {
            "alarm_category_counts",
            "alarm_daily_counts",
            "alarm_duration_by_category",
        }
        bdt_chart_types = {
            "bdt_verdict_counts",
            "bdt_duration_trend",
        }

        if report_type in alarm_chart_types:
            q = alarm_store.AlarmQuery(
                site_text=site_text if not site_code else "",
                site_scope_keys={normalize_site_key(site_code)} if site_code else None,
                category=category,
                vendor=vendor,
                network_type=network_type,
                date_from=date_from,
                date_to=date_to,
                sort_by="occurred_on",
                sort_desc=False,
                limit=None,
                offset=0,
            )
            alarm_df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
            labels, values = self._alarm_graph_series(alarm_df, report_type)
            series = [{"label": str(label), "value": _sanitize_mcp_value(value)} for label, value in zip(labels, values)]
            payload = self._chart_page_payload(series, total=len(series), limit=limit, offset=offset)
            payload["report_type"] = report_type
            payload["labels"] = _sanitize_mcp_value(payload["labels"])
            payload["values"] = _sanitize_mcp_value(payload["values"])
            payload["series"] = [{"label": str(point["label"]), "value": _sanitize_mcp_value(point["value"])} for point in payload["series"]]
            return payload

        if report_type in bdt_chart_types:
            rows = self._query_all_bdt_rows(
                site_code=normalize_site_key(site_code) if site_code else "",
                date_from=date_from,
                date_to=date_to,
            )
            labels, values = self._bdt_graph_series(rows, report_type)
            series = [{"label": str(label), "value": _sanitize_mcp_value(value)} for label, value in zip(labels, values)]
            payload = self._chart_page_payload(series, total=len(series), limit=limit, offset=offset)
            payload["report_type"] = report_type
            payload["labels"] = _sanitize_mcp_value(payload["labels"])
            payload["values"] = _sanitize_mcp_value(payload["values"])
            payload["series"] = [{"label": str(point["label"]), "value": _sanitize_mcp_value(point["value"])} for point in payload["series"]]
            return payload

        if report_type in {
            "ht_meet",
            "ht_weekly_summary",
            "ht_consolidated_history",
        }:
            if not required_week:
                return _missing_inputs_error(
                    ["export_week"],
                    "Provide export_week (format W##-YY), retry the request.",
                )

            q = alarm_store.AlarmQuery(
                site_text=site_text if not site_code else "",
                site_scope_keys={normalize_site_key(site_code)} if site_code else None,
                category=category,
                vendor=vendor,
                network_type=network_type,
                date_from=date_from,
                date_to=date_to,
                sort_by="occurred_on",
                sort_desc=False,
                limit=None,
                offset=0,
            )
            source_df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
            if report_type == "ht_meet":
                rows = compute_ht_meet_rows(source_df, week_label=required_week)
                meet = rows[1]
                row_payload = _sanitize_mcp_records(meet.to_dict(orient="records"), include_raw_json=include_raw_json)
            elif report_type == "ht_weekly_summary":
                _, _, meet_source = _compute_ht_meet_frames(source_df, week_label=required_week)
                summary = build_temp_alarm_summary(meet_source, week_label=required_week)
                row_payload = _sanitize_mcp_records(summary.to_dict(orient="records"), include_raw_json=include_raw_json)
            else:
                history_source = _filter_source_from_week(source_df, DEFAULT_HT_HISTORY_START_WEEK)
                _, _, consolidated_source = _compute_ht_meet_frames(
                    history_source,
                    week_label=None,
                )
                consolidated = build_temp_alarm_summary(
                    consolidated_source,
                    week_label=None,
                    rolling_week_label=required_week,
                )
                row_payload = _sanitize_mcp_records(consolidated.to_dict(orient="records"), include_raw_json=include_raw_json)

            payload = _paged_payload_from_page(
                row_payload[offset:offset + limit] if limit > 0 else [],
                total=len(row_payload),
                limit=limit,
                offset=offset,
            )
            payload.update({
                "report_type": report_type,
                "export_week": required_week,
                "week_label": week_label or export_week,
            })
            return payload

        if report_type == "bdt_export":
            section_name = section
            health_pct = 80.0 if kwargs.get("health_pct") is None else float(kwargs.get("health_pct"))

            site_keys: set[str] | None = None
            if source_file_id:
                source_path, _, source_error = self._resolve_source_file(kwargs, required=False)
                if source_error:
                    return {
                        "error": source_error,
                        "required": ["source_file_id"],
                        "action": "Use one of the uploaded allowlisted source_file_id values from chat context.",
                        "report_type": report_type,
                    }
                if source_path is not None:
                    source_df, _sheet_name, site_col = self._read_site_list(source_path)
                    site_keys = collect_site_sheet_keys(source_df, site_col)

            if not section_name:
                return {
                    "error": "section is required for bdt_export",
                    "required": ["section"],
                    "action": "Provide section name, one of Validation Results, Rule Evidence, or PM Summary.",
                    "report_type": report_type,
                }

            bdt_results = self._load_validation_results(site_keys=site_keys)
            sheets = build_bdt_export_sheets(bdt_results, health_pct=health_pct)
            available_sections = list(sheets.keys())
            resolved_section = ""
            for name in available_sections:
                if name.lower() == section_name.lower():
                    resolved_section = name
                    break
            if not resolved_section:
                return {
                    "error": f"unknown section: {section_name}",
                    "required": ["section"],
                    "action": f"Use one of {', '.join(available_sections)}.",
                    "sections": available_sections,
                    "report_type": report_type,
                }

            all_rows = _sanitize_mcp_records(sheets[resolved_section].to_dict(orient="records"), include_raw_json=include_raw_json)
            rows = all_rows[offset:offset + limit] if limit > 0 else []
            payload = _paged_payload_from_page(
                rows,
                total=len(all_rows),
                limit=limit,
                offset=offset,
            )
            payload.update({
                "report_type": report_type,
                "section": resolved_section,
                "sections": available_sections,
                "health_pct": health_pct,
            })
            return payload

        if report_type == "accepted_pm_report":
            source_path, resolved_source_file_id, source_err = self._resolve_source_file(kwargs, required=True)
            if source_err:
                return {
                    "error": source_err,
                    "required": ["source_file_id"],
                    "action": "Use one of the uploaded allowlisted source_file_id values from chat context.",
                    "report_type": report_type,
                }

            source_file_id = resolved_source_file_id

            if source_path is None:
                return {
                    "error": "source_file_id is required",
                    "required": ["source_file_id"],
                    "action": "Upload an Accepted PM file and pass its source_file_id.",
                    "report_type": report_type,
                }

            reference_df = self._alarm_reference_df()
            pm_df, sheet_name, site_col, date_col, status_col = read_pm_accept_sheet(
                str(source_path),
                reference_df,
            )
            site_keys = collect_site_sheet_keys(pm_df, site_col)
            alarm_df = self._alarm_rows_for_pm_sheet(pm_df, site_col, date_col)
            bdt_results = self._load_validation_results(site_keys=site_keys)
            all_report_df = build_pm_accept_report(
                pm_df,
                site_col,
                date_col,
                bdt_results,
                alarm_df,
                health_pct=80.0 if kwargs.get("health_pct") is None else float(kwargs.get("health_pct")),
                status_column=status_col,
            )
            all_rows = _sanitize_mcp_records(all_report_df.to_dict(orient="records"), include_raw_json=include_raw_json)
            rows = all_rows[offset:offset + limit] if limit > 0 else []
            payload = _paged_payload_from_page(
                rows,
                total=len(all_rows),
                limit=limit,
                offset=offset,
            )
            payload.update({
                "report_type": report_type,
                "sheet_name": sheet_name,
                "site_column": site_col,
                "date_column": date_col,
                "status_column": status_col,
                "source_file_id": resolved_source_file_id,
            })
            return payload

        return {"error": f"unsupported report_type: {report_type}"}

    def export_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "bdt_results").strip()
        fmt = str(kwargs.get("format") or "xlsx").lower()
        name = str(kwargs.get("name") or report_type)
        passthrough = {
            key: value for key, value in kwargs.items()
            if key not in {"report_type", "format", "name"}
        }
        if fmt not in {"xlsx", "csv"}:
            return {"error": "format must be xlsx or csv"}

        if report_type == "alarms":
            payload = self.query_alarms(**kwargs)
            df = pd.DataFrame(payload["rows"])
        elif report_type == "bdt_results":
            payload = self.query_bdt_results(**kwargs)
            df = pd.DataFrame(payload["rows"])
        elif report_type == "photo_manifest":
            payload = self.get_photo_metadata(**kwargs)
            df = pd.DataFrame(payload["rows"])
        elif report_type == "site_alarm_report":
            return self._export_site_alarm_report(fmt=fmt, name=name, **passthrough)
        elif report_type == "accepted_pm_report":
            return self._export_accepted_pm_report(fmt=fmt, name=name, **passthrough)
        elif report_type == "bdt_export":
            return self._export_bdt_validation_report(fmt=fmt, name=name, **passthrough)
        else:
            return {"error": f"unsupported report_type: {report_type}"}

        path = _safe_export_path(self.export_dir, name, fmt)
        if fmt == "csv":
            df.to_csv(path, index=False)
        else:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=report_type[:31] or "Report")
        return {"path": str(path), "rows": len(df), "format": fmt, "report_type": report_type}

    def _export_site_alarm_report(self, *, fmt: str, name: str, **kwargs) -> dict[str, Any]:
        source_path, source_file_id, error = self._resolve_source_file(kwargs, required=True)
        if error:
            return {"error": error}
        if source_path is None:
            return {"error": "source_file_id is required"}
        site_df, sheet_name, site_col = self._read_site_list(source_path)
        site_keys = collect_site_sheet_keys(site_df, site_col)
        alarm_df = self._alarm_rows_for_sites(
            site_keys,
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        report_df = build_site_alarm_report(site_df, site_col, alarm_df)
        path = _safe_export_path(self.export_dir, name, fmt)
        self._write_dataframe(report_df, path, fmt, "Site Report")
        return {
            "path": str(path),
            "rows": len(report_df),
            "format": fmt,
            "report_type": "site_alarm_report",
            "source_file_id": source_file_id,
            "sheet_name": sheet_name,
            "site_column": site_col,
            "site_count": len(site_keys),
            "alarm_rows": len(alarm_df),
        }

    def _export_accepted_pm_report(self, *, fmt: str, name: str, **kwargs) -> dict[str, Any]:
        source_path, source_file_id, error = self._resolve_source_file(kwargs, required=True)
        if error:
            return {"error": error}
        if source_path is None:
            return {"error": "source_file_id is required"}
        reference_df = self._alarm_reference_df()
        pm_df, sheet_name, site_col, date_col, status_col = read_pm_accept_sheet(
            str(source_path),
            reference_df,
        )
        site_keys = collect_site_sheet_keys(pm_df, site_col)
        alarm_df = self._alarm_rows_for_pm_sheet(pm_df, site_col, date_col)
        bdt_results = self._load_validation_results(site_keys=site_keys)
        report_df = build_pm_accept_report(
            pm_df,
            site_col,
            date_col,
            bdt_results,
            alarm_df,
            health_pct=float(kwargs.get("health_pct") or 80.0),
            status_column=status_col,
        )
        path = _safe_export_path(self.export_dir, name, fmt)
        self._write_dataframe(report_df, path, fmt, "Accepted PM")
        return {
            "path": str(path),
            "rows": len(report_df),
            "format": fmt,
            "report_type": "accepted_pm_report",
            "source_file_id": source_file_id,
            "sheet_name": sheet_name,
            "site_column": site_col,
            "date_column": date_col,
            "status_column": status_col,
            "site_count": len(site_keys),
            "alarm_rows": len(alarm_df),
            "bdt_results": len(bdt_results),
        }

    def _export_bdt_validation_report(self, *, fmt: str, name: str, **kwargs) -> dict[str, Any]:
        if fmt != "xlsx":
            return {"error": "bdt_export supports xlsx only because it contains multiple sheets"}
        site_keys: set[str] | None = None
        source_path, source_file_id, error = self._resolve_source_file(kwargs, required=False)
        if error:
            return {"error": error}
        if source_path:
            site_df, _sheet_name, site_col = self._read_site_list(source_path)
            site_keys = collect_site_sheet_keys(site_df, site_col)
        bdt_results = self._load_validation_results(site_keys=site_keys)
        sheets = build_bdt_export_sheets(
            bdt_results,
            health_pct=float(kwargs.get("health_pct") or 80.0),
        )
        path = _safe_export_path(self.export_dir, name, "xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, index=False, sheet_name=str(sheet_name)[:31] or "Sheet")
        return {
            "path": str(path),
            "rows": sum(len(df) for df in sheets.values()),
            "format": "xlsx",
            "report_type": "bdt_export",
            "source_file_id": source_file_id,
            "site_count": len(site_keys or set()),
            "bdt_results": len(bdt_results),
            "sheets": list(sheets.keys()),
        }

    def _resolve_source_file(self, kwargs: dict[str, Any], *, required: bool) -> tuple[Path | None, str, str | None]:
        source_file_id = str(kwargs.get("source_file_id") or "").strip()
        if source_file_id:
            upload = self.upload_allowlist.get(source_file_id)
            if upload is None:
                session = db_engine.get_session()
                try:
                    try:
                        upload = _build_uploaded_file_session_query(session, source_file_id)
                    except Exception:
                        upload = None
                    if upload is None:
                        return None, source_file_id, f"unknown source_file_id: {source_file_id}"
                    source_path, error = _validate_uploaded_file_record(upload)
                    return source_path, source_file_id, error
                finally:
                    session.close()
            source_path, error = _validate_allowlisted_source_file(upload)
            return source_path, source_file_id, error

        source_file_path = str(kwargs.get("source_file_path") or "").strip()
        if source_file_path:
            return None, "", "source_file_id is required"

        if required:
            return None, "", "source_file_id is required"
        return None, "", None

    def _read_site_list(self, source_path: Path) -> tuple[pd.DataFrame, str, str]:
        if source_path.suffix.lower() == ".csv":
            df = pd.read_csv(source_path, dtype=object)
            site_col = infer_site_id_column(df, self._alarm_reference_df())
            if not site_col:
                raise ValueError("Could not identify a site ID column in the uploaded file.")
            return df, "Sheet1", site_col

        book = pd.ExcelFile(source_path)
        reference_df = self._alarm_reference_df()
        best: tuple[pd.DataFrame, str, str, int] | None = None
        try:
            for sheet_name in book.sheet_names:
                df = pd.read_excel(book, sheet_name=sheet_name, dtype=object)
                site_col = infer_site_id_column(df, reference_df)
                if not site_col:
                    continue
                keys = {normalize_site_key(v) for v in df[site_col].dropna().tolist() if normalize_site_key(v)}
                score = len(keys)
                if best is None or score > best[3]:
                    best = (df, sheet_name, site_col, score)
        finally:
            try:
                book.close()
            except Exception:
                pass
        if best is None:
            raise ValueError("Could not identify a site ID column in the uploaded workbook.")
        return best[0], best[1], best[2]

    def _alarm_reference_df(self) -> pd.DataFrame:
        try:
            values = self._with_alarm_source(lambda: alarm_store.distinct_values("site_id")) or []
        except Exception:
            values = []
        return pd.DataFrame({"site_id": values})

    def _alarm_rows_for_sites(
        self,
        site_keys: set[str],
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> pd.DataFrame:
        if not site_keys:
            return pd.DataFrame()
        query = alarm_store.AlarmQuery(
            site_scope_keys=site_keys,
            date_from=date_from,
            date_to=date_to,
            sort_by="occurred_on",
            limit=None,
            offset=0,
        )
        return self._with_alarm_source(lambda: alarm_store.query_alarms(query))

    def _alarm_rows_for_pm_sheet(self, pm_df: pd.DataFrame, site_col: str, date_col: str) -> pd.DataFrame:
        site_keys = collect_site_sheet_keys(pm_df, site_col)
        dates = pd.to_datetime(pm_df[date_col], errors="coerce", format="mixed")
        valid_dates = [pd.Timestamp(v).date() for v in dates.dropna().tolist()]
        date_from = min(valid_dates) - timedelta(days=1) if valid_dates else None
        date_to = max(valid_dates) + timedelta(days=1) if valid_dates else None
        return self._alarm_rows_for_sites(site_keys, date_from=date_from, date_to=date_to)

    def _export_site_dossier_workbook(
        self,
        *,
        site_code: str,
        alarm_df: pd.DataFrame,
        bdt_rows: list[dict[str, Any]],
        bdt_details: list[dict[str, Any]],
    ) -> Path:
        path = _safe_export_path(self.export_dir, f"site_dossier_{site_code}", "xlsx")
        rules: list[dict[str, Any]] = []
        photos: list[dict[str, Any]] = []
        discharge_rows: list[dict[str, Any]] = []
        for detail in bdt_details:
            bdt = detail.get("bdt") if isinstance(detail.get("bdt"), dict) else {}
            run_id = detail.get("validation_run_id")
            for rule in detail.get("rules", []) if isinstance(detail.get("rules"), list) else []:
                if isinstance(rule, dict):
                    rules.append({"validation_run_id": run_id, **rule})
            for photo in detail.get("photos", []) if isinstance(detail.get("photos"), list) else []:
                if isinstance(photo, dict):
                    photos.append({"validation_run_id": run_id, **photo})
            for reading in bdt.get("discharge_readings", []) if isinstance(bdt, dict) else []:
                discharge_rows.append({
                    "validation_run_id": run_id,
                    "site_code": bdt.get("site_code"),
                    "test_date": bdt.get("test_date"),
                    "reading": reading,
                })

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            alarm_df.to_excel(writer, index=False, sheet_name="Alarms")
            pd.DataFrame(bdt_rows).to_excel(writer, index=False, sheet_name="BDT Results")
            pd.DataFrame(rules).to_excel(writer, index=False, sheet_name="BDT Rules")
            pd.DataFrame(photos).to_excel(writer, index=False, sheet_name="BDT Photos")
            pd.DataFrame(discharge_rows).to_excel(writer, index=False, sheet_name="Discharge")
        return path

    @staticmethod
    def _site_alarm_summary(alarm_df: pd.DataFrame) -> dict[str, Any]:
        if alarm_df is None or alarm_df.empty:
            return {"total": 0, "by_category": {}, "first_alarm": None, "last_alarm": None}
        work = alarm_df.copy()
        if "occurred_on" in work.columns:
            work["occurred_on"] = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed")
        category_col = "alarm_category" if "alarm_category" in work.columns else None
        counts = work[category_col].fillna("Unknown").value_counts().to_dict() if category_col else {}
        return {
            "total": len(work),
            "by_category": {str(k): int(v) for k, v in counts.items()},
            "first_alarm": _jsonable(work["occurred_on"].min()) if "occurred_on" in work.columns else None,
            "last_alarm": _jsonable(work["occurred_on"].max()) if "occurred_on" in work.columns else None,
        }

    @staticmethod
    def _alarm_graph_series(alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float]]:
        if alarm_df is None or alarm_df.empty:
            return [], []
        work = alarm_df.copy()
        if graph_type == "alarm_category_counts":
            col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
            counts = work[col].fillna("Unknown").value_counts()
            return counts.index.astype(str).tolist(), counts.astype(float).tolist()
        if graph_type == "alarm_daily_counts":
            if "occurred_on" not in work.columns:
                return [], []
            days = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dropna().dt.date
            counts = days.value_counts().sort_index()
            return [str(v) for v in counts.index.tolist()], counts.astype(float).tolist()
        if graph_type == "alarm_duration_by_category":
            if "_duration_secs" not in work.columns:
                return [], []
            col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
            grouped = work.groupby(col, dropna=False)["_duration_secs"].sum().sort_values(ascending=False)
            return grouped.index.astype(str).tolist(), (grouped / 60.0).astype(float).tolist()
        return [], []

    @staticmethod
    def _chart_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
        candidates = [
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    @classmethod
    def _wrap_chart_text(cls, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        cleaned = str(text).replace("_", " ").strip()
        if not cleaned:
            return [""]
        lines: list[str] = []
        for paragraph in cleaned.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if cls._text_size(draw, candidate, font)[0] <= max_width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    @staticmethod
    def _format_chart_label(label: str) -> str:
        text = str(label).strip().replace("_", " ")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text[5:]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", text):
            return text[5:10]
        return text

    @classmethod
    def _draw_bar_chart(cls, path: Path, title: str, labels: list[str], values: list[float]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        point_count = min(len(values), 24)
        width = max(1200, min(2000, 180 + max(point_count, 1) * 58))
        height = 760
        margin_left, margin_right, margin_top, margin_bottom = 104, 48, 112, 152
        image = Image.new("RGB", (width, height), "#10111a")
        draw = ImageDraw.Draw(image)
        font = cls._chart_font(14)
        title_font = cls._chart_font(24, bold=True)
        value_font = cls._chart_font(13, bold=True)
        title_lines = cls._wrap_chart_text(draw, title, title_font, width - margin_left - margin_right)
        title_text = "\n".join(title_lines)
        title_bbox = draw.multiline_textbbox((0, 0), title_text, font=title_font, spacing=6)
        title_w = title_bbox[2] - title_bbox[0]
        draw.multiline_text(
            ((width - title_w) / 2, 24),
            title_text,
            fill="#d8def8",
            font=title_font,
            spacing=6,
        )
        if not values:
            draw.text((margin_left, height // 2), "No matching data", fill="#8f96ad", font=font)
            image.save(path)
            return
        max_points = 24
        labels = labels[:max_points]
        values = values[:max_points]
        max_value = max(max(values), 1.0)
        chart_w = width - margin_left - margin_right
        chart_h = height - margin_top - margin_bottom
        axis_color = "#3a3d55"
        draw.line((margin_left, margin_top, margin_left, margin_top + chart_h), fill=axis_color, width=2)
        draw.line((margin_left, margin_top + chart_h, margin_left + chart_w, margin_top + chart_h), fill=axis_color, width=2)
        bar_gap = 14 if len(values) <= 8 else 10
        label_band_h = 54 if len(values) <= 8 else 68
        bar_w = max(22, int((chart_w - bar_gap * (len(values) - 1)) / max(len(values), 1)))
        usable_chart_h = chart_h - label_band_h - 18
        for idx, (label, value) in enumerate(zip(labels, values, strict=False)):
            x0 = margin_left + idx * (bar_w + bar_gap)
            bar_h = int((float(value) / max_value) * max(usable_chart_h, 24))
            y0 = margin_top + chart_h - bar_h
            x1 = x0 + bar_w
            y1 = margin_top + chart_h
            draw.rectangle((x0, y0, x1, y1), fill="#7aa2ff")
            value_text = f"{value:g}"
            value_w, value_h = cls._text_size(draw, value_text, value_font)
            draw.text(
                (x0 + max(0, (bar_w - value_w) / 2), max(margin_top, y0 - value_h - 6)),
                value_text,
                fill="#d8def8",
                font=value_font,
            )
            wrapped_label = cls._wrap_chart_text(draw, cls._format_chart_label(label), font, max(bar_w + 10, 90))
            label_text = "\n".join(wrapped_label[:3])
            label_bbox = draw.multiline_textbbox((0, 0), label_text, font=font, spacing=2)
            label_w = label_bbox[2] - label_bbox[0]
            draw.multiline_text(
                (x0 + max(0, (bar_w - label_w) / 2), y1 + 10),
                label_text,
                fill="#b9c1dc",
                font=font,
                spacing=2,
                align="center",
            )
        image.save(path)

    @staticmethod
    def _write_dataframe(df: pd.DataFrame, path: Path, fmt: str, sheet_name: str) -> None:
        if fmt == "csv":
            df.to_csv(path, index=False)
            return
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31] or "Report")

    @staticmethod
    def _load_validation_results(*, site_keys: set[str] | None = None) -> list:
        session = db_engine.get_session()
        try:
            results = load_all_validation_results(session)
        finally:
            session.close()
        if not site_keys:
            return results
        return [
            result for result in results
            if normalize_site_key(getattr(result, "site_code", "")) in site_keys
        ]

    @staticmethod
    def _filename_for_bdt(session, bdt: BDTTest) -> str:
        if not bdt.file_id:
            return ""
        try:
            uploaded = session.get(UploadedFile, bdt.file_id)
            return str(uploaded.original_name or "") if uploaded else ""
        except Exception:
            return ""

    def _photo_rows_for_bdt(self, session, bdt_test_id: int) -> list[dict[str, Any]]:
        rows = []
        query = (
            session.query(BDTPhoto, BDTTest, BlobAsset)
            .join(BDTTest, BDTPhoto.bdt_test_id == BDTTest.id)
            .outerjoin(BlobAsset, BDTPhoto.blob_asset_id == BlobAsset.id)
            .filter(BDTPhoto.bdt_test_id == bdt_test_id)
            .order_by(BDTPhoto.slot_index.asc())
        )
        for photo, bdt, blob in query.all():
            rows.append(self._photo_row(photo, bdt, blob))
        return rows

    @staticmethod
    def _photo_row(photo: BDTPhoto, bdt: BDTTest, blob: BlobAsset | None) -> dict[str, Any]:
        return {
            "bdt_test_id": bdt.id,
            "site_code": bdt.site_code,
            "test_date": bdt.test_date,
            "slot_index": photo.slot_index,
            "slot_category": photo.slot_category,
            "sha256": blob.sha256 if blob else None,
            "mime_type": blob.mime_type if blob else None,
            "file_size": blob.file_size if blob else None,
            "width": blob.width if blob else None,
            "height": blob.height if blob else None,
            "local_path": blob.local_path if blob else None,
        }

    # ------------------------------------------------------------------
    # Catalog-backed tools (DuckDB)
    # ------------------------------------------------------------------

    def query_site_metadata(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        if not site_raw:
            return {"error": "site_code or site_id is required"}
        try:
            normalized = catalog_store._normalize_site_id(site_raw)
        except Exception:
            normalized = site_raw.upper()
        try:
            df = catalog_store.query_site_metadata(site_raw)
        except Exception as exc:
            return {"site_id": normalized, "rows": [], "row_count": 0, "error": _sanitize_mcp_value(str(exc))}
        rows = _df_records(df)
        for row in rows:
            raw_json = row.pop("raw_data_json", None)
            if raw_json and isinstance(raw_json, str):
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, dict):
                        row.update({str(k): v for k, v in parsed.items()})
                except (json.JSONDecodeError, TypeError):
                    pass
        rows = _sanitize_mcp_records(rows)
        return {"site_id": normalized, "rows": rows, "row_count": len(rows)}

    def search_site_metadata(self, **kwargs) -> dict[str, Any]:
        limit = _limit(kwargs.get("limit"), default=100)
        try:
            df = catalog_store.search_site_metadata(
                site_text=str(kwargs.get("site_text") or kwargs.get("site_code") or kwargs.get("site_id") or "").strip() or None,
                area=str(kwargs.get("area") or "").strip() or None,
                subcontractor=str(kwargs.get("subcontractor") or kwargs.get("contractor") or "").strip() or None,
                backup_status=str(kwargs.get("backup_status") or kwargs.get("battery_status") or "").strip() or None,
                limit=limit,
            )
        except Exception as exc:
            return {"rows": [], "row_count": 0, "error": _sanitize_mcp_value(str(exc))}
        rows = _df_records(df)
        for row in rows:
            raw_json = row.pop("raw_data_json", None)
            if raw_json and isinstance(raw_json, str):
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, dict):
                        row.update({str(k): v for k, v in parsed.items()})
                except (json.JSONDecodeError, TypeError):
                    pass
        rows = _sanitize_mcp_records(rows)
        return {"rows": rows, "row_count": len(rows)}

    def query_bdt_summary(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip() or None
        reporting_period = str(kwargs.get("reporting_period") or kwargs.get("period") or "").strip() or None
        week = str(kwargs.get("week") or "").strip() or None
        date_from = str(kwargs.get("date_from") or "").strip() or None
        date_to = str(kwargs.get("date_to") or "").strip() or None
        limit = _limit(kwargs.get("limit"), default=100)
        offset = max(int(kwargs.get("offset") or 0), 0)
        try:
            df = catalog_store.query_bdt_summary(
                site_id=site_raw,
                reporting_period=reporting_period,
                week=week,
                test_date_from=date_from,
                test_date_to=date_to,
            )
        except Exception as exc:
            return {"rows": [], "total": 0, "error": _sanitize_mcp_value(str(exc))}
        total = len(df)
        if total and offset:
            df = df.iloc[offset:]
        if total and limit is not None:
            df = df.head(limit)
        rows = _df_records(df)
        for row in rows:
            raw_json = row.pop("raw_data_json", None)
            if raw_json and isinstance(raw_json, str):
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, dict):
                        row.update({str(k): v for k, v in parsed.items()})
                except (json.JSONDecodeError, TypeError):
                    pass
        rows = _sanitize_mcp_records(rows)
        return {"rows": rows, "total": total}

    def query_bdt_full(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        reporting_period = str(kwargs.get("reporting_period") or kwargs.get("period") or "").strip() or None
        week = str(kwargs.get("week") or "").strip() or None
        date_from = str(kwargs.get("date_from") or "").strip() or None
        date_to = str(kwargs.get("date_to") or "").strip() or None
        overall = str(kwargs.get("overall") or "").strip()
        rule_id = str(kwargs.get("rule_id") or "").strip().upper()
        rule_verdict = str(kwargs.get("rule_verdict") or "").strip()
        include_raw_json = bool(kwargs.get("include_raw_json", False))
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))

        try:
            normalized_site = catalog_store._normalize_site_id(site_raw)
        except Exception:
            normalized_site = site_raw.upper() if site_raw else None

        def _matches_site(candidate: Any) -> bool:
            if not normalized_site:
                return True
            normalized_candidate = catalog_store._normalize_site_id(candidate)
            return normalized_candidate == normalized_site

        def _parse_json(value: Any) -> Any:
            if not value:
                return None
            if isinstance(value, (dict, list)):
                return value
            if not isinstance(value, str):
                return None
            try:
                parsed = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return None
            return parsed

        def _empty_section_payload() -> dict[str, Any]:
            return {
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
            }

        def _site_filter_values() -> list[str]:
            if not site_raw:
                return []
            normalized_only = catalog_store._normalize_site_id(site_raw)
            values = {site_raw.strip().upper()}
            if normalized_only:
                values.add(normalized_only)
            normalized_candidate = set(values)
            for value in list(values):
                normalized_candidate.add(value.replace("-", ""))
                compact = value.replace("-", "")
                if len(compact) > 3:
                    normalized_candidate.add(f"{compact[:3]}-{compact[3:]}")
            return list(normalized_candidate)

        site_filter_values = _site_filter_values()
        date_from_value = _date_value(date_from)
        date_to_value = _date_value(date_to)

        source_errors: list[str] = []

        def _collect_error(message: str) -> None:
            source_errors.append(_sanitize_mcp_value(message))

        try:
            summary_df = catalog_store.query_bdt_summary(
                site_id=site_raw or None,
                reporting_period=reporting_period,
                week=week,
                test_date_from=date_from,
                test_date_to=date_to,
            )
            summary_rows = [
                _sanitize_mcp_record(_jsonable(row), include_raw_json=include_raw_json)
                for row in _df_records(summary_df)
            ]
            summary_payload = _page_records(summary_rows, limit=limit, offset=offset, total=len(summary_rows))
        except Exception as exc:
            _collect_error(str(exc))
            summary_payload = {
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
            }

        validation_run_rows_raw: list[dict[str, Any]] = []
        test_rows: dict[int, BDTTest] = {}
        upload_by_test: dict[int, UploadedFile | None] = {}
        validation_payload = _empty_section_payload()
        bdt_test_payload = _empty_section_payload()
        rule_payload = _empty_section_payload()
        photo_payload = _empty_section_payload()
        review_payload = _empty_section_payload()

        session = db_engine.get_session()
        try:
            try:
                scoped_validation_run_ids: set[int] | None = None
                if rule_id or rule_verdict:
                    scoped_validation_run_ids = set()
                    rule_scope_query = (
                        session.query(PMValidationRun.id)
                        .join(PMRuleResult, PMRuleResult.validation_run_id == PMValidationRun.id)
                        .join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                        .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
                    )
                    if site_filter_values:
                        rule_scope_query = rule_scope_query.filter(BDTTest.site_code.in_(site_filter_values))
                    if date_from_value is not None:
                        rule_scope_query = rule_scope_query.filter(BDTTest.test_date >= date_from_value)
                    if date_to_value is not None:
                        rule_scope_query = rule_scope_query.filter(BDTTest.test_date <= date_to_value)
                    if rule_id:
                        rule_scope_query = rule_scope_query.filter(PMRuleCatalog.rule_code == rule_id)
                    if rule_verdict:
                        rule_scope_query = rule_scope_query.filter(PMRuleResult.verdict == rule_verdict)
                    if overall:
                        rule_scope_query = rule_scope_query.filter(PMValidationRun.overall_verdict == overall)
                    for run_id_row in rule_scope_query.all() or []:
                        if isinstance(run_id_row, tuple):
                            raw_run_id = run_id_row[0]
                        else:
                            raw_run_id = run_id_row
                        try:
                            scoped_validation_run_ids.add(int(raw_run_id))
                        except (TypeError, ValueError):
                            continue

                validation_query = (
                    session.query(PMValidationRun, BDTTest, UploadedFile)
                    .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
                    .outerjoin(UploadedFile, UploadedFile.id == BDTTest.file_id)
                    .order_by(PMValidationRun.run_at.desc())
                )

                if site_filter_values:
                    validation_query = validation_query.filter(BDTTest.site_code.in_(site_filter_values))
                if date_from_value is not None:
                    validation_query = validation_query.filter(BDTTest.test_date >= date_from_value)
                if date_to_value is not None:
                    validation_query = validation_query.filter(BDTTest.test_date <= date_to_value)
                if overall:
                    validation_query = validation_query.filter(PMValidationRun.overall_verdict == overall)
                if scoped_validation_run_ids is not None:
                    validation_query = validation_query.filter(PMValidationRun.id.in_(scoped_validation_run_ids))

                validation_run_rows_raw = []
                seen_validation_run_ids: set[int] = set()
                for run, bdt, uploaded in (
                    validation_query
                    .offset(offset)
                    .limit(limit)
                    .all()
                    or []
                ):
                    if not isinstance(run, PMValidationRun) or not isinstance(bdt, BDTTest):
                        continue
                    if not _matches_site(getattr(bdt, "site_code", "")):
                        continue
                    run_id = run.id
                    if run_id is None:
                        continue
                    run_id = int(run_id)
                    if run_id in seen_validation_run_ids:
                        continue
                    seen_validation_run_ids.add(run_id)

                    test_rows[run.bdt_test_id] = bdt
                    if uploaded is not None:
                        upload_by_test[run.bdt_test_id] = uploaded
                    validation_run_rows_raw.append({
                        "validation_run_id": run_id,
                        "bdt_test_id": run.bdt_test_id,
                        "site_code": bdt.site_code,
                        "test_date": bdt.test_date,
                        "overall_verdict": run.overall_verdict,
                        "run_at": run.run_at,
                        "filename": uploaded.original_name if uploaded else None,
                        "original_path": uploaded.original_path if uploaded else None,
                        "file_id": bdt.file_id,
                        "discharge_minutes": bdt.discharge_minutes,
                        "battery_brand": bdt.battery_brand,
                        "num_strings": bdt.num_strings,
                        "end_voltage": bdt.end_voltage,
                        "created_at": run.created_at,
                        "parameter_set_id": run.parameter_set_id,
                    })

                validation_payload = _paged_payload_from_page(
                    _sanitize_mcp_records(
                        validation_run_rows_raw,
                        include_raw_json=include_raw_json,
                    ),
                    total=validation_query.count(),
                    limit=limit,
                    offset=offset,
                )
            except Exception as exc:
                _collect_error(str(exc))

            try:
                bdt_test_query = (
                    session.query(BDTTest, UploadedFile)
                    .outerjoin(UploadedFile, UploadedFile.id == BDTTest.file_id)
                    .order_by(BDTTest.test_date.desc(), BDTTest.id.desc())
                )
                if site_filter_values:
                    bdt_test_query = bdt_test_query.filter(BDTTest.site_code.in_(site_filter_values))
                if date_from_value is not None:
                    bdt_test_query = bdt_test_query.filter(BDTTest.test_date >= date_from_value)
                if date_to_value is not None:
                    bdt_test_query = bdt_test_query.filter(BDTTest.test_date <= date_to_value)

                bdt_test_rows_raw: list[dict[str, Any]] = []
                for bdt, uploaded in (
                    bdt_test_query
                    .offset(offset)
                    .limit(limit)
                    .all() or []
                ):
                    if not isinstance(bdt, BDTTest):
                        continue
                    if not _matches_site(getattr(bdt, "site_code", "")):
                        continue
                    discharge = _parse_json(getattr(bdt, "discharge_readings_json", None))
                    string_discharge = _parse_json(getattr(bdt, "string_discharge_readings_json", None))
                    if not isinstance(discharge, list):
                        discharge = []
                    if not isinstance(string_discharge, list):
                        string_discharge = []
                    bdt_test_rows_raw.append({
                        "bdt_test_id": bdt.id,
                        "site_code": bdt.site_code,
                        "test_date": bdt.test_date,
                        "time_in": bdt.time_in,
                        "time_out": bdt.time_out,
                        "site_name": bdt.site_name,
                        "filename": uploaded.original_name if uploaded else None,
                        "original_path": uploaded.original_path if uploaded else None,
                        "file_id": bdt.file_id,
                        "battery_brand": bdt.battery_brand,
                        "battery_ah": bdt.battery_ah,
                        "battery_voltage": bdt.battery_voltage,
                        "num_batteries": bdt.num_batteries,
                        "num_modules": bdt.num_modules,
                        "start_voltage": bdt.start_voltage,
                        "end_voltage": bdt.end_voltage,
                        "discharge_minutes": bdt.discharge_minutes,
                        "discharge_readings": discharge,
                        "string_discharge_readings": string_discharge,
                        "created_at": bdt.created_at,
                    })

                bdt_test_payload = _paged_payload_from_page(
                    _sanitize_mcp_records(
                        bdt_test_rows_raw,
                        include_raw_json=include_raw_json,
                    ),
                    total=bdt_test_query.count(),
                    limit=limit,
                    offset=offset,
                )
            except Exception as exc:
                _collect_error(str(exc))

            try:
                rule_rows_raw: list[dict[str, Any]] = []
                rule_query = (
                    session.query(PMRuleResult, PMRuleCatalog, PMValidationRun, BDTTest)
                    .join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                    .join(PMValidationRun, PMRuleResult.validation_run_id == PMValidationRun.id)
                    .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
                    .order_by(PMRuleResult.created_at.desc())
                )
                if site_filter_values:
                    rule_query = rule_query.filter(BDTTest.site_code.in_(site_filter_values))
                if date_from_value is not None:
                    rule_query = rule_query.filter(BDTTest.test_date >= date_from_value)
                if date_to_value is not None:
                    rule_query = rule_query.filter(BDTTest.test_date <= date_to_value)
                if overall:
                    rule_query = rule_query.filter(PMValidationRun.overall_verdict == overall)
                if rule_id:
                    rule_query = rule_query.filter(PMRuleCatalog.rule_code == rule_id)
                if rule_verdict:
                    rule_query = rule_query.filter(PMRuleResult.verdict == rule_verdict)

                rule_total = rule_query.count()

                for rule_result, rule, run, bdt in (
                    rule_query
                    .offset(offset)
                    .limit(limit)
                    .all() or []
                ):
                    if not _matches_site(getattr(bdt, "site_code", "")):
                        continue
                    rule_rows_raw.append({
                        "rule_result_id": rule_result.id,
                        "validation_run_id": run.id,
                        "rule_id": rule.rule_code,
                        "rule_name": rule.name,
                        "verdict": rule_result.verdict,
                        "evidence_json": rule_result.evidence_json,
                        "site_code": bdt.site_code,
                        "test_date": bdt.test_date,
                        "created_at": rule_result.created_at,
                    })

                rule_payload = _paged_payload_from_page(
                    _sanitize_mcp_records(rule_rows_raw, include_raw_json=include_raw_json),
                    total=rule_total,
                    limit=limit,
                    offset=offset,
                )
            except Exception as exc:
                _collect_error(str(exc))

            try:
                photo_query = (
                    session.query(BDTPhoto, BDTTest, BlobAsset)
                    .join(BDTTest, BDTPhoto.bdt_test_id == BDTTest.id)
                    .outerjoin(BlobAsset, BDTPhoto.blob_asset_id == BlobAsset.id)
                    .order_by(BDTPhoto.slot_index.asc())
                )
                if site_filter_values:
                    photo_query = photo_query.filter(BDTTest.site_code.in_(site_filter_values))
                if date_from_value is not None:
                    photo_query = photo_query.filter(BDTTest.test_date >= date_from_value)
                if date_to_value is not None:
                    photo_query = photo_query.filter(BDTTest.test_date <= date_to_value)

                photo_rows_raw: list[dict[str, Any]] = []
                for photo, bdt, blob in (
                    photo_query
                    .offset(offset)
                    .limit(limit)
                    .all() or []
                ):
                    if not _matches_site(getattr(bdt, "site_code", "")):
                        continue
                    photo_rows_raw.append({
                        "photo_id": photo.id,
                        "bdt_test_id": bdt.id,
                        "site_code": bdt.site_code,
                        "test_date": bdt.test_date,
                        "slot_index": photo.slot_index,
                        "slot_category": photo.slot_category,
                        "sha256": blob.sha256 if blob else None,
                        "mime_type": blob.mime_type if blob else None,
                        "file_size": blob.file_size if blob else None,
                        "width": blob.width if blob else None,
                        "height": blob.height if blob else None,
                        "local_path": blob.local_path if blob else None,
                        "created_at": photo.created_at,
                    })

                photo_payload = _paged_payload_from_page(
                    _sanitize_mcp_records(photo_rows_raw, include_raw_json=include_raw_json),
                    total=photo_query.count(),
                    limit=limit,
                    offset=offset,
                )
            except Exception as exc:
                _collect_error(str(exc))

            try:
                review_query = session.query(ReviewEvent).order_by(ReviewEvent.created_at.desc())
                if site_filter_values:
                    review_query = review_query.filter(ReviewEvent.site_code.in_(site_filter_values))
                if date_from_value is not None:
                    review_query = review_query.filter(ReviewEvent.test_date >= date_from_value)
                if date_to_value is not None:
                    review_query = review_query.filter(ReviewEvent.test_date <= date_to_value)
                if overall:
                    review_query = review_query.filter(ReviewEvent.verdict == overall)

                review_rows_raw: list[dict[str, Any]] = []
                for review_event in review_query.offset(offset).limit(limit).all() or []:
                    if not _matches_site(getattr(review_event, "site_code", "")):
                        continue
                    payload_data = _parse_json(review_event.payload_json)
                    if not isinstance(payload_data, dict):
                        payload_data = {}

                    reviewer = _first_non_empty(review_event.reviewer)
                    if reviewer is None:
                        reviewer = _first_non_empty(payload_data.get("reviewer"))

                    engineer = _first_non_empty(payload_data.get("engineer"))
                    comment = _first_non_empty(payload_data.get("comment"))

                    review_rows_raw.append(_jsonable({
                        "event_type": review_event.event_type,
                        "site_code": review_event.site_code,
                        "test_date": review_event.test_date,
                        "reviewer": reviewer,
                        "engineer": engineer,
                        "comment": comment,
                        "filename": review_event.filename,
                        "verdict": review_event.verdict,
                        "payload_json": review_event.payload_json,
                        "reviewed_at": review_event.reviewed_at,
                        "created_at": review_event.created_at,
                    }))

                review_payload = _paged_payload_from_page(
                    _sanitize_mcp_records(review_rows_raw, include_raw_json=include_raw_json),
                    total=review_query.count(),
                    limit=limit,
                    offset=offset,
                )
            except Exception as exc:
                _collect_error(str(exc))
        finally:
            session.close()

        payload = {
            "bdt_summary": summary_payload,
            "validation_runs": validation_payload,
            "bdt_tests": bdt_test_payload,
            "rule_results": rule_payload,
            "photos": photo_payload,
            "review_events": review_payload,
        }
        if source_errors:
            payload["error"] = _sanitize_mcp_value( "; ".join(source_errors))
        return payload

    def _metadata_site_rows_by_id(self) -> tuple[dict[str, dict[str, Any]], set[str], list[str]]:
        try:
            df = catalog_store.read_site_metadata()
        except Exception as exc:
            return {}, set(), [str(exc)]

        needed_columns = {
            "site_id",
            "raw_data_json",
            "site_name",
            "sitename",
            "name",
            "area",
            "orange_area",
            "orangearea",
            "contractor",
            "subcontractor",
            "sub_contractor",
            "subcontractor_name",
            "backup_status",
            "backupstatus",
            "battery_status",
            "batterystatus",
        }
        available_columns = [col for col in needed_columns if col in df.columns]
        if available_columns:
            df = df.loc[:, available_columns]

        rows_by_id: dict[str, dict[str, Any]] = {}
        source_errors: list[str] = []
        for row in _df_records(df):
            raw_rows: dict[str, Any] = {}
            raw_value = row.get("raw_data_json")
            if isinstance(raw_value, str) and raw_value.strip():
                try:
                    parsed = json.loads(raw_value)
                    if isinstance(parsed, dict):
                        raw_rows = {str(k): v for k, v in parsed.items()}
                except (TypeError, json.JSONDecodeError):
                    pass

            site_id = str(row.get("site_id") or "").strip()
            if not site_id:
                continue
            normalized = catalog_store._normalize_site_id(site_id)
            if not normalized:
                continue
            existing = rows_by_id.setdefault(
                normalized,
                {},
            )
            existing.setdefault("site_id", normalized)
            existing.setdefault("site_code", normalized)
            for field in ("site_name", "area", "contractor", "subcontractor", "backup_status", "battery_status"):
                value = _metadata_value_for_field(row, raw_rows, field)
                if value is not None:
                    existing[field] = value

        return rows_by_id, set(rows_by_id.keys()), source_errors

    def _alarm_site_ids(self) -> tuple[set[str], list[str]]:
        ids: set[str] = set()
        errors: list[str] = []
        for path in (state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE):
            if not Path(path).exists():
                continue
            previous = alarm_store.ALARM_DB_FILE
            try:
                alarm_store.set_alarm_db_file(path)
                for value in alarm_store.distinct_values("site_id"):
                    normalized = alarm_store._normalize_site_key(value)
                    if normalized:
                        ids.add(normalized)
            except Exception as exc:
                errors.append(str(exc))
            finally:
                alarm_store.set_alarm_db_file(previous)
        return ids, errors

    def _alarm_site_stats(self) -> tuple[dict[str, dict[str, Any]], list[str]]:
        counts: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        for path in (state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE):
            if not Path(path).exists():
                continue
            previous = alarm_store.ALARM_DB_FILE
            try:
                alarm_store.set_alarm_db_file(path)
                con = alarm_store._safe_connect(read_only=True)
                if con is None:
                    continue
                try:
                    table_cols = alarm_store._table_columns(con)
                    if "site_id" not in table_cols:
                        continue
                    select_clause = "SELECT site_id, COUNT(*) AS alarm_count"
                    if "occurred_on" in table_cols:
                        select_clause += ", MAX(occurred_on) AS latest_alarm_at"
                    query = f"{select_clause} FROM {alarm_store.ALARM_TABLE} GROUP BY site_id"
                    for row in con.execute(query).fetchall():
                        raw_site_id = row[0]
                        count = row[1]
                        latest_row = row[2] if len(row) > 2 else None
                        normalized = alarm_store._normalize_site_key(raw_site_id)
                        if not normalized:
                            continue
                        current = counts.setdefault(
                            normalized,
                            {"alarm_count": 0, "latest_alarm_at": None},
                        )
                        current["alarm_count"] += int(count or 0)
                        if latest_row is not None:
                            latest = pd.to_datetime(latest_row, errors="coerce")
                            if pd.notna(latest):
                                existing = current["latest_alarm_at"]
                                if existing is None or existing < latest:
                                    current["latest_alarm_at"] = latest
                finally:
                    con.close()
            except Exception as exc:
                errors.append(str(exc))
            finally:
                alarm_store.set_alarm_db_file(previous)
        return counts, errors

    def _bdt_summary_site_ids(self) -> tuple[set[str], list[str]]:
        try:
            return catalog_store.read_bdt_summary_site_ids(), []
        except AttributeError:
            # Backward-compatible fallback for older catalog store versions.
            df = catalog_store.read_bdt_summary()
        except Exception as exc:
            return set(), [str(exc)]
        return {
            catalog_store._normalize_site_id(value)
            for value in df.get("site_id", pd.Series([], dtype="string"))
            if catalog_store._normalize_site_id(value)
        }, []

    def _bdt_summary_site_stats(self) -> tuple[dict[str, dict[str, Any]], list[str]]:
        try:
            return catalog_store.read_bdt_summary_site_stats(), []
        except AttributeError:
            pass
        except Exception as exc:
            return {}, [str(exc)]

        try:
            df = catalog_store.read_bdt_summary()
        except Exception as exc:
            return {}, [str(exc)]
        if df is None or df.empty:
            return {}, []

        if "site_id" not in df.columns:
            return {}, []

        grouped = df.groupby("site_id", dropna=False)
        stats: dict[str, dict[str, Any]] = {}
        for site_id, group in grouped:
            normalized = catalog_store._normalize_site_id(site_id)
            if not normalized:
                continue
            stats.setdefault(
                normalized,
                {
                    "bdt_summary_count": 0,
                    "latest_bdt_at": None,
                },
            )
            stats[normalized]["bdt_summary_count"] += int(group.shape[0])
            latest_value = group.get("test_date", pd.Series([], dtype="object")).max()
            stats[normalized]["latest_bdt_at"] = _jsonable(
                _max_timestamp(
                    stats[normalized]["latest_bdt_at"],
                    latest_value,
                )
            )
        return stats, []

    def _bdt_validation_site_ids(self) -> tuple[set[str], list[str]]:
        ids: set[str] = set()
        errors: list[str] = []
        session = db_engine.get_session()
        try:
            rows = (
                session.query(BDTTest.site_code)
                .join(PMValidationRun, PMValidationRun.bdt_test_id == BDTTest.id)
                .distinct()
                .all()
            )
            for row in rows:
                candidate = row[0] if isinstance(row, (tuple, list)) else row
                normalized = catalog_store._normalize_site_id(candidate)
                if normalized:
                    ids.add(normalized)
        except Exception as exc:
            errors.append(str(exc))
        finally:
            session.close()
        return ids, errors

    def _bdt_validation_site_stats(self) -> tuple[dict[str, dict[str, Any]], list[str]]:
        stats: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        session = db_engine.get_session()
        try:
            rows = (
                session.query(
                    BDTTest.site_code,
                    func.count(PMValidationRun.id).label("bdt_validation_count"),
                    func.max(PMValidationRun.run_at).label("latest_validation_run_at"),
                    func.max(BDTTest.test_date).label("latest_validation_test_date"),
                )
                .join(PMValidationRun, PMValidationRun.bdt_test_id == BDTTest.id)
                .group_by(BDTTest.site_code)
                .all()
            )
            for row in rows:
                if not row:
                    continue
                site_code = row[0]
                count_value = row[1]
                latest_validation_run_at = row[2]
                latest_validation_test_date = row[3]
                normalized = catalog_store._normalize_site_id(site_code)
                if not normalized:
                    continue
                current = stats.setdefault(
                    normalized,
                    {
                        "bdt_validation_count": 0,
                        "latest_validation_run_at": None,
                        "latest_validation_test_date": None,
                    },
                )
                current["bdt_validation_count"] += int(count_value or 0)
                current["latest_validation_run_at"] = _jsonable(
                    _max_timestamp(
                        current["latest_validation_run_at"],
                        latest_validation_run_at,
                    )
                )
                current["latest_validation_test_date"] = _jsonable(
                    _max_timestamp(
                        current["latest_validation_test_date"],
                        latest_validation_test_date,
                    )
                )
        except Exception as exc:
            errors.append(str(exc))
        finally:
            session.close()
        return stats, errors

    def list_sites(self, **kwargs) -> dict[str, Any]:
        site_text = str(kwargs.get("site_text") or kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        area = str(kwargs.get("area") or "").strip()
        contractor = str(kwargs.get("contractor") or "").strip()
        subcontractor = str(kwargs.get("subcontractor") or "").strip()
        backup_status = str(kwargs.get("backup_status") or "").strip()
        battery_status = str(kwargs.get("battery_status") or "").strip()
        has_metadata = kwargs.get("has_metadata")
        has_alarms = kwargs.get("has_alarms")
        has_bdt_summary = kwargs.get("has_bdt_summary")
        has_bdt_validation = kwargs.get("has_bdt_validation")
        has_bdt = kwargs.get("has_bdt")
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))

        metadata_rows, metadata_ids, metadata_errors = self._metadata_site_rows_by_id()
        alarm_ids, alarm_errors = self._alarm_site_ids()
        alarm_stats, alarm_stats_errors = self._alarm_site_stats()
        bdt_summary_ids, summary_errors = self._bdt_summary_site_ids()
        bdt_summary_stats, bdt_summary_stats_errors = self._bdt_summary_site_stats()
        bdt_validation_ids, validation_errors = self._bdt_validation_site_ids()
        bdt_validation_stats, bdt_validation_stats_errors = self._bdt_validation_site_stats()

        all_sites = sorted(metadata_ids | alarm_ids | bdt_summary_ids | bdt_validation_ids)
        area_text = area.upper()
        contractor_text = contractor.upper()
        subcontractor_text = subcontractor.upper()
        backup_text = backup_status.upper()
        battery_text = battery_status.upper()
        site_text_upper = site_text.upper()
        normalized_site_text = catalog_store._normalize_site_id(site_text) if site_text else ""

        rows: list[dict[str, Any]] = []
        for site_id in all_sites:
            has_md = site_id in metadata_ids
            has_alarm = site_id in alarm_ids
            has_summary = site_id in bdt_summary_ids
            has_validation = site_id in bdt_validation_ids

            if has_metadata is True and not has_md:
                continue
            if has_metadata is False and has_md:
                continue
            if has_alarms is True and not has_alarm:
                continue
            if has_alarms is False and has_alarm:
                continue
            if has_bdt_summary is True and not has_summary:
                continue
            if has_bdt_summary is False and has_summary:
                continue
            if has_bdt_validation is True and not has_validation:
                continue
            if has_bdt_validation is False and has_validation:
                continue
            has_bdt_combined = has_summary or has_validation
            if has_bdt is True and not has_bdt_combined:
                continue
            if has_bdt is False and has_bdt_combined:
                continue

            metadata = metadata_rows.get(site_id, {})
            metadata_area = str(metadata.get("area") or "").upper()
            metadata_contractor = str(metadata.get("contractor") or "").upper()
            metadata_subcontractor = str(metadata.get("subcontractor") or "").upper()
            metadata_backup = str(metadata.get("backup_status") or "").upper()
            metadata_battery = str(metadata.get("battery_status") or "").upper()

            if site_text:
                match_text = (site_id + str(metadata.get("site_name", "") or "")).upper()
                if site_text_upper not in match_text and (
                    not normalized_site_text
                    or normalized_site_text not in match_text
                ):
                    continue

            if area and area_text not in metadata_area:
                continue

            if contractor and contractor_text not in metadata_contractor:
                continue

            if subcontractor and subcontractor_text not in metadata_subcontractor:
                continue

            if backup_status and backup_text not in metadata_backup:
                continue

            if battery_status and battery_text not in metadata_battery:
                continue

            row = {
                "site_id": site_id,
                "site_code": site_id,
                "has_metadata": has_md,
                "has_alarms": has_alarm,
                "alarm_count": alarm_stats.get(site_id, {}).get("alarm_count", 0),
                "latest_alarm_at": _jsonable(alarm_stats.get(site_id, {}).get("latest_alarm_at")),
                "has_bdt_summary": has_summary,
                "bdt_summary_count": bdt_summary_stats.get(site_id, {}).get("bdt_summary_count", 0),
                "has_bdt_validation": has_validation,
                "bdt_validation_count": bdt_validation_stats.get(site_id, {}).get("bdt_validation_count", 0),
                "has_bdt": has_bdt_combined,
                "latest_bdt_at": _jsonable(_max_timestamp(
                    bdt_summary_stats.get(site_id, {}).get("latest_bdt_at"),
                    bdt_validation_stats.get(site_id, {}).get("latest_validation_test_date"),
                    bdt_validation_stats.get(site_id, {}).get("latest_validation_run_at"),
                )),
            }
            for field in ("site_name", "area", "contractor", "subcontractor", "backup_status", "battery_status"):
                if field in metadata:
                    row[field] = metadata.get(field)
            rows.append(row)

        sanitized_rows = _sanitize_mcp_records(rows)
        payload = _page_records(sanitized_rows, limit=limit, offset=offset, total=len(sanitized_rows))
        source_errors = _sanitize_source_errors({
            "site_metadata": metadata_errors,
            "alarms": alarm_errors,
            "alarm_stats": alarm_stats_errors,
            "bdt_summary": summary_errors,
            "bdt_summary_stats": bdt_summary_stats_errors,
            "bdt_validation": validation_errors,
            "bdt_validation_stats": bdt_validation_stats_errors,
        })
        if source_errors:
            payload["source_errors"] = source_errors
        return payload

    def query_network_summary(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_text") or kwargs.get("site_id") or kwargs.get("site_code") or "").strip()
        area = str(kwargs.get("area") or "").strip()
        subcontractor = str(kwargs.get("subcontractor") or "").strip()
        contractor = str(kwargs.get("contractor") or "").strip()
        backup_status = str(kwargs.get("backup_status") or "").strip()
        battery_status = str(kwargs.get("battery_status") or "").strip()
        include_raw_json = bool(kwargs.get("include_raw_json", False))
        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))

        try:
            df = catalog_store.read_site_metadata()
        except Exception as exc:
            return {
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
                "error": _sanitize_mcp_value(str(exc)),
            }

        if df is None or df.empty:
            return {
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
            }

        filtered = df.copy()
        if site_raw:
            site_text = str(site_raw).upper().strip()
            normalized_site = catalog_store._normalize_site_id(site_raw)
            mask = pd.Series(False, index=filtered.index)
            if "site_id" in filtered.columns:
                site_col = filtered["site_id"].fillna("").astype(str).str.upper()
                mask |= site_col.str.contains(normalized_site or site_text, case=False, regex=False, na=False)
            if "site_name" in filtered.columns:
                mask |= filtered["site_name"].fillna("").astype(str).str.contains(site_text, case=False, regex=False, na=False)
            if "name" in filtered.columns and not mask.any():
                mask |= filtered["name"].fillna("").astype(str).str.contains(site_text, case=False, regex=False, na=False)
            filtered = filtered[mask]

        if area:
            area_text = str(area).strip()
            if "area" in filtered.columns:
                filtered = filtered[filtered["area"].fillna("").astype(str).str.contains(area_text, case=False, regex=False, na=False)]

        if subcontractor:
            sub_text = str(subcontractor).strip()
            submask = pd.Series(False, index=filtered.index)
            if "subcontractor" in filtered.columns:
                submask |= filtered["subcontractor"].fillna("").astype(str).str.contains(sub_text, case=False, regex=False, na=False)
            filtered = filtered[submask]

        if contractor:
            contractor_text = str(contractor).strip()
            if "contractor" in filtered.columns:
                filtered = filtered[filtered["contractor"].fillna("").astype(str).str.contains(contractor_text, case=False, regex=False, na=False)]
            else:
                filtered = filtered.iloc[0:0]

        if backup_status:
            backup_text = str(backup_status).strip()
            if "backup_status" in filtered.columns:
                filtered = filtered[filtered["backup_status"].fillna("").astype(str).str.contains(backup_text, case=False, regex=False, na=False)]

        if battery_status:
            battery_text = str(battery_status).strip()
            if "battery_status" in filtered.columns:
                filtered = filtered[filtered["battery_status"].fillna("").astype(str).str.contains(battery_text, case=False, regex=False, na=False)]

        filtered_rows = _df_records(filtered.reset_index(drop=True))
        sanitized = _sanitize_mcp_records(filtered_rows, include_raw_json=include_raw_json)
        return _page_records(sanitized, limit=limit, offset=offset, total=len(sanitized))

    def get_site_full_context(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        if not site_raw:
            return {"error": "site_code or site_id is required"}

        site_code = str(catalog_store._normalize_site_id(site_raw) or site_raw).strip().upper()
        metadata_limit = _mcp_limit(kwargs.get("metadata_limit"), default=100)
        metadata_offset = _mcp_offset(kwargs.get("metadata_offset"))
        alarm_limit = _mcp_limit(kwargs.get("alarm_limit"), default=100)
        alarm_offset = _mcp_offset(kwargs.get("alarm_offset"))
        bdt_limit = _mcp_limit(kwargs.get("bdt_limit"), default=100)
        bdt_offset = _mcp_offset(kwargs.get("bdt_offset"))

        date_from = str(kwargs.get("date_from") or "").strip() or None
        date_to = str(kwargs.get("date_to") or "").strip() or None
        category = str(kwargs.get("category") or "").strip()
        vendor = str(kwargs.get("vendor") or "").strip()
        network_type = str(kwargs.get("network_type") or "").strip()
        include_raw_json = bool(kwargs.get("include_raw_json", False))

        try:
            network_summary = self.query_network_summary(
                site_code=site_code,
                site_id=site_code,
                include_raw_json=include_raw_json,
                limit=metadata_limit,
                offset=metadata_offset,
            )
        except Exception as exc:
            network_summary = {
                "error": _sanitize_mcp_value(str(exc)),
                "rows": [],
                "returned": 0,
                "limit": metadata_limit,
                "offset": metadata_offset,
                "has_more": False,
                "total": 0,
            }

        if isinstance(network_summary, dict) and isinstance(network_summary.get("rows"), list):
            network_summary["rows"] = _sanitize_mcp_records(
                network_summary.get("rows", []),
                include_raw_json=include_raw_json,
            )
        if isinstance(network_summary, dict) and network_summary.get("error") is not None:
            network_summary["error"] = _sanitize_mcp_value(network_summary["error"])

        try:
            alarm_stats = self.alarm_stats(
                site_id=site_code,
                site_code=site_code,
                category=category,
                vendor=vendor,
                network_type=network_type,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as exc:
            alarm_stats = {"error": _sanitize_mcp_value(str(exc))}

        try:
            alarm_rows = self.query_alarm_events(
                site_code=site_code,
                site_id=site_code,
                category=category,
                vendor=vendor,
                network_type=network_type,
                date_from=date_from,
                date_to=date_to,
                limit=alarm_limit,
                offset=alarm_offset,
            )
        except Exception as exc:
            alarm_rows = {
                "error": _sanitize_mcp_value(str(exc)),
                "rows": [],
                "returned": 0,
                "limit": alarm_limit,
                "offset": alarm_offset,
                "has_more": False,
                "total": 0,
            }

        if isinstance(alarm_rows, dict) and isinstance(alarm_rows.get("rows"), list):
            alarm_rows["rows"] = _sanitize_mcp_records(
                alarm_rows.get("rows", []),
                include_raw_json=include_raw_json,
            )
        if isinstance(alarm_rows, dict) and alarm_rows.get("error") is not None:
            alarm_rows["error"] = _sanitize_mcp_value(alarm_rows["error"])

        reporting_period = str(kwargs.get("reporting_period") or kwargs.get("period") or "").strip() or None
        week = str(kwargs.get("week") or "").strip() or None
        overall = str(kwargs.get("overall") or "").strip()
        rule_id = str(kwargs.get("rule_id") or "").strip().upper()
        rule_verdict = str(kwargs.get("rule_verdict") or "").strip()

        try:
            bdt_payload = self.query_bdt_full(
                site_code=site_code,
                site_id=site_code,
                reporting_period=reporting_period,
                week=week,
                date_from=date_from,
                date_to=date_to,
                overall=overall,
                rule_id=rule_id,
                rule_verdict=rule_verdict,
                include_raw_json=include_raw_json,
                limit=bdt_limit,
                offset=bdt_offset,
            )
        except Exception as exc:
            bdt_payload = {
                "error": _sanitize_mcp_value(str(exc)),
                "bdt_summary": {"rows": [], "returned": 0, "limit": bdt_limit, "offset": bdt_offset, "has_more": False, "total": 0},
                "validation_runs": {"rows": [], "returned": 0, "limit": bdt_limit, "offset": bdt_offset, "has_more": False, "total": 0},
                "bdt_tests": {"rows": [], "returned": 0, "limit": bdt_limit, "offset": bdt_offset, "has_more": False, "total": 0},
                "rule_results": {"rows": [], "returned": 0, "limit": bdt_limit, "offset": bdt_offset, "has_more": False, "total": 0},
                "photos": {"rows": [], "returned": 0, "limit": bdt_limit, "offset": bdt_offset, "has_more": False, "total": 0},
                "review_events": {"rows": [], "returned": 0, "limit": bdt_limit, "offset": bdt_offset, "has_more": False, "total": 0},
            }

        for section_name in ("bdt_summary", "validation_runs", "bdt_tests", "rule_results", "photos", "review_events"):
            section = bdt_payload.get(section_name)
            if isinstance(section, dict) and isinstance(section.get("rows"), list):
                section["rows"] = _sanitize_mcp_records(
                    section.get("rows", []),
                    include_raw_json=include_raw_json,
                )
                bdt_payload[section_name] = section
            elif isinstance(section, dict) and section.get("error") is not None:
                section["error"] = _sanitize_mcp_value(section["error"])

        if isinstance(bdt_payload, dict) and bdt_payload.get("error") is not None:
            bdt_payload["error"] = _sanitize_mcp_value(bdt_payload["error"])

        source_errors: list[str] = []
        if isinstance(network_summary, dict) and network_summary.get("error") is not None:
            source_errors.append(str(network_summary["error"]))
        if isinstance(alarm_rows, dict) and alarm_rows.get("error") is not None:
            source_errors.append(str(alarm_rows["error"]))
        if isinstance(bdt_payload, dict) and bdt_payload.get("error") is not None:
            source_errors.append(str(bdt_payload["error"]))

        return {
            "site_id": site_code,
            "site_code": site_code,
            "network_summary": _jsonable(network_summary),
            "alarm_stats": _jsonable(alarm_stats),
            "alarm_rows": _jsonable(alarm_rows),
            "bdt_summary": _jsonable(bdt_payload.get("bdt_summary", {})),
            "validation_runs": _jsonable(bdt_payload.get("validation_runs", {})),
            "bdt_tests": _jsonable(bdt_payload.get("bdt_tests", {})),
            "rule_results": _jsonable(bdt_payload.get("rule_results", {})),
            "photos": _jsonable(bdt_payload.get("photos", {})),
            "review_events": _jsonable(bdt_payload.get("review_events", {})),
            "bdt_error": _sanitize_mcp_value(bdt_payload.get("error")) if isinstance(bdt_payload, dict) else None,
            "error": " | ".join(source_errors) if source_errors else None,
        }

    def get_sites_context_report(self, **kwargs) -> dict[str, Any]:
        def _sheet_alias(name: str) -> str:
            normalized = str(name).strip().lower()
            return {
                "sites": "Sites",
                "network_summary": "Network Summary",
                "network summary": "Network Summary",
                "networksummary": "Network Summary",
                "alarm_stats": "Alarm Stats",
                "alarm stats": "Alarm Stats",
                "alarmstats": "Alarm Stats",
                "alarms": "Alarms",
                "bdt_summary": "BDT Summary",
                "bdt summary": "BDT Summary",
                "bdtsummary": "BDT Summary",
                "bdt_tests": "BDT Tests",
                "bdt tests": "BDT Tests",
                "bdttests": "BDT Tests",
                "bdt_runs": "BDT Runs",
                "bdt runs": "BDT Runs",
                "bdtruns": "BDT Runs",
                "bdt_rules": "BDT Rules",
                "bdt rules": "BDT Rules",
                "bdtrules": "BDT Rules",
                "photo_metadata": "Photo Metadata",
                "photo metadata": "Photo Metadata",
                "photometadata": "Photo Metadata",
                "review_events": "Review Events",
                "review events": "Review Events",
                "reviewevents": "Review Events",
            }.get(normalized, "")

        limit = _mcp_limit(kwargs.get("limit"))
        offset = _mcp_offset(kwargs.get("offset"))
        include_raw_json = bool(kwargs.get("include_raw_json", False))

        sheet_input = str(kwargs.get("sheet") or "").strip()
        sheet = _sheet_alias(sheet_input)

        if sheet_input and not sheet:
            return {
                "sheet": sheet_input,
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
                "error": f"unknown sheet '{sheet_input}'",
                "error_sheet": sheet_input,
            }

        site_text = str(
            kwargs.get("site_text") or kwargs.get("site_code") or kwargs.get("site_id") or ""
        ).strip()
        area = str(kwargs.get("area") or "").strip()
        contractor = str(kwargs.get("contractor") or "").strip()
        subcontractor = str(kwargs.get("subcontractor") or "").strip()
        backup_status = str(kwargs.get("backup_status") or "").strip()
        battery_status = str(kwargs.get("battery_status") or "").strip()
        has_metadata = kwargs.get("has_metadata")
        has_alarms = kwargs.get("has_alarms")
        has_bdt_summary = kwargs.get("has_bdt_summary")
        has_bdt_validation = kwargs.get("has_bdt_validation")
        has_bdt = kwargs.get("has_bdt")

        site_kwargs = {
            "site_text": site_text,
            "site_code": str(kwargs.get("site_code") or "").strip(),
            "site_id": str(kwargs.get("site_id") or "").strip(),
            "area": area,
            "contractor": contractor,
            "subcontractor": subcontractor,
            "backup_status": backup_status,
            "battery_status": battery_status,
            "has_metadata": has_metadata,
            "has_alarms": has_alarms,
            "has_bdt_summary": has_bdt_summary,
            "has_bdt_validation": has_bdt_validation,
            "has_bdt": has_bdt,
        }

        alarm_kwargs = {
            "site_text": site_text,
            "site_code": str(kwargs.get("site_code") or "").strip(),
            "site_id": str(kwargs.get("site_id") or "").strip(),
            "category": str(kwargs.get("category") or "").strip(),
            "vendor": str(kwargs.get("vendor") or "").strip(),
            "network_type": str(kwargs.get("network_type") or "").strip(),
            "date_from": str(kwargs.get("date_from") or "").strip() or None,
            "date_to": str(kwargs.get("date_to") or "").strip() or None,
            "include_raw_json": include_raw_json,
            "limit": limit,
            "offset": offset,
        }

        network_kwargs = dict(alarm_kwargs)
        network_kwargs["include_raw_json"] = include_raw_json
        network_kwargs["limit"] = limit
        network_kwargs["offset"] = offset
        network_kwargs.update({
            "site_text": site_text,
            "site_code": str(kwargs.get("site_code") or "").strip(),
            "site_id": str(kwargs.get("site_id") or "").strip(),
            "area": area,
            "subcontractor": subcontractor,
            "contractor": contractor,
            "backup_status": backup_status,
            "battery_status": battery_status,
        })

        bdt_kwargs = {
            "site_code": str(kwargs.get("site_code") or kwargs.get("site_id") or site_text or "").strip(),
            "site_id": str(kwargs.get("site_id") or kwargs.get("site_code") or site_text or "").strip(),
            "site_text": site_text,
            "reporting_period": str(kwargs.get("reporting_period") or kwargs.get("period") or "").strip() or None,
            "period": str(kwargs.get("period") or "").strip() or None,
            "week": str(kwargs.get("week") or "").strip() or None,
            "date_from": str(kwargs.get("date_from") or "").strip() or None,
            "date_to": str(kwargs.get("date_to") or "").strip() or None,
            "overall": str(kwargs.get("overall") or "").strip(),
            "rule_id": str(kwargs.get("rule_id") or "").strip().upper(),
            "rule_verdict": str(kwargs.get("rule_verdict") or "").strip(),
            "include_raw_json": include_raw_json,
            "limit": limit,
            "offset": offset,
        }

        def _total_from_payload(payload: Any) -> int:
            if not isinstance(payload, dict):
                return 0
            value = payload.get("total")
            if isinstance(value, int):
                return value
            return len(payload.get("rows", [])) if isinstance(payload.get("rows"), list) else 0

        def _sheet_page(payload: Any, sheet_name: str, *, fallback_error: str | None = None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {
                    "sheet": sheet_name,
                    "rows": [],
                    "returned": 0,
                    "limit": limit,
                    "offset": offset,
                    "has_more": False,
                    "total": 0,
                }

            rows = payload.get("rows")
            if not isinstance(rows, list):
                rows = []
                payload_returned = 0
                payload_limit = limit
                payload_offset = offset
                payload_has_more = False
                payload_total = 0
            else:
                payload_returned = payload.get("returned")
                payload_limit = payload.get("limit")
                payload_offset = payload.get("offset")
                payload_has_more = payload.get("has_more")
                payload_total = payload.get("total")

            if not isinstance(payload_returned, int):
                payload_returned = len(rows)
            if not isinstance(payload_limit, int):
                payload_limit = limit
            if not isinstance(payload_offset, int):
                payload_offset = offset
            if not isinstance(payload_has_more, bool):
                payload_has_more = False
            if not isinstance(payload_total, int):
                payload_total = len(rows)

            response = {
                "sheet": sheet_name,
                "rows": rows,
                "returned": payload_returned,
                "limit": payload_limit,
                "offset": payload_offset,
                "has_more": payload_has_more,
                "total": payload_total,
            }
            if isinstance(payload.get("error"), str):
                response["error"] = _sanitize_mcp_value(payload.get("error"))
            elif isinstance(fallback_error, str):
                response["error"] = _sanitize_mcp_value(fallback_error)
            return response

        if sheet:
            try:
                if sheet == "Sites":
                    manifest_site_kwargs = dict(site_kwargs)
                    manifest_site_kwargs.update({"limit": limit, "offset": offset})
                    payload = self.list_sites(**manifest_site_kwargs)
                    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
                        return _jsonable(_sheet_page(payload, sheet))
                    return {"sheet": sheet, "rows": [], "returned": 0, "limit": limit, "offset": offset, "has_more": False, "total": 0}

                if sheet == "Network Summary":
                    payload = self.query_network_summary(**network_kwargs)
                    return _jsonable(_sheet_page(payload, sheet))

                if sheet == "Alarm Stats":
                    payload = self.list_sites(**{
                        **site_kwargs,
                        "limit": limit,
                        "offset": offset,
                    })
                    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
                        return _jsonable(_sheet_page(payload, sheet))
                    return {"sheet": sheet, "rows": [], "returned": 0, "limit": limit, "offset": offset, "has_more": False, "total": 0}

                if sheet == "Alarms":
                    payload = self.query_alarm_events(**alarm_kwargs)
                    return _jsonable(_sheet_page(payload, sheet))

                if sheet == "BDT Summary":
                    payload = self.query_bdt_full(**bdt_kwargs)
                    section = payload.get("bdt_summary") if isinstance(payload, dict) else None
                    return _jsonable(_sheet_page(
                        section if isinstance(section, dict) else {},
                        sheet,
                        fallback_error=payload.get("error") if isinstance(payload, dict) else None,
                    ))

                if sheet == "BDT Tests":
                    payload = self.query_bdt_full(**bdt_kwargs)
                    section = payload.get("bdt_tests") if isinstance(payload, dict) else None
                    return _jsonable(_sheet_page(
                        section if isinstance(section, dict) else {},
                        sheet,
                        fallback_error=payload.get("error") if isinstance(payload, dict) else None,
                    ))

                if sheet == "BDT Runs":
                    payload = self.query_bdt_full(**bdt_kwargs)
                    section = payload.get("validation_runs") if isinstance(payload, dict) else None
                    return _jsonable(_sheet_page(
                        section if isinstance(section, dict) else {},
                        sheet,
                        fallback_error=payload.get("error") if isinstance(payload, dict) else None,
                    ))

                if sheet == "BDT Rules":
                    payload = self.query_bdt_full(**bdt_kwargs)
                    section = payload.get("rule_results") if isinstance(payload, dict) else None
                    return _jsonable(_sheet_page(
                        section if isinstance(section, dict) else {},
                        sheet,
                        fallback_error=payload.get("error") if isinstance(payload, dict) else None,
                    ))

                if sheet == "Photo Metadata":
                    payload = self.query_bdt_full(**bdt_kwargs)
                    section = payload.get("photos") if isinstance(payload, dict) else None
                    return _jsonable(_sheet_page(
                        section if isinstance(section, dict) else {},
                        sheet,
                        fallback_error=payload.get("error") if isinstance(payload, dict) else None,
                    ))

                if sheet == "Review Events":
                    payload = self.query_bdt_full(**bdt_kwargs)
                    section = payload.get("review_events") if isinstance(payload, dict) else None
                    return _jsonable(_sheet_page(
                        section if isinstance(section, dict) else {},
                        sheet,
                        fallback_error=payload.get("error") if isinstance(payload, dict) else None,
                    ))
            except Exception as exc:
                return {
                    "sheet": sheet,
                    "rows": [],
                    "returned": 0,
                    "limit": limit,
                    "offset": offset,
                    "has_more": False,
                    "total": 0,
                    "error": _sanitize_mcp_value(str(exc)),
                }

            return {
                "sheet": sheet,
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
                "error": f"unknown sheet '{sheet_input}'",
                "error_sheet": sheet_input,
            }

        try:
            sites_payload = self.list_sites(**{**site_kwargs, "limit": 0, "offset": 0})
            sites_total = _total_from_payload(sites_payload)
            network_payload = self.query_network_summary(**{**network_kwargs, "limit": 0, "offset": 0})
            network_total = _total_from_payload(network_payload)
            alarm_payload = self.query_alarm_events(**{**alarm_kwargs, "limit": 0, "offset": 0})
            alarm_total = _total_from_payload(alarm_payload)
            bdt_payload = self.query_bdt_full(**{**bdt_kwargs, "limit": 0, "offset": 0})
            if not isinstance(bdt_payload, dict):
                bdt_payload = {}
            bdt_summary_total = _total_from_payload(bdt_payload.get("bdt_summary", {}))
            bdt_tests_total = _total_from_payload(bdt_payload.get("bdt_tests", {}))
            bdt_runs_total = _total_from_payload(bdt_payload.get("validation_runs", {}))
            bdt_rules_total = _total_from_payload(bdt_payload.get("rule_results", {}))
            photo_total = _total_from_payload(bdt_payload.get("photos", {}))
            review_total = _total_from_payload(bdt_payload.get("review_events", {}))
            alarm_stats_total = sites_total
            if isinstance(sites_payload, dict):
                sites_rows = sites_payload.get("rows", []) if isinstance(sites_payload.get("rows"), list) else []
                alarm_stats_total = sum(1 for row in sites_rows if isinstance(row, dict))
                if not sites_rows and isinstance(sites_payload.get("total"), int):
                    alarm_stats_total = sites_payload["total"]
        except Exception as exc:
            return {
                "sheets": [],
                "sheet": None,
                "rows": [],
                "returned": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "total": 0,
                "error": _sanitize_mcp_value(str(exc)),
            }

        return {
            "sheets": [
                {"name": "Sites", "total": _jsonable(sites_total), "available": sites_total > 0},
                {"name": "Network Summary", "total": _jsonable(network_total), "available": network_total > 0},
                {"name": "Alarm Stats", "total": _jsonable(alarm_stats_total), "available": alarm_stats_total > 0},
                {"name": "Alarms", "total": _jsonable(alarm_total), "available": alarm_total > 0},
                {"name": "BDT Summary", "total": _jsonable(bdt_summary_total), "available": bdt_summary_total > 0},
                {"name": "BDT Tests", "total": _jsonable(bdt_tests_total), "available": bdt_tests_total > 0},
                {"name": "BDT Runs", "total": _jsonable(bdt_runs_total), "available": bdt_runs_total > 0},
                {"name": "BDT Rules", "total": _jsonable(bdt_rules_total), "available": bdt_rules_total > 0},
                {"name": "Photo Metadata", "total": _jsonable(photo_total), "available": photo_total > 0},
                {"name": "Review Events", "total": _jsonable(review_total), "available": review_total > 0},
            ],
            "returned": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "total": 0,
            "sheet": None,
        }

    def get_site_alarm_context(self, **kwargs) -> dict[str, Any]:
        site_raw = str(kwargs.get("site_code") or kwargs.get("site_id") or "").strip()
        if not site_raw:
            return {"error": "site_code or site_id is required"}
        site_code = normalize_site_key(site_raw)
        date_from = str(kwargs.get("date_from") or "").strip() or None
        date_to = str(kwargs.get("date_to") or "").strip() or None
        limit = _limit(kwargs.get("limit"), default=100)

        stats = self.alarm_stats(site_text=site_code, date_from=date_from, date_to=date_to)
        alarms = self.query_alarms(site_text=site_code, date_from=date_from, date_to=date_to, limit=limit)

        return {
            "site_code": site_code,
            "alarm_stats": stats,
            "alarm_rows": alarms.get("rows", []) if isinstance(alarms, dict) else [],
            "alarm_total": alarms.get("row_count", 0) if isinstance(alarms, dict) else 0,
        }
