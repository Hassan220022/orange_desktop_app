"""DuckDB-backed alarm access and query layer."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from contextlib import contextmanager
from threading import RLock
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
    from alarm_app.core.duration import duration_to_secs, secs_to_hhmmss
except ImportError:
    from core.classify import classify_by_alarm_id, compute_site_down_flag
    from core.duration import duration_to_secs, secs_to_hhmmss

STATE_DIR = Path.home() / ".alarm_viewer"
ALARM_DB_FILE = STATE_DIR / "alarms.duckdb"
ALARM_TABLE = "alarm_records"
_log = logging.getLogger(__name__)
_LOCK_WARNING_EMITTED = False
_ALARM_STORE_LOCK = RLock()


@contextmanager
def _alarm_store_read_lock():
    with _ALARM_STORE_LOCK:
        yield


@contextmanager
def _alarm_store_write_lock():
    with _ALARM_STORE_LOCK:
        yield

_COLUMN_WHITELIST = {
    "site_id",
    "alarm_name",
    "alarm_id",
    "network_type",
    "vendor",
    "occurred_on",
    "cleared_on",
    "duration",
    "_duration_secs",
    "clearance_status",
    "alarm_source",
    "site_down_flag",
    "alarm_category",
    "file_source",
}
_SORTABLE_COLUMNS = {
    "site_id",
    "alarm_name",
    "alarm_id",
    "network_type",
    "vendor",
    "occurred_on",
    "cleared_on",
    "duration",
    "_duration_secs",
    "clearance_status",
    "alarm_source",
    "site_down_flag",
    "alarm_category",
    "file_source",
}
_TEXT_COLUMN_FILTERS = {
    "site_id",
    "alarm_name",
    "alarm_id",
    "network_type",
    "vendor",
    "duration",
    "clearance_status",
    "alarm_source",
    "site_down_flag",
    "alarm_category",
    "file_source",
}


@dataclass(slots=True)
class AlarmQuery:
    site_text: str = ""
    category: str = "All"
    vendor: str = "All"
    network_type: str = "All"
    min_duration_secs: float | None = None
    date_from: date | datetime | None = None
    date_to: date | datetime | None = None
    manual_days: Iterable[date | datetime | pd.Timestamp | str] | None = None
    both_pd: bool = False
    sort_by: str | None = None
    sort_desc: bool = False
    limit: int | None = None
    offset: int = 0
    site_scope_keys: Iterable[str] | None = None
    allowed_values: dict[str, Iterable[Any] | None] = field(default_factory=dict)
    column_filters: dict[str, Iterable[Any] | None] = field(default_factory=dict)
    col_filters: dict[str, Iterable[Any] | None] = field(default_factory=dict)


def set_alarm_db_file(path: Path) -> None:
    global ALARM_DB_FILE
    ALARM_DB_FILE = Path(path)


def _connect(*, read_only: bool = False):
    import duckdb

    if not read_only:
        ALARM_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(ALARM_DB_FILE), read_only=read_only)


def _safe_connect(*, read_only: bool = False):
    global _LOCK_WARNING_EMITTED
    try:
        con = _connect(read_only=read_only)
        _LOCK_WARNING_EMITTED = False
        return con
    except Exception as exc:
        mode = "read-only" if read_only else "read-write"
        if not _LOCK_WARNING_EMITTED:
            _log.warning(
                "Alarm store connection failed (%s): %s (%s)",
                mode,
                ALARM_DB_FILE,
                exc,
            )
            _LOCK_WARNING_EMITTED = True
        return None


def _table_exists(con) -> bool:
    count = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [ALARM_TABLE],
    ).fetchone()[0]
    return bool(count)


def _table_columns(con) -> set[str]:
    if not _table_exists(con):
        return set()
    rows = con.execute(f"PRAGMA table_info('{ALARM_TABLE}')").fetchall()
    return {str(row[1]) for row in rows}


def _normalize_site_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_manual_days(values: Iterable[date | datetime | pd.Timestamp | str] | None) -> list[date]:
    out: list[date] = []
    seen: set[date] = set()
    for value in values or []:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            continue
        day = pd.Timestamp(parsed).date()
        if day not in seen:
            out.append(day)
            seen.add(day)
    return out


def _range_start(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _range_end_exclusive(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None
    return (ts.normalize() + pd.Timedelta(days=1)).to_pydatetime()


def _load_alarm_ids() -> dict[str, list[str]]:
    try:
        try:
            from alarm_app.data import state as _state
        except ImportError:
            from data import state as _state
    except ImportError:
        _state = None
    if _state is None:
        return {"power": [], "down": [], "door": []}
    try:
        data = _state.load_alarm_ids()
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "power": [str(v).strip() for v in data.get("power", [])],
        "down": [str(v).strip() for v in data.get("down", [])],
        "door": [str(v).strip() for v in data.get("door", [])],
    }


def _ensure_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        for col in ("alarm_category", "site_down_flag", "duration", "_duration_secs"):
            if col not in out.columns:
                out[col] = pd.Series(dtype="object")
        return out

    for col in ("occurred_on", "cleared_on"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce", format="mixed")

    if "duration" not in out.columns:
        out["duration"] = ""

    if {"occurred_on", "cleared_on", "duration"}.issubset(out.columns):
        missing_duration = out["duration"].fillna("").astype(str).str.strip().eq("")
        has_times = missing_duration & out["occurred_on"].notna() & out["cleared_on"].notna()
        if has_times.any():
            delta_secs = (out.loc[has_times, "cleared_on"] - out.loc[has_times, "occurred_on"]).dt.total_seconds()
            out.loc[has_times, "duration"] = delta_secs.apply(secs_to_hhmmss)

    out["_duration_secs"] = out["duration"].apply(duration_to_secs).astype(float)
    out["duration"] = out["_duration_secs"].apply(secs_to_hhmmss)

    if "alarm_category" not in out.columns:
        out["alarm_category"] = ""
    out = classify_by_alarm_id(out, _load_alarm_ids())
    out["alarm_category"] = out["alarm_category"].fillna("").astype(str)
    out = compute_site_down_flag(out)
    if "site_down_flag" not in out.columns:
        out["site_down_flag"] = "No"
    out["site_down_flag"] = out["site_down_flag"].fillna("No").astype(str)
    return out


def replace_alarm_table(df: pd.DataFrame) -> None:
    with _alarm_store_write_lock():
        prepared = _ensure_derived_fields(df if df is not None else pd.DataFrame())
        con = _connect(read_only=False)
        try:
            con.execute(f"DROP TABLE IF EXISTS {ALARM_TABLE}")
            con.register("prepared_df", prepared)
            con.execute(f"CREATE TABLE {ALARM_TABLE} AS SELECT * FROM prepared_df")
            con.unregister("prepared_df")
        finally:
            con.close()


def _build_where_clause(q: AlarmQuery, table_cols: set[str]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if q.site_scope_keys and "site_id" in table_cols:
        keys = [_normalize_site_key(v) for v in q.site_scope_keys]
        keys = [v for v in keys if v]
        if keys:
            placeholders = ", ".join(["?"] * len(keys))
            clauses.append(
                "regexp_replace(upper(COALESCE(CAST(site_id AS VARCHAR), '')), '[^A-Z0-9]', '', 'g') "
                f"IN ({placeholders})"
            )
            params.extend(keys)

    if q.site_text:
        terms = [t.strip().upper() for t in str(q.site_text).split(",") if t.strip()]
        if terms:
            term_clauses: list[str] = []
            for term in terms:
                like = f"%{term}%"
                if "site_id" in table_cols:
                    term_clauses.append("upper(COALESCE(CAST(site_id AS VARCHAR), '')) LIKE ?")
                    params.append(like)
                if "alarm_source" in table_cols:
                    term_clauses.append("upper(COALESCE(CAST(alarm_source AS VARCHAR), '')) LIKE ?")
                    params.append(like)
            if term_clauses:
                clauses.append("(" + " OR ".join(term_clauses) + ")")

    if "occurred_on" in table_cols:
        range_parts: list[str] = []
        range_start = _range_start(q.date_from)
        range_end = _range_end_exclusive(q.date_to)
        if range_start is not None:
            range_parts.append("occurred_on >= ?")
            params.append(range_start)
        if range_end is not None:
            range_parts.append("occurred_on < ?")
            params.append(range_end)
        range_clause = "(" + " AND ".join(range_parts) + ")" if range_parts else ""

        days = _normalize_manual_days(q.manual_days)
        day_clause = ""
        if days:
            placeholders = ", ".join(["?"] * len(days))
            day_clause = f"CAST(occurred_on AS DATE) IN ({placeholders})"
            params.extend(days)

        if range_clause and day_clause:
            clauses.append(f"({range_clause} OR {day_clause})")
        elif range_clause:
            clauses.append(range_clause)
        elif day_clause:
            clauses.append(day_clause)

    if q.category and q.category != "All" and "alarm_category" in table_cols:
        clauses.append("COALESCE(CAST(alarm_category AS VARCHAR), '') = ?")
        params.append(str(q.category))

    if q.network_type and q.network_type != "All" and "network_type" in table_cols:
        clauses.append("COALESCE(CAST(network_type AS VARCHAR), '') = ?")
        params.append(str(q.network_type))

    if q.vendor and q.vendor != "All" and "vendor" in table_cols:
        clauses.append("upper(COALESCE(CAST(vendor AS VARCHAR), '')) = ?")
        params.append(str(q.vendor).upper())

    if q.min_duration_secs is not None and "_duration_secs" in table_cols:
        clauses.append("COALESCE(_duration_secs, 0) >= ?")
        params.append(float(q.min_duration_secs))

    merged_column_filters: dict[str, Iterable[Any] | None] = {}
    merged_column_filters.update(q.allowed_values or {})
    merged_column_filters.update(q.column_filters or {})
    merged_column_filters.update(q.col_filters or {})

    for col, raw_allowed in merged_column_filters.items():
        if raw_allowed is None:
            continue
        if col not in _TEXT_COLUMN_FILTERS or col not in table_cols:
            continue
        allowed = [str(v) for v in raw_allowed]
        if not allowed:
            clauses.append("1 = 0")
            continue
        placeholders = ", ".join(["?"] * len(allowed))
        clauses.append(f"COALESCE(CAST({col} AS VARCHAR), '') IN ({placeholders})")
        params.extend(allowed)

    if q.both_pd and {"site_id", "alarm_category"}.issubset(table_cols):
        clauses.append(
            f"""
            site_id IN (
                SELECT site_id
                FROM {ALARM_TABLE}
                WHERE site_id IS NOT NULL
                GROUP BY site_id
                HAVING
                    SUM(CASE WHEN alarm_category = 'Power' THEN 1 ELSE 0 END) > 0
                    AND
                    SUM(CASE WHEN alarm_category = 'Down' THEN 1 ELSE 0 END) > 0
            )
            """
        )

    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def query_alarms(q: AlarmQuery) -> pd.DataFrame:
    with _alarm_store_read_lock():
        if not ALARM_DB_FILE.exists():
            return pd.DataFrame()
        con = _safe_connect(read_only=True)
        if con is None:
            return pd.DataFrame()
        try:
            table_cols = _table_columns(con)
            if not table_cols:
                return pd.DataFrame()
            where_sql, params = _build_where_clause(q, table_cols)
            sql = f"SELECT * FROM {ALARM_TABLE}{where_sql}"

            sort_by = q.sort_by if q.sort_by in _SORTABLE_COLUMNS and q.sort_by in table_cols else None
            if sort_by:
                direction = "DESC" if q.sort_desc else "ASC"
                sql += f" ORDER BY {sort_by} {direction} NULLS LAST"

            if q.limit is not None:
                limit = max(int(q.limit), 0)
                sql += " LIMIT ?"
                params.append(limit)
            if q.offset:
                offset = max(int(q.offset), 0)
                sql += " OFFSET ?"
                params.append(offset)

            return con.execute(sql, params).fetchdf()
        finally:
            con.close()


def count_alarms(q: AlarmQuery) -> int:
    with _alarm_store_read_lock():
        if not ALARM_DB_FILE.exists():
            return 0
        con = _safe_connect(read_only=True)
        if con is None:
            return 0
        try:
            table_cols = _table_columns(con)
            if not table_cols:
                return 0
            where_sql, params = _build_where_clause(q, table_cols)
            row = con.execute(f"SELECT COUNT(*) FROM {ALARM_TABLE}{where_sql}", params).fetchone()
            return int(row[0] if row else 0)
        finally:
            con.close()


def distinct_values(column: str, q: AlarmQuery | None = None) -> list[str]:
    with _alarm_store_read_lock():
        if column not in _COLUMN_WHITELIST:
            raise ValueError(f"Unsupported column: {column}")
        if not ALARM_DB_FILE.exists():
            return []
        con = _safe_connect(read_only=True)
        if con is None:
            return []
        try:
            table_cols = _table_columns(con)
            if column not in table_cols:
                return []
            normalized_q = replace(q, sort_by=None, limit=None, offset=0) if q else AlarmQuery()
            where_sql, params = _build_where_clause(normalized_q, table_cols)
            sql = (
                f"SELECT DISTINCT COALESCE(CAST({column} AS VARCHAR), '') AS value "
                f"FROM {ALARM_TABLE}{where_sql} ORDER BY value ASC"
            )
            rows = con.execute(sql, params).fetchall()
            return [str(row[0]) for row in rows]
        finally:
            con.close()


def stats(q: AlarmQuery | None = None) -> dict[str, int | float]:
    with _alarm_store_read_lock():
        empty_stats = {
            "total": 0,
            "power": 0,
            "down": 0,
            "door": 0,
            "temp": 0,
            "sites": 0,
            "avg_duration_secs": 0.0,
        }
        if not ALARM_DB_FILE.exists():
            return empty_stats
        con = _safe_connect(read_only=True)
        if con is None:
            return empty_stats
        try:
            table_cols = _table_columns(con)
            if not table_cols:
                return empty_stats
            normalized_q = replace(q, sort_by=None, limit=None, offset=0) if q else AlarmQuery()
            where_sql, params = _build_where_clause(normalized_q, table_cols)
            row = con.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN alarm_category = 'Power' THEN 1 ELSE 0 END) AS power,
                    SUM(CASE WHEN alarm_category = 'Down' THEN 1 ELSE 0 END) AS down,
                    SUM(CASE WHEN alarm_category = 'Door' THEN 1 ELSE 0 END) AS door,
                    SUM(CASE WHEN alarm_category = 'Temp' THEN 1 ELSE 0 END) AS temp,
                    COUNT(DISTINCT site_id) AS sites,
                    COALESCE(AVG(_duration_secs), 0) AS avg_duration_secs
                FROM {ALARM_TABLE}{where_sql}
                """,
                params,
            ).fetchone()
            return {
                "total": int(row[0] or 0),
                "power": int(row[1] or 0),
                "down": int(row[2] or 0),
                "door": int(row[3] or 0),
                "temp": int(row[4] or 0),
                "sites": int(row[5] or 0),
                "avg_duration_secs": float(row[6] or 0.0),
            }
        finally:
            con.close()


