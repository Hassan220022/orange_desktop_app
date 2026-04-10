"""Tests for db/repos/sync_repo.py."""
import pytest
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.sync_repo import (
    append_outbox_event, load_pending_outbox,
    mark_outbox_synced, save_sync_checkpoint, load_sync_checkpoint,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestSyncRepo:
    def test_append_and_load(self, session):
        append_outbox_event(session, entity_type="alarm",
                            entity_local_id="1", op="upsert",
                            entity_hash="h1", payload={"site": "S1"})
        pending = load_pending_outbox(session)
        assert len(pending) == 1
        assert pending[0]["entity_type"] == "alarm"

    def test_mark_synced(self, session):
        evt = append_outbox_event(session, entity_type="alarm",
                                  entity_local_id="1", op="upsert",
                                  entity_hash="h1", payload={})
        count = mark_outbox_synced(session, [evt.event_id])
        assert count == 1
        assert load_pending_outbox(session) == []

    def test_checkpoint_round_trip(self, session):
        save_sync_checkpoint(session, "cursor-42")
        cp = load_sync_checkpoint(session)
        assert cp is not None
        assert cp["cursor"] == "cursor-42"

    def test_checkpoint_overwrites(self, session):
        save_sync_checkpoint(session, "cursor-1")
        save_sync_checkpoint(session, "cursor-2")
        cp = load_sync_checkpoint(session)
        assert cp["cursor"] == "cursor-2"

    def test_load_with_limit(self, session):
        for i in range(5):
            append_outbox_event(session, entity_type="alarm",
                                entity_local_id=str(i), op="upsert",
                                entity_hash=f"h{i}", payload={})
        pending = load_pending_outbox(session, limit=3)
        assert len(pending) == 3
