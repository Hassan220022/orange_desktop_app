"""DuckDB-backed catalog access layer for Site Metadata and BDT Summary."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from alarm_app.db.repos import catalog_repo
except ImportError:
    from db.repos import catalog_repo

_log = logging.getLogger(__name__)

STATE_DIR = Path.home() / ".alarm_viewer"
CATALOG_DB_FILE = STATE_DIR / "catalog.duckdb"
SITE_META_TABLE = "site_metadata_catalog"
BDT_SUMMARY_TABLE = "bdt_summary_catalog"


def set_catalog_db_file(path: Path) -> None:
    global CATALOG_DB_FILE
    CATALOG_DB_FILE = Path(path)


def _connect(*, read_only: bool = False):
    import duckdb

    if not read_only:
        CATALOG_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(CATALOG_DB_FILE), read_only=read_only)


def _table_exists(con, table_name: str) -> bool:
    count = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table_name],
    ).fetchone()[0]
    return bool(count)


# ---------------------------------------------------------------------------
# Site Metadata Catalog
# ---------------------------------------------------------------------------


def _normalize_site_id(value: Any) -> str:
    """Normalize a site identifier: uppercase, alphanumeric only."""
    if value is None:
        return ""
    text = str(value).strip().upper()
    if not text:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _site_metadata_value_to_text(value: Any) -> str | None:
    """Return a DuckDB-safe text representation for arbitrary catalog cells."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return str(value.to_pydatetime())
    if isinstance(value, datetime):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _prepare_site_metadata_frame(df: pd.DataFrame | None) -> pd.DataFrame:
    """Normalize arbitrary Network Summary columns before DuckDB registration.

    Network Summary workbooks mix Excel dates, blanks, text placeholders like
    ``_``, and numeric values in the same column. DuckDB can infer TIMESTAMP
    for sparse mixed columns, then fail when it later sees ``_``. Treating the
    catalog's arbitrary source columns as text keeps imports lossless enough for
    search/query while avoiding type-inference casts.
    """
    prepared = df.copy() if df is not None else pd.DataFrame()
    if prepared.empty:
        return prepared
    prepared = prepared.apply(lambda column: column.map(_site_metadata_value_to_text))
    if "site_id" in prepared.columns:
        prepared = prepared.drop_duplicates(subset=["site_id"], keep="last").reset_index(drop=True)
    return prepared


def replace_site_metadata(df: pd.DataFrame, original_headers_map: dict[str, str] | None = None) -> int:
    """Replace the DuckDB site_metadata_catalog table with *df*.

    *df* must already contain a ``site_id`` column (normalized).
    Returns the number of rows inserted.
    """
    if original_headers_map is None:
        original_headers_map = {}
    prepared = _prepare_site_metadata_frame(df)
    row_count = len(prepared)
    con = _connect(read_only=False)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(f"DROP TABLE IF EXISTS {SITE_META_TABLE}")
        if not prepared.empty:
            con.register("prepared_df", prepared)
            con.execute(f"CREATE TABLE {SITE_META_TABLE} AS SELECT * FROM prepared_df")
            con.unregister("prepared_df")
            con.execute(f"ALTER TABLE {SITE_META_TABLE} ADD PRIMARY KEY (site_id)")
        else:
            con.execute(
                f"CREATE TABLE {SITE_META_TABLE} "
                "(site_id VARCHAR PRIMARY KEY, "
                "original_headers_json VARCHAR, raw_data_json VARCHAR)"
            )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    _log.info("DuckDB site_metadata_catalog replaced: %d rows", row_count)
    return row_count


def merge_site_metadata(df: pd.DataFrame, original_headers_map: dict[str, str] | None = None) -> int:
    """Upsert *df* rows into site_metadata_catalog by site_id.

    Existing rows with matching ``site_id`` are replaced by incoming rows.
    Existing rows whose ``site_id`` is not present in *df* are preserved.
    Returns the number of unique incoming site IDs merged.
    """
    if original_headers_map is None:
        original_headers_map = {}
    prepared = _prepare_site_metadata_frame(df)
    row_count = len(prepared)
    con = _connect(read_only=False)
    try:
        con.execute("BEGIN TRANSACTION")
        if prepared.empty:
            if not _table_exists(con, SITE_META_TABLE):
                con.execute(
                    f"CREATE TABLE {SITE_META_TABLE} "
                    "(site_id VARCHAR PRIMARY KEY, "
                    "original_headers_json VARCHAR, raw_data_json VARCHAR)"
                )
            con.execute("COMMIT")
            return 0

        if _table_exists(con, SITE_META_TABLE):
            incoming_site_ids = prepared["site_id"].fillna("").astype(str).tolist()
            placeholders = ", ".join(["?"] * len(incoming_site_ids))
            existing = con.execute(
                f"SELECT * FROM {SITE_META_TABLE} WHERE site_id NOT IN ({placeholders})",
                incoming_site_ids,
            ).fetchdf()
        else:
            existing = pd.DataFrame()

        merged = pd.concat([existing, prepared], ignore_index=True, sort=False) if not existing.empty else prepared
        con.execute(f"DROP TABLE IF EXISTS {SITE_META_TABLE}")
        con.register("merged_site_metadata_df", merged)
        con.execute(f"CREATE TABLE {SITE_META_TABLE} AS SELECT * FROM merged_site_metadata_df")
        con.unregister("merged_site_metadata_df")
        con.execute(f"ALTER TABLE {SITE_META_TABLE} ADD PRIMARY KEY (site_id)")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    _log.info("DuckDB site_metadata_catalog merged: %d rows", row_count)
    return row_count


