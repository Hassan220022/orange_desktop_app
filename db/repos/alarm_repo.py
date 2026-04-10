"""Alarm records repository — row-level dedup via row_hash."""

import logging
import math

import pandas as pd
from sqlalchemy.orm import Session
from alarm_app.db.models import AlarmRecord
from alarm_app.db.hashing import compute_row_hash, ALARM_HASH_COLS

_log = logging.getLogger(__name__)


def _safe_val(value):
    """Convert pandas sentinel values (NaT, NaN) to None for SQLAlchemy."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def bulk_upsert_alarms(session: Session, df: pd.DataFrame,
                       file_id: int | None = None) -> tuple[int, int]:
    """Insert alarm rows with dedup. Returns (inserted, skipped).

    Uses batch hash computation and a single query to fetch existing
    hashes, then bulk-inserts only new rows. Much faster than per-row
    SELECT for large datasets.
    """
    if df.empty:
        return 0, 0

    # 1. Compute all row hashes in one pass
    hashes = df.apply(lambda row: compute_row_hash(row.to_dict()), axis=1)
    _log.debug("Computed %d row hashes", len(hashes))

    # 2. Fetch existing hashes in one query
    unique_hashes = set(hashes)
    existing_hashes: set[str] = set()
    batch_size = 500
    hash_list = list(unique_hashes)
    for i in range(0, len(hash_list), batch_size):
        chunk = hash_list[i:i + batch_size]
        rows = (
            session.query(AlarmRecord.row_hash)
            .filter(AlarmRecord.row_hash.in_(chunk))
            .all()
        )
        existing_hashes.update(r[0] for r in rows)

    # 3. Bulk-insert only new rows
    new_records = []
    for idx, row_hash in enumerate(hashes):
        if row_hash in existing_hashes:
            continue
        existing_hashes.add(row_hash)  # prevent dupes within same batch
        row_dict = df.iloc[idx].to_dict()
        new_records.append(AlarmRecord(
            row_hash=row_hash,
            file_id=file_id,
            site_id=_safe_val(row_dict.get("site_id")),
            alarm_name=_safe_val(row_dict.get("alarm_name")),
            alarm_id=_safe_val(row_dict.get("alarm_id")),
            occurred_on=_safe_val(row_dict.get("occurred_on")),
            cleared_on=_safe_val(row_dict.get("cleared_on")),
            duration=_safe_val(row_dict.get("duration")),
            duration_secs=_safe_val(row_dict.get("_duration_secs")),
            category=_safe_val(row_dict.get("_category")),
            vendor=_safe_val(row_dict.get("vendor")),
            network_type=_safe_val(row_dict.get("network_type")),
            severity=_safe_val(row_dict.get("severity")),
            fm_office=_safe_val(row_dict.get("fm_office")),
            alarm_source=_safe_val(row_dict.get("alarm_source")),
            alarm_category=_safe_val(row_dict.get("alarm_category")),
            clearance_status=_safe_val(row_dict.get("clearance_status")),
            additional_info=_safe_val(row_dict.get("additional_info")),
            site_down=bool(row_dict.get("site_down", False)),
        ))

    if new_records:
        session.add_all(new_records)
    session.commit()

    inserted = len(new_records)
    skipped = len(hashes) - inserted
    _log.info("Alarms upserted: inserted=%d, skipped=%d (of %d total rows)",
              inserted, skipped, len(hashes))
    return inserted, skipped


def load_alarms_as_df(session: Session) -> pd.DataFrame:
    """Load all alarm records as a pandas DataFrame."""
    rows = session.query(AlarmRecord).all()
    if not rows:
        return pd.DataFrame()

    records = []
    for r in rows:
        records.append({
            "site_id": r.site_id,
            "alarm_name": r.alarm_name,
            "alarm_id": r.alarm_id,
            "occurred_on": r.occurred_on,
            "cleared_on": r.cleared_on,
            "duration": r.duration,
            "_duration_secs": r.duration_secs,
            "_category": r.category,
            "vendor": r.vendor,
            "network_type": r.network_type,
            "severity": r.severity,
            "fm_office": r.fm_office,
            "alarm_source": r.alarm_source,
            "alarm_category": r.alarm_category,
            "clearance_status": r.clearance_status,
            "additional_info": r.additional_info,
            "site_down": r.site_down,
        })
    return pd.DataFrame(records)


def count_alarms(session: Session) -> int:
    """Return total alarm record count."""
    return session.query(AlarmRecord).count()
