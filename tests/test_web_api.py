"""Tests for the FastAPI web API."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.repos.blob_repo.BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr("alarm_app.web.config.DATABASE_URL", db_url)
    # Reset engine state so each test gets a fresh DB
    monkeypatch.setattr("alarm_app.web.deps._engine", None)
    monkeypatch.setattr("alarm_app.web.deps._SessionFactory", None)

    from alarm_app.web.app import create_app

    app = create_app()
    return TestClient(app)


class TestHealth:
    def test_health_check(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestSyncBatch:
    def test_receive_batch(self, client):
        r = client.post("/v1/sync/batches", json={
            "idempotency_key": "batch-1",
            "events": [
                {
                    "event_id": "evt-1",
                    "origin_device_id": "dev-1",
                    "entity_type": "alarm_record",
                    "entity_local_id": "1",
                    "op": "upsert",
                    "entity_hash": "abc123",
                    "payload": {"site_id": "S1"},
                }
            ],
        })
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 1
        assert results[0]["status"] == "applied"

    def test_duplicate_event_returns_duplicate(self, client):
        payload = {
            "idempotency_key": "batch-2",
            "events": [{
                "event_id": "evt-dup",
                "origin_device_id": "dev-1",
                "entity_type": "alarm_record",
                "entity_local_id": "1",
                "op": "upsert",
                "entity_hash": "abc123",
                "payload": {},
            }],
        }
        client.post("/v1/sync/batches", json=payload)
        r = client.post("/v1/sync/batches", json=payload)
        assert r.json()["results"][0]["status"] == "duplicate"


class TestAlarmUpsert:
    def test_upsert_alarms(self, client):
        r = client.post("/v1/alarms/upsert", json={
            "alarms": [
                {"site_id": "S1", "alarm_name": "Power Fail",
                 "occurred_on": "2026-01-01T10:00:00"},
            ],
        })
        assert r.status_code == 200
        assert r.json()["inserted"] >= 0


class TestPMRuns:
    def test_get_nonexistent_run(self, client):
        r = client.get("/v1/pm/runs/99999")
        assert r.status_code == 404
