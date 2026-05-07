"""Tests for data/sync_client.py -- HTTP batch sender."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from alarm_app.data.sync import TransientSyncError
from alarm_app.data.sync_client import http_send_batch


def _make_request(events=None):
    """Build a request dict matching what LocalSyncWorker produces."""
    if events is None:
        events = [
            {
                "event_id": "e1",
                "origin_device_id": "dev-1",
                "entity_type": "alarm",
                "entity_local_id": "1",
                "op": "upsert",
                "entity_hash": "h1",
                "payload": {},
                "created_at": "2026-04-08T09:00:00",
            },
        ]
    return {
        "idempotency_key": "test-key-abc",
        "checkpoint_cursor": events[-1]["event_id"] if events else "",
        "events": events,
    }


class TestHttpSendBatch:
    def test_successful_batch_returns_items(self):
        request = _make_request()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [{"event_id": "e1", "status": "applied"}],
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            result = http_send_batch(request)

            assert result["items"][0]["event_id"] == "e1"
            assert result["items"][0]["status"] == "applied"
            assert result["checkpoint_cursor"] == "e1"

            call_args = mock_open.call_args
            sent_req = call_args[0][0]
            body = json.loads(sent_req.data.decode("utf-8"))
            assert body["idempotency_key"] == "test-key-abc"
            assert len(body["events"]) == 1

    def test_maps_results_to_items_key(self):
        """The API returns 'results' but the worker expects 'items'."""
        request = _make_request()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [
                {"event_id": "e1", "status": "applied"},
            ],
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = http_send_batch(request)
            assert "items" in result
            assert "results" not in result

    def test_server_500_raises_transient(self):
        request = _make_request()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "url", 500, "Internal Server Error", {}, None,
            ),
        ):
            with pytest.raises(TransientSyncError, match="Server error 500"):
                http_send_batch(request)

    def test_server_502_raises_transient(self):
        request = _make_request()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "url", 502, "Bad Gateway", {}, None,
            ),
        ):
            with pytest.raises(TransientSyncError, match="Server error 502"):
                http_send_batch(request)

    def test_client_400_does_not_raise_transient(self):
        """4xx errors are caller bugs, not transient -- let them propagate."""
        request = _make_request()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "url", 400, "Bad Request", {}, None,
            ),
        ):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                http_send_batch(request)
            assert exc_info.value.code == 400
            assert not isinstance(exc_info.value, TransientSyncError)

    def test_network_error_raises_transient(self):
        request = _make_request()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(TransientSyncError, match="Network error"):
                http_send_batch(request)

    def test_timeout_raises_transient(self):
        request = _make_request()

        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            with pytest.raises(TransientSyncError, match="Network error"):
                http_send_batch(request)

    def test_connection_error_raises_transient(self):
        request = _make_request()

        with patch(
            "urllib.request.urlopen",
            side_effect=ConnectionError("refused"),
        ):
            with pytest.raises(TransientSyncError, match="Network error"):
                http_send_batch(request)

    def test_preserves_checkpoint_cursor_from_request(self):
        events = [
            {
                "event_id": "e-last",
                "entity_type": "alarm",
                "entity_local_id": "99",
                "op": "upsert",
            },
        ]
        request = {
            "idempotency_key": "key-123",
            "checkpoint_cursor": "cursor-abc",
            "events": events,
        }

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "results": [{"event_id": "e-last", "status": "applied"}],
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = http_send_batch(request)
            assert result["checkpoint_cursor"] == "cursor-abc"

    def test_uses_backend_url_env(self, monkeypatch):
        monkeypatch.setattr(
            "alarm_app.data.sync_client.BACKEND_URL",
            "http://custom-host:9999",
        )
        request = _make_request()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"results": []}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            http_send_batch(request)
            sent_req = mock_open.call_args[0][0]
            assert sent_req.full_url == "http://custom-host:9999/v1/sync/batches"
