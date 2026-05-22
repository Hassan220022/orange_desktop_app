"""Site Metadata Catalog and BDT Summary Catalog SQLite repository."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

try:
    from alarm_app.db.models import BDTSummaryCatalog, SiteMetadataCatalog
    from alarm_app.db.retry import safe_flush
except ImportError:
    from db.models import BDTSummaryCatalog, SiteMetadataCatalog
    from db.retry import safe_flush

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Site Metadata Catalog
# ---------------------------------------------------------------------------


def replace_all_site_metadata(
    session: Session,
    rows: list[dict[str, Any]],
) -> int:
    """Delete all site-metadata rows then insert *rows*.

    Each dict must have keys: ``site_id``, ``original_headers_json``,
    ``raw_data_json``.  Returns the number of rows inserted.
    """
    session.query(SiteMetadataCatalog).delete()
    count = 0
    for row in rows:
        record = SiteMetadataCatalog(
            site_id=row["site_id"],
            original_headers_json=row["original_headers_json"],
            raw_data_json=row["raw_data_json"],
        )
        session.add(record)
        count += 1
    safe_flush(session)
    _log.info("Site metadata catalog replaced: %d rows", count)
    return count


def merge_site_metadata(
    session: Session,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert site-metadata *rows* by site_id, preserving unrelated sites.

    Each dict must have keys: ``site_id``, ``original_headers_json``,
    ``raw_data_json``. Duplicate site IDs in *rows* use the last row.
    Returns the number of unique site IDs merged.
    """
    by_site_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        site_id = str(row.get("site_id") or "").strip()
        if site_id:
            by_site_id[site_id] = row

    for site_id, row in by_site_id.items():
        record = session.get(SiteMetadataCatalog, site_id)
        if record is None:
            record = SiteMetadataCatalog(site_id=site_id)
            session.add(record)
        record.original_headers_json = row["original_headers_json"]
        record.raw_data_json = row["raw_data_json"]
    safe_flush(session)
    count = len(by_site_id)
    _log.info("Site metadata catalog merged: %d rows", count)
    return count


def query_site_metadata(session: Session, site_id: str) -> SiteMetadataCatalog | None:
    """Look up a single site-metadata row by normalized site_id."""
    return session.get(SiteMetadataCatalog, site_id)


# ---------------------------------------------------------------------------
# BDT Summary Catalog
# ---------------------------------------------------------------------------


def delete_bdt_period(session: Session, reporting_period: str) -> int:
    """Delete all BDT summary rows for *reporting_period*. Returns count deleted."""
    deleted = (
        session.query(BDTSummaryCatalog)
        .filter(BDTSummaryCatalog.reporting_period == reporting_period)
        .delete()
    )
    _log.info("BDT summary period deleted: period=%s count=%d", reporting_period, deleted)
    return deleted


def insert_bdt_rows(
    session: Session,
    rows: list[dict[str, Any]],
) -> int:
    """Insert *rows* into bdt_summary_catalog.

    Each dict must have: ``site_id``, ``reporting_period``, ``week``,
    ``test_date``, ``test_year``, ``original_headers_json``,
    ``raw_data_json``.  Duplicate rows (by unique constraint) are
    silently skipped. Returns rows actually inserted.
    """
    from sqlalchemy.exc import IntegrityError

    inserted = 0
    skipped = 0
    for row in rows:
        record = BDTSummaryCatalog(
            site_id=row["site_id"],
            reporting_period=row["reporting_period"],
            week=row.get("week"),
            test_date=_ensure_date(row.get("test_date")),
            test_year=_ensure_int(row.get("test_year")),
            content_hash=row["content_hash"],
            original_headers_json=row["original_headers_json"],
            raw_data_json=row["raw_data_json"],
        )
        # Use a savepoint so a duplicate skip doesn't roll back prior inserts
        try:
            with session.begin_nested():
                session.add(record)
                safe_flush(session)
            inserted += 1
        except IntegrityError:
            skipped += 1
    _log.info(
        "BDT summary rows: inserted=%d skipped=%d", inserted, skipped,
    )
    return inserted


def merge_bdt_period(
    session: Session,
    reporting_period: str,
    rows: list[dict[str, Any]],
) -> int:
    """Replace BDT summary rows for *reporting_period* with *rows*."""
    delete_bdt_period(session, reporting_period)
    return insert_bdt_rows(session, rows)


def _ensure_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _ensure_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None
