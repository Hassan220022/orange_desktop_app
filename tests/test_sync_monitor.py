"""Tests for sync monitoring."""

import pytest
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.sync_repo import append_outbox_event
from alarm_app.data.sync_monitor import outbox_stats


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestOutboxStats:
    def test_empty_outbox(self, session):
        stats = outbox_stats(session)
        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["synced"] == 0
        assert stats["lag_seconds"] == 0.0
        assert stats["health"] == "healthy"

    def test_with_pending_events(self, session):
        for i in range(5):
            append_outbox_event(
                session,
                entity_type="alarm",
                entity_local_id=str(i),
                op="upsert",
                entity_hash=f"h{i}",
                payload={},
            )
        stats = outbox_stats(session)
        assert stats["total"] == 5
        assert stats["pending"] == 5
        assert stats["synced"] == 0
        assert stats["health"] == "healthy"

    def test_health_degraded_with_many_pending(self, session):
        for i in range(101):
            append_outbox_event(
                session,
                entity_type="alarm",
                entity_local_id=str(i),
                op="upsert",
                entity_hash=f"h{i}",
                payload={},
            )
        stats = outbox_stats(session)
        assert stats["pending"] == 101
        assert stats["health"] == "degraded"

    def test_mixed_statuses(self, session):
        for i in range(3):
            append_outbox_event(
                session,
                entity_type="alarm",
                entity_local_id=str(i),
                op="upsert",
                entity_hash=f"h{i}",
                payload={},
            )
        from alarm_app.db.repos.sync_repo import mark_outbox_synced

        evt = session.query(
            __import__("alarm_app.db.models", fromlist=["SyncOutboxEvent"]).SyncOutboxEvent
        ).first()
        mark_outbox_synced(session, [evt.event_id])

        stats = outbox_stats(session)
        assert stats["total"] == 3
        assert stats["synced"] == 1
        assert stats["pending"] == 2