def read_site_metadata() -> pd.DataFrame:
    """Return the full Site Metadata Catalog table, or an empty frame."""
    if not CATALOG_DB_FILE.exists():
        return pd.DataFrame()
    con = _connect(read_only=True)
    try:
        if not _table_exists(con, SITE_META_TABLE):
            return pd.DataFrame()
        return con.execute(f"SELECT * FROM {SITE_META_TABLE}").fetchdf()
    finally:
        con.close()


def query_site_metadata(site_id: str) -> pd.DataFrame:
    """Return the DuckDB row(s) matching the normalized *site_id*."""
    normalized = _normalize_site_id(site_id)
    if not normalized or not CATALOG_DB_FILE.exists():
        return pd.DataFrame()
    con = _connect(read_only=True)
    try:
        if not _table_exists(con, SITE_META_TABLE):
            return pd.DataFrame()
        return con.execute(
            f"SELECT * FROM {SITE_META_TABLE} WHERE site_id = ?", [normalized]
        ).fetchdf()
    finally:
        con.close()


def search_site_metadata(
    site_text: str | None = None,
    area: str | None = None,
    subcontractor: str | None = None,
    backup_status: str | None = None,
    limit: int | None = 100,
) -> pd.DataFrame:
    """Search Site Metadata Catalog by common normalized metadata fields."""
    if not CATALOG_DB_FILE.exists():
        return pd.DataFrame()
    con = _connect(read_only=True)
    try:
        if not _table_exists(con, SITE_META_TABLE):
            return pd.DataFrame()
        df = con.execute(f"SELECT * FROM {SITE_META_TABLE}").fetchdf()
    finally:
        con.close()
    if df.empty:
        return df
    filtered = df.copy()
    if site_text:
        needle = str(site_text).strip().upper()
        normalized = _normalize_site_id(needle)
        mask = filtered.get("site_id", pd.Series("", index=filtered.index)).fillna("").astype(str).str.upper().str.contains(normalized, na=False, regex=False)
        if "site_name" in filtered.columns:
            mask |= filtered["site_name"].fillna("").astype(str).str.upper().str.contains(needle, na=False, regex=False)
        filtered = filtered[mask]
    for columns, value in (
        (("area", "orange_area"), area),
        (("subcontractor", "contractor"), subcontractor),
        (("backup_status", "battery_status"), backup_status),
    ):
        if value:
            mask = pd.Series(False, index=filtered.index)
            for column in columns:
                if column in filtered.columns:
                    mask |= filtered[column].fillna("").astype(str).str.contains(str(value), case=False, na=False, regex=False)
            filtered = filtered[mask]
    if limit is not None:
        filtered = filtered.head(max(0, int(limit)))
    return filtered.reset_index(drop=True)


# ---------------------------------------------------------------------------
# BDT Summary Catalog
# ---------------------------------------------------------------------------


def _ensure_bdt_table(con) -> None:
    if not _table_exists(con, BDT_SUMMARY_TABLE):
        con.execute(
            f"""
            CREATE TABLE {BDT_SUMMARY_TABLE} (
                site_id VARCHAR,
                reporting_period VARCHAR,
                week VARCHAR,
                test_date DATE,
                test_year INTEGER,
                content_hash VARCHAR,
                original_headers_json VARCHAR,
                raw_data_json VARCHAR
            )
            """
        )


