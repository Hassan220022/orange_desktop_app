"""Alarm records repository — row-level dedup via row_hash.

Optimized for large datasets (1M+ rows): uses vectorized pandas
operations and raw SQL instead of ORM objects for bulk insert/load.
"""

import hashlib
import logging
import math

import pandas as pd
from sqlalchemy.orm import Session
from alarm_app.db.models import AlarmRecord
from alarm_app.db.hashing import ALARM_HASH_COLS, _canonical_value

_log = logging.getLogger(__name__)

# Column mapping: DataFrame column name -> DB column name
_DF_TO_DB = {
    "site_id": "site_id",
    "alarm_name": "alarm_name",
    "alarm_id": "alarm_id",
    "occurred_on": "occurred_on",
    "cleared_on": "cleared_on",
    "duration": "duration",
    "_duration_secs": "duration_secs",
    "_category": "category",
    "vendor": "vendor",
    "network_type": "network_type",
    "severity": "severity",
    "fm_office": "fm_office",
    "alarm_source": "alarm_source",
    "alarm_category": "alarm_category",
    "clearance_status": "clearance_status",
    "additional_info": "additional_info",
    "site_down": "site_down",
}


def _sqlite_max_multi_rows(connectable, num_columns: int, default_max_variables: int = 999) -> int:
    """Return a safe max rows-per-statement for SQLite multi-row inserts."""
    if num_columns <= 0:
        return 1

    max_variables = default_max_variables
    try:
        if hasattr(connectable, "exec_driver_sql"):
            rows = connectable.exec_driver_sql("PRAGMA compile_options").fetchall()
        else:
            with connectable.connect() as conn:
                rows = conn.exec_driver_sql("PRAGMA compile_options").fetchall()
        for row in rows:
            option = str(row[0] if isinstance(row, tuple) else row)
            if option.startswith("MAX_VARIABLE_NUMBER="):
                max_variables = int(option.split("=", 1)[1])
                break
    except Exception:
        pass

    return max(1, max_variables // num_columns)


def _vectorized_row_hash(df: pd.DataFrame) -> pd.Series:
    """Compute SHA-256 row hashes using vectorized string ops."""
    parts = []
    for col in ALARM_HASH_COLS:
        if col in df.columns:
            s = df[col].astype(str).str.strip()
            s = s.replace({"nan": "", "None": "", "NaT": "", "<NA>": ""})
            parts.append(s.fillna(""))
        else:
            parts.append(pd.Series([""] * len(df), index=df.index))

    combined = parts[0]
    for p in parts[1:]:
        combined = combined.str.cat(p, sep="|")

    # str.cat can produce NaN if any part is NaN — fill before hashing
    combined = combined.fillna("")
    return combined.apply(lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest())


def bulk_upsert_alarms(session: Session, df: pd.DataFrame,
                       file_id: int | None = None) -> tuple[int, int]:
    """Insert alarm rows with dedup. Returns (inserted, skipped).

    Uses vectorized hashing and pandas to_sql for speed on large datasets.
    """
    if df.empty:
        return 0, 0

    total = len(df)
    _log.debug("bulk_upsert_alarms: processing %d rows", total)

    # 1. Vectorized hash computation (~10x faster than apply+to_dict)
    df = df.copy()
    df["_row_hash"] = _vectorized_row_hash(df)
    _log.debug("Hashes computed for %d rows", total)

    # 2. Drop duplicates within the batch itself
    df = df.drop_duplicates(subset="_row_hash", keep="first")
    in_batch_dupes = total - len(df)
    if in_batch_dupes > 0:
        _log.debug("Dropped %d in-batch duplicates", in_batch_dupes)

    # 3. Fetch existing hashes from DB
    conn = session.connection()
    existing = pd.read_sql(
        "SELECT row_hash FROM alarm_records",
        conn,
    )
    existing_set = set(existing["row_hash"]) if not existing.empty else set()
    _log.debug("DB has %d existing hashes", len(existing_set))

    # 4. Filter to only new rows
    mask = ~df["_row_hash"].isin(existing_set)
    new_df = df[mask].copy()
    skipped = int((~mask).sum()) + in_batch_dupes

    if new_df.empty:
        _log.info("Alarms upserted: inserted=0, skipped=%d (of %d total)", skipped, total)
        return 0, skipped

    # 5. Build insert DataFrame with DB column names
    insert_df = pd.DataFrame()
    insert_df["row_hash"] = new_df["_row_hash"]
    if file_id is not None:
        insert_df["file_id"] = file_id

    for df_col, db_col in _DF_TO_DB.items():
        if df_col in new_df.columns:
            insert_df[db_col] = new_df[df_col]
        else:
            insert_df[db_col] = None

    # Convert NaT/NaN to None for SQLite
    insert_df = insert_df.where(insert_df.notna(), None)

    # 6. Bulk insert via pandas to_sql (much faster than ORM add_all)
    inserted = len(insert_df)
    chunk_rows = 5000
    if getattr(conn.dialect, "name", "") == "sqlite":
        chunk_rows = min(
            chunk_rows,
            _sqlite_max_multi_rows(conn, len(insert_df.columns)),
        )
    insert_df.to_sql(
        "alarm_records",
        conn,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=chunk_rows,
    )

    _log.info("Alarms upserted: inserted=%d, skipped=%d (of %d total)",
              inserted, skipped, total)
    return inserted, skipped


def load_alarms_as_df(session: Session) -> pd.DataFrame:
    """Load all alarm records as a pandas DataFrame.

    Uses pd.read_sql for speed instead of ORM iteration.
    """
    conn = session.connection()
    df = pd.read_sql("SELECT * FROM alarm_records", conn)

    if df.empty:
        return pd.DataFrame()

    # Rename DB columns back to DataFrame convention
    db_to_df = {v: k for k, v in _DF_TO_DB.items()}
    df = df.rename(columns=db_to_df)

    # Drop DB-only columns
    for col in ("id", "row_hash", "file_id", "created_at", "tenant_id"):
        if col in df.columns:
            df = df.drop(columns=col)

    _log.debug("Loaded %d alarm records from DB", len(df))
    return df


def count_alarms(session: Session) -> int:
    """Return total alarm record count."""
    conn = session.connection()
    result = pd.read_sql("SELECT COUNT(*) as cnt FROM alarm_records", conn)
    return int(result["cnt"].iloc[0]) if not result.empty else 0