def load_alarm_slice_for_bdt(
    site_codes: list[str],
    date_from: datetime | None,
    date_to: datetime | None,
) -> pd.DataFrame:
    query = AlarmQuery(
        site_scope_keys=site_codes or None,
        date_from=date_from,
        date_to=date_to,
        sort_by="occurred_on",
        sort_desc=False,
    )
    return query_alarms(query)


def load_all_alarms() -> pd.DataFrame:
    with _alarm_store_read_lock():
        if not ALARM_DB_FILE.exists():
            return pd.DataFrame()
        con = _safe_connect(read_only=True)
        if con is None:
            return pd.DataFrame()
        try:
            if not _table_exists(con):
                return pd.DataFrame()
            return con.execute(f"SELECT * FROM {ALARM_TABLE}").fetchdf()
        finally:
            con.close()


def occurred_on_bounds() -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    with _alarm_store_read_lock():
        if not ALARM_DB_FILE.exists():
            return None, None
        con = _safe_connect(read_only=True)
        if con is None:
            return None, None
        try:
            table_cols = _table_columns(con)
            if "occurred_on" not in table_cols:
                return None, None
            row = con.execute(
                f"SELECT MIN(occurred_on), MAX(occurred_on) FROM {ALARM_TABLE}"
            ).fetchone()
            if not row:
                return None, None
            min_ts = pd.to_datetime(row[0], errors="coerce", format="mixed")
            max_ts = pd.to_datetime(row[1], errors="coerce", format="mixed")
            return (
                None if pd.isna(min_ts) else pd.Timestamp(min_ts),
                None if pd.isna(max_ts) else pd.Timestamp(max_ts),
            )
        finally:
            con.close()