def merge_bdt_summary(
    df: pd.DataFrame,
    reporting_periods: list[str],
) -> int:
    """Merge *df* rows into DuckDB by reporting period.

    Rows belonging to *reporting_periods* are deleted first so the table
    matches the import.  Periods not in the list are left untouched.
    Returns the number of rows inserted.
    """
    prepared = df.copy() if df is not None else pd.DataFrame()
    dedup_cols = ["site_id", "reporting_period", "content_hash"]
    if all(column in prepared.columns for column in dedup_cols):
        prepared = prepared.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    con = _connect(read_only=False)
    try:
        con.execute("BEGIN TRANSACTION")
        if _table_exists(con, BDT_SUMMARY_TABLE):
            placeholders = ", ".join(["?"] * len(reporting_periods)) if reporting_periods else "''"
            existing = con.execute(
                f"SELECT * FROM {BDT_SUMMARY_TABLE} WHERE reporting_period NOT IN ({placeholders})",
                reporting_periods,
            ).fetchdf() if reporting_periods else con.execute(f"SELECT * FROM {BDT_SUMMARY_TABLE}").fetchdf()
        else:
            existing = pd.DataFrame()
        merged = pd.concat([existing, prepared], ignore_index=True, sort=False) if not existing.empty else prepared
        con.execute(f"DROP TABLE IF EXISTS {BDT_SUMMARY_TABLE}")
        if merged.empty:
            _ensure_bdt_table(con)
        else:
            con.register("merged_df", merged)
            con.execute(f"CREATE TABLE {BDT_SUMMARY_TABLE} AS SELECT * FROM merged_df")
            con.unregister("merged_df")
        row_count = len(prepared)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    _log.info(
        "DuckDB bdt_summary merged: periods=%s rows=%d",
        reporting_periods,
        row_count,
    )
    return row_count


def replace_bdt_summary(df: pd.DataFrame) -> int:
    """Replace the complete DuckDB BDT Summary Catalog table with *df*."""
    prepared = df.copy() if df is not None else pd.DataFrame()
    con = _connect(read_only=False)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(f"DROP TABLE IF EXISTS {BDT_SUMMARY_TABLE}")
        if prepared.empty:
            _ensure_bdt_table(con)
        else:
            con.register("prepared_df", prepared)
            con.execute(f"CREATE TABLE {BDT_SUMMARY_TABLE} AS SELECT * FROM prepared_df")
            con.unregister("prepared_df")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return len(prepared)


def read_bdt_summary() -> pd.DataFrame:
    """Return the full BDT Summary Catalog table, or an empty frame."""
    if not CATALOG_DB_FILE.exists():
        return pd.DataFrame()
    con = _connect(read_only=True)
    try:
        if not _table_exists(con, BDT_SUMMARY_TABLE):
            return pd.DataFrame()
        return con.execute(f"SELECT * FROM {BDT_SUMMARY_TABLE}").fetchdf()
    finally:
        con.close()


def read_bdt_summary_site_ids() -> set[str]:
    """Return distinct site IDs from BDT summary catalog."""
    return {
        _normalize_site_id(site_id)
        for site_id in catalog_repo.fetch_bdt_summary_site_ids(
            CATALOG_DB_FILE,
            BDT_SUMMARY_TABLE,
        )
        if _normalize_site_id(site_id)
    }


def read_bdt_summary_site_stats() -> dict[str, dict[str, Any]]:
    """Return per-site BDT Summary counts and latest test dates."""
    stats: dict[str, dict[str, Any]] = {}
    rows = catalog_repo.fetch_bdt_summary_site_dates(
        CATALOG_DB_FILE,
        BDT_SUMMARY_TABLE,
    )
    for site_id, test_date in rows:
        normalized = _normalize_site_id(site_id)
        if not normalized:
            continue
        existing = stats.setdefault(
            normalized,
            {
                "bdt_summary_count": 0,
                "latest_bdt_at": None,
            },
        )
        existing["bdt_summary_count"] += 1
        if test_date is None:
            continue
        latest = pd.to_datetime(test_date, errors="coerce")
        if pd.isna(latest):
            continue
        existing_latest = pd.to_datetime(existing["latest_bdt_at"], errors="coerce")
        if pd.isna(existing_latest) or existing_latest < latest:
            existing["latest_bdt_at"] = str(test_date)
    return stats


def query_bdt_summary(
    site_id: str | None = None,
    reporting_period: str | None = None,
    week: str | None = None,
    test_date_from: str | None = None,
    test_date_to: str | None = None,
) -> pd.DataFrame:
    """Query BDT summary rows from DuckDB with optional filters."""
    if not CATALOG_DB_FILE.exists():
        return pd.DataFrame()
    con = _connect(read_only=True)
    try:
        if not _table_exists(con, BDT_SUMMARY_TABLE):
            return pd.DataFrame()
        clauses: list[str] = []
        params: list[Any] = []
        if site_id:
            clauses.append("site_id = ?")
            params.append(_normalize_site_id(site_id))
        if reporting_period:
            clauses.append("reporting_period = ?")
            params.append(reporting_period)
        if week:
            clauses.append("week = ?")
            params.append(week)
        if test_date_from:
            clauses.append("test_date >= ?")
            params.append(test_date_from)
        if test_date_to:
            clauses.append("test_date <= ?")
            params.append(test_date_to)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return con.execute(
            f"SELECT * FROM {BDT_SUMMARY_TABLE}{where}", params
        ).fetchdf()
    finally:
        con.close()
