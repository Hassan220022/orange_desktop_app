"""Bootstrap backfill -- queue outbox events for existing local data."""

from sqlalchemy.orm import Session

from alarm_app.db.models import (
    AlarmRecord,
    BDTTest,
    PMValidationRun,
    SyncOutboxEvent,
)
from alarm_app.db.repos.sync_repo import append_outbox_event as _repo_append
from alarm_app.data.state import get_or_create_device_id


def _already_synced_entity_ids(session: Session, entity_type: str) -> set[str]:
    """Return entity_local_ids that already have outbox events."""
    rows = (
        session.query(SyncOutboxEvent.entity_local_id)
        .filter_by(entity_type=entity_type)
        .all()
    )
    return {r[0] for r in rows}


def bootstrap_alarm_records(session: Session, batch_size: int = 500) -> int:
    """Queue outbox events for alarm records not yet synced. Returns count."""
    synced = _already_synced_entity_ids(session, "alarm_record")
    device_id = get_or_create_device_id()

    records = session.query(AlarmRecord).all()
    queued = 0
    for r in records:
        if str(r.id) in synced:
            continue
        _repo_append(
            session,
            entity_type="alarm_record",
            entity_local_id=str(r.id),
            op="upsert",
            entity_hash=r.row_hash or "",
            payload={
                "site_id": r.site_id,
                "alarm_name": r.alarm_name,
                "occurred_on": str(r.occurred_on) if r.occurred_on else "",
                "category": r.category,
                "vendor": r.vendor,
            },
            origin_device_id=device_id,
        )
        queued += 1
    return queued


def bootstrap_bdt_tests(session: Session) -> int:
    """Queue outbox events for BDT tests not yet synced."""
    synced = _already_synced_entity_ids(session, "bdt_test")
    device_id = get_or_create_device_id()

    tests = session.query(BDTTest).all()
    queued = 0
    for t in tests:
        if str(t.id) in synced:
            continue
        _repo_append(
            session,
            entity_type="bdt_test",
            entity_local_id=str(t.id),
            op="upsert",
            entity_hash=t.content_hash or "",
            payload={
                "site_code": t.site_code,
                "test_date": str(t.test_date) if t.test_date else "",
                "battery_brand": t.battery_brand or "",
            },
            origin_device_id=device_id,
        )
        queued += 1
    return queued


def bootstrap_validation_runs(session: Session) -> int:
    """Queue outbox events for PM validation runs not yet synced."""
    synced = _already_synced_entity_ids(session, "pm_run")
    device_id = get_or_create_device_id()

    runs = session.query(PMValidationRun).all()
    queued = 0
    for r in runs:
        if str(r.id) in synced:
            continue
        _repo_append(
            session,
            entity_type="pm_run",
            entity_local_id=str(r.id),
            op="upsert",
            entity_hash=r.alarm_input_sha256 or "",
            payload={"overall_verdict": r.overall_verdict or ""},
            origin_device_id=device_id,
        )
        queued += 1
    return queued


def run_bootstrap(session: Session) -> dict:
    """Run full bootstrap backfill. Returns counts per entity type."""
    return {
        "alarm_records": bootstrap_alarm_records(session),
        "bdt_tests": bootstrap_bdt_tests(session),
        "validation_runs": bootstrap_validation_runs(session),
    }
