"""Sync outbox and checkpoint repository — replaces JSONL files."""

import json
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from alarm_app.db.models import SyncCheckpoint, SyncOutboxEvent

_log = logging.getLogger(__name__)


def append_outbox_event(session: Session, *, entity_type: str,
                        entity_local_id: str, op: str, entity_hash: str,
                        payload: dict, origin_device_id: str | None = None,
                        event_id: str | None = None) -> SyncOutboxEvent:
    """Append a sync event to the outbox."""
    try:
        evt = SyncOutboxEvent(
            event_id=event_id or str(uuid4()),
            origin_device_id=origin_device_id or "",
            entity_type=entity_type,
            entity_local_id=entity_local_id,
            op=op,
            entity_hash=entity_hash,
            payload_json=json.dumps(payload, default=str),
            status="pending",
        )
        session.add(evt)
        session.commit()
        _log.info("Outbox event appended: event_id=%s, entity_type=%s", evt.event_id, evt.entity_type)
        return evt
    except Exception:
        session.rollback()
        raise


def append_outbox_events(session: Session, events: list[dict]) -> int:
    """Append multiple sync events and commit once."""
    if not events:
        return 0

    try:
        for raw in events:
            session.add(SyncOutboxEvent(
                event_id=str(raw.get("event_id") or str(uuid4())),
                origin_device_id=str(raw.get("origin_device_id") or ""),
                entity_type=str(raw.get("entity_type") or ""),
                entity_local_id=str(raw.get("entity_local_id") or ""),
                op=str(raw.get("op") or "upsert"),
                entity_hash=str(raw.get("entity_hash") or ""),
                payload_json=json.dumps(raw.get("payload") or {}, default=str),
                status="pending",
            ))

        session.commit()
        _log.info("Outbox events appended in batch: count=%d", len(events))
        return len(events)
    except Exception:
        session.rollback()
        raise


def load_pending_outbox(session: Session, limit: int | None = None) -> list[dict]:
    """Load pending outbox events as dicts."""
    q = session.query(SyncOutboxEvent).filter_by(status="pending").order_by(
        SyncOutboxEvent.id
    )
    if limit:
        q = q.limit(limit)

    return [
        {
            "event_id": e.event_id,
            "origin_device_id": e.origin_device_id,
            "entity_type": e.entity_type,
            "entity_local_id": e.entity_local_id,
            "op": e.op,
            "entity_hash": e.entity_hash,
            "payload": json.loads(e.payload_json) if e.payload_json else {},
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in q.all()
    ]


def mark_outbox_synced(session: Session, event_ids: list[str],
                       checkpoint_cursor: str | None = None) -> int:
    """Mark events as synced and optionally update checkpoint."""
    try:
        count = 0
        now = datetime.now()
        for eid in event_ids:
            evt = session.query(SyncOutboxEvent).filter_by(event_id=eid).first()
            if evt and evt.status == "pending":
                evt.status = "synced"
                evt.synced_at = now
                count += 1

        if checkpoint_cursor:
            save_sync_checkpoint(session, checkpoint_cursor)

        session.commit()
        _log.info("Events marked synced: count=%d", count)
        return count
    except Exception:
        session.rollback()
        raise


def save_sync_checkpoint(session: Session, cursor: str) -> None:
    """Save or update the sync checkpoint."""
    try:
        cp = session.query(SyncCheckpoint).first()
        if cp:
            cp.cursor = cursor
            cp.last_ack_at = datetime.now()
        else:
            session.add(SyncCheckpoint(cursor=cursor, last_ack_at=datetime.now()))
        session.commit()
        _log.debug("Sync checkpoint saved: cursor=%s", cursor)
    except Exception:
        session.rollback()
        raise


def load_sync_checkpoint(session: Session) -> dict | None:
    """Load the current sync checkpoint."""
    cp = session.query(SyncCheckpoint).first()
    if not cp:
        return None
    return {
        "cursor": cp.cursor,
        "batch_key": cp.batch_key,
        "last_ack_at": cp.last_ack_at.isoformat() if cp.last_ack_at else None,
    }
