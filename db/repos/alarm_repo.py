"""Alarm records repository — row-level dedup via row_hash."""

import math

import pandas as pd
from sqlalchemy.orm import Session
from alarm_app.db.models import AlarmRecord
from alarm_app.db.hashing import compute_row_hash, ALARM_HASH_COLS


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
    """Insert alarm rows with dedup. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        row_hash = compute_row_hash(row_dict)

        existing = session.query(AlarmRecord.id).filter_by(
            row_hash=row_hash
        ).first()
        if existing:
            skipped += 1
            continue

        record = AlarmRecord(
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
        )
        session.add(record)
        inserted += 1

    session.commit()
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
