"""End-to-end sync test: desktop sync_client -> FastAPI API -> DB.

Uses FastAPI TestClient to avoid subprocess/port flakiness while still
exercising the full HTTP serialisation round-trip through sync_client
and the real API router.
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from alarm_app.data.sync import _extract_synced_event_ids
from alarm_app.data.sync_client import http_send_batch


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Isolated FastAPI TestClient with a fresh temp database."""
    db_url = f"sqlite:///{tmp_path / 'server.db'}"
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "server.db")
    monkeypatch.setattr("alarm_app.web.config.DATABASE_URL", db_url)
    monkeypatch.setattr("alarm_app.web.deps._engine", None)
    monkeypatch.setattr("alarm_app.web.deps._SessionFactory", None)

    from alarm_app.web.app import create_app
    app = create_app()
    return TestClient(app)


def _urlopen_via_testclient(test_client):
    """Return a urlopen replacement that routes requests through TestClient."""

    def fake_urlopen(req, timeout=None):
        body = req.data
        resp = test_client.post(
            "/v1/sync/batches",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        resp_bytes = json.dumps(resp.json()).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = resp_bytes
        mock_resp.status = resp.status_code
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        if resp.status_code >= 400:
            import urllib.error
            raise urllib.error.HTTPError(
                req.full_url,
                resp.status_code,
                "Error",
                {},
                BytesIO(resp_bytes),
            )

        return mock_resp

    return fake_urlopen


class TestSyncE2E:
    def test_send_event_applied(self, api_client):
        """A fresh event goes through sync_client and gets 'applied'."""
        request = {
            "idempotency_key": "e2e-key-1",
            "checkpoint_cursor": "e2e-1",
            "events": [
                {
                    "event_id": "e2e-1",
                    "origin_device_id": "dev-test",
                    "entity_type": "alarm_record",
                    "entity_local_id": "100",
                    "op": "upsert",
                    "entity_hash": "testhash",
                    "payload": {"site_id": "TEST-SITE"},
                    "created_at": "2026-04-08T09:00:00",
                },
            ],
        }

        with patch("urllib.request.urlopen", _urlopen_via_testclient(api_client)):
            result = http_send_batch(request)

        assert len(result["items"]) == 1
        assert result["items"][0]["status"] == "applied"
        assert result["items"][0]["event_id"] == "e2e-1"

    def test_duplicate_event_returns_duplicate(self, api_client):
        """Sending the same event_id twice returns 'duplicate' on the second call."""
        request = {
            "idempotency_key": "e2e-key-dup",
            "checkpoint_cursor": "e2e-dup",
            "events": [
                {
                    "event_id": "e2e-dup",
                    "origin_device_id": "dev-test",
                    "entity_type": "alarm_record",
                    "entity_local_id": "200",
                    "op": "upsert",
                    "entity_hash": "duphash",
                    "payload": {},
                    "created_at": "2026-04-08T09:01:00",
                },
            ],
        }

        with patch("urllib.request.urlopen", _urlopen_via_testclient(api_client)):
            first = http_send_batch(request)
            assert first["items"][0]["status"] == "applied"

            second = http_send_batch(request)
            assert second["items"][0]["status"] == "duplicate"

    def test_worker_extract_parses_sync_client_response(self, api_client):
        """The worker's _extract_synced_event_ids handles sync_client output."""
        batch = [
            {
                "event_id": "parse-1",
                "origin_device_id": "dev-test",
                "entity_type": "alarm_record",
                "entity_local_id": "300",
                "op": "upsert",
                "entity_hash": "h300",
                "payload": {},
                "created_at": "2026-04-08T09:02:00",
            },
        ]
        request = {
            "idempotency_key": "e2e-key-parse",
            "checkpoint_cursor": "parse-1",
            "events": batch,
        }

        with patch("urllib.request.urlopen", _urlopen_via_testclient(api_client)):
            response = http_send_batch(request)

        synced_ids, cursor = _extract_synced_event_ids(batch, response)
        assert synced_ids == ["parse-1"]

    def test_multi_event_batch(self, api_client):
        """A batch with multiple events processes all of them."""
        events = [
            {
                "event_id": f"multi-{i}",
                "origin_device_id": "dev-test",
                "entity_type": "alarm_record",
                "entity_local_id": str(400 + i),
                "op": "upsert",
                "entity_hash": f"h{400 + i}",
                "payload": {"index": i},
                "created_at": f"2026-04-08T09:0{i}:00",
            }
            for i in range(3)
        ]
        request = {
            "idempotency_key": "e2e-key-multi",
            "checkpoint_cursor": "multi-2",
            "events": events,
        }

        with patch("urllib.request.urlopen", _urlopen_via_testclient(api_client)):
            result = http_send_batch(request)

        assert len(result["items"]) == 3
        statuses = {item["event_id"]: item["status"] for item in result["items"]}
        assert statuses["multi-0"] == "applied"
        assert statuses["multi-1"] == "applied"
        assert statuses["multi-2"] == "applied"
