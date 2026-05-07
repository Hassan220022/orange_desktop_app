"""HTTP sync client -- sends outbox batches to the cloud API."""

import json
import logging
import os
import urllib.error
import urllib.request

_log = logging.getLogger(__name__)

from alarm_app.data.sync import TransientSyncError

# Development-only: defaults to localhost for local testing.
# Set ALARM_SYNC_URL env var to override for production.
BACKEND_URL = os.environ.get("ALARM_SYNC_URL", "http://127.0.0.1:8787")

from urllib.parse import urlparse
_parsed = urlparse(BACKEND_URL)
if _parsed.scheme == "http" and _parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
    _log.warning("BACKEND_URL uses http to non-local host %s — payloads may be exposed", _parsed.hostname)


def http_send_batch(request: dict) -> dict:
    """POST a batch of outbox events to the sync API.

    Accepts the full request dict produced by LocalSyncWorker
    (keys: idempotency_key, checkpoint_cursor, events).

    Returns a dict with an ``items`` key that the worker's
    _extract_synced_event_ids can parse.

    Raises TransientSyncError on network or 5xx failures so the
    worker applies exponential backoff.
    """
    url = f"{BACKEND_URL}/v1/sync/batches"
    events = request.get("events") or []
    idempotency_key = request.get("idempotency_key", "")

    payload = json.dumps({
        "idempotency_key": idempotency_key,
        "events": [
            {
                "event_id": str(e.get("event_id", "") or ""),
                "origin_device_id": str(e.get("origin_device_id", "") or ""),
                "entity_type": str(e.get("entity_type", "") or ""),
                "entity_local_id": str(e.get("entity_local_id", "") or ""),
                "op": str(e.get("op", "") or ""),
                "entity_hash": str(e.get("entity_hash", "") or ""),
                "payload": e.get("payload") or {},
                "created_at": e.get("created_at") or "",
            }
            for e in events
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    _log.info("Batch sending: event_count=%d, url=%s", len(events), url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            _log.debug("Sync response payload: %s", body)
    except urllib.error.HTTPError as exc:
        if exc.code >= 500:
            _log.warning("Transient sync error: status=%d", exc.code)
            raise TransientSyncError(f"Server error {exc.code}") from exc
        raise
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        _log.warning("Transient sync error: %s", type(exc).__name__)
        raise TransientSyncError(f"Network error: {exc}") from exc

    # The API returns {"results": [...]}, but the worker expects {"items": [...]}.
    # Bridge the key name so _extract_synced_event_ids works unchanged.
    api_results = body.get("results") or []
    return {
        "items": api_results,
        "checkpoint_cursor": request.get("checkpoint_cursor"),
    }
