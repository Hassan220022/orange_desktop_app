"""API stress tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'api.db'}"
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.repos.blob_repo.BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr("alarm_app.web.deps._engine", None)
    monkeypatch.setattr("alarm_app.web.deps._SessionFactory", None)
    monkeypatch.setattr("alarm_app.web.config.DATABASE_URL", db_url)
    from alarm_app.web.app import create_app
    return TestClient(create_app())


class TestSyncBatchStress:
    def test_batch_100_events(self, client):
        events = [
            {"event_id": f"evt-{i}", "origin_device_id": "dev-1",
             "entity_type": "alarm_record", "entity_local_id": str(i),
             "op": "upsert", "entity_hash": f"h{i}", "payload": {"i": i}}
            for i in range(100)
        ]
        r = client.post("/v1/sync/batches", json={
            "idempotency_key": "stress-batch",
            "events": events,
        })
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 100
        applied = sum(1 for r in results if r["status"] == "applied")
        assert applied == 100

    def test_batch_replay_all_duplicate(self, client):
        events = [
            {"event_id": f"replay-{i}", "origin_device_id": "dev-1",
             "entity_type": "alarm_record", "entity_local_id": str(i),
             "op": "upsert", "entity_hash": f"h{i}", "payload": {}}
            for i in range(50)
        ]
        payload = {"idempotency_key": "replay-test", "events": events}
        client.post("/v1/sync/batches", json=payload)
        r = client.post("/v1/sync/batches", json=payload)
        results = r.json()["results"]
        dupes = sum(1 for r in results if r["status"] == "duplicate")
        assert dupes == 50


class TestAlarmUpsertStress:
    def test_upsert_200_alarms(self, client):
        alarms = [
            {"site_id": f"S{i}", "alarm_name": f"Alarm-{i}",
             "occurred_on": f"2026-01-01T{i % 24:02d}:00:00"}
            for i in range(200)
        ]
        r = client.post("/v1/alarms/upsert", json={"alarms": alarms})
        assert r.status_code == 200
        assert r.json()["inserted"] > 0
