"""Bootstrap backfill -- queue outbox events for existing local data."""

import json
import logging
from uuid import uuid4

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

try:
    from alarm_app.data.state import get_or_create_device_id
    from alarm_app.db.models import (
        AlarmRecord,
        BDTTest,
        PMValidationRun,
        SyncOutboxEvent,
    )
except ImportError:
    from data.state import get_or_create_device_id
    from db.models import (
        AlarmRecord,
        BDTTest,
        PMValidationRun,
        SyncOutboxEvent,
    )


def _already_synced_entity_ids(session: Session, entity_type: str) -> set[str]:
    """Return entity_local_ids that already have outbox events."""
    rows = (
        session.query(SyncOutboxEvent.entity_local_id)
        .filter_by(entity_type=entity_type)
        .all()
    )
    return {r[0] for r in rows}


def _queue_batch(session: Session, events: list[dict], device_id: str) -> int:
    """Add a batch of outbox events via add_all and commit once."""
    if not events:
        return 0
    for raw in events:
        session.add(SyncOutboxEvent(
            event_id=str(uuid4()),
            origin_device_id=device_id,
            entity_type=raw["entity_type"],
            entity_local_id=raw["entity_local_id"],
            op="upsert",
            entity_hash=raw["entity_hash"],
            payload_json=json.dumps(raw["payload"], default=str),
            status="pending",
        ))
    session.commit()
    return len(events)


def bootstrap_alarm_records(session: Session, batch_size: int = 500) -> int:
    """Queue outbox events for alarm records not yet synced. Returns count."""
    if session.bind is None or not sa_inspect(session.bind).has_table("alarm_records"):
        return 0

    synced = _already_synced_entity_ids(session, "alarm_record")
    device_id = get_or_create_device_id()

    records = session.query(AlarmRecord).all()
    events = []
    for r in records:
        if str(r.id) in synced:
            continue
        events.append({
            "entity_type": "alarm_record",
            "entity_local_id": str(r.id),
            "entity_hash": r.row_hash or "",
            "payload": {
                "site_id": r.site_id,
                "alarm_name": r.alarm_name,
                "occurred_on": str(r.occurred_on) if r.occurred_on else "",
                "category": r.category,
                "vendor": r.vendor,
            },
        })
    return _queue_batch(session, events, device_id)


def bootstrap_bdt_tests(session: Session) -> int:
    """Queue outbox events for BDT tests not yet synced."""
    synced = _already_synced_entity_ids(session, "bdt_test")
    device_id = get_or_create_device_id()

    tests = session.query(BDTTest).all()
    events = []
    for t in tests:
        if str(t.id) in synced:
            continue
        events.append({
            "entity_type": "bdt_test",
            "entity_local_id": str(t.id),
            "entity_hash": t.content_hash or "",
            "payload": {
                "site_code": t.site_code,
                "test_date": str(t.test_date) if t.test_date else "",
                "battery_brand": t.battery_brand or "",
            },
        })
    return _queue_batch(session, events, device_id)


def bootstrap_validation_runs(session: Session) -> int:
    """Queue outbox events for PM validation runs not yet synced."""
    synced = _already_synced_entity_ids(session, "pm_run")
    device_id = get_or_create_device_id()

    runs = session.query(PMValidationRun).all()
    events = []
    for r in runs:
        if str(r.id) in synced:
            continue
        events.append({
            "entity_type": "pm_run",
            "entity_local_id": str(r.id),
            "entity_hash": r.alarm_input_sha256 or "",
            "payload": {"overall_verdict": r.overall_verdict or ""},
        })
    return _queue_batch(session, events, device_id)


def run_bootstrap(session: Session) -> dict:
    """Run full bootstrap backfill. Returns counts per entity type."""
    _log.info("Bootstrap started")
    counts = {
        "alarm_records": bootstrap_alarm_records(session),
        "bdt_tests": bootstrap_bdt_tests(session),
        "validation_runs": bootstrap_validation_runs(session),
    }
    _log.info("Bootstrap completed: alarm_records=%d, bdt_tests=%d, validation_runs=%d",
              counts["alarm_records"], counts["bdt_tests"], counts["validation_runs"])
    return counts
