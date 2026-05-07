"""Background local outbox sync worker for desktop migration."""

import hashlib
import json
import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from alarm_app.data import state

SyncSender = Callable[[dict], dict]


class TransientSyncError(RuntimeError):
    """Raised when sync fails and should be retried with backoff."""


def _event_for_idempotency(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(event.get("event_id", "") or ""),
        "origin_device_id": str(event.get("origin_device_id", "") or ""),
        "entity_type": str(event.get("entity_type", "") or ""),
        "entity_local_id": str(event.get("entity_local_id", "") or ""),
        "op": str(event.get("op", "") or ""),
        "entity_hash": str(event.get("entity_hash", "") or ""),
        "payload": event.get("payload") or {},
        "created_at": str(event.get("created_at", "") or ""),
    }


def compute_batch_idempotency_key(events: Sequence[Mapping[str, Any]]) -> str:
    """Compute stable idempotency key for one sync batch."""
    material = {
        "events": [_event_for_idempotency(event) for event in events],
        "event_count": len(events),
    }
    payload = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _default_send_batch(request: dict) -> dict:
    events = request.get("events") or []
    return {
        "items": [
            {
                "event_id": event.get("event_id"),
                "status": "applied",
            }
            for event in events
        ],
        "checkpoint_cursor": request.get("checkpoint_cursor"),
    }


def _extract_synced_event_ids(batch: Sequence[Mapping[str, Any]], response: Any) -> tuple[list[str], str | None]:
    if not isinstance(response, dict):
        event_ids = [str(event.get("event_id", "") or "") for event in batch]
        return [event_id for event_id in event_ids if event_id], event_ids[-1] if event_ids else None

    items = response.get("items")
    if isinstance(items, list):
        synced_ids: list[str] = []
        retryable_found = False
        for item in items:
            if not isinstance(item, dict):
                continue
            event_id = str(item.get("event_id", "") or "")
            if not event_id:
                continue
            status = str(item.get("status", "") or "").lower()
            if status in {"applied", "duplicate", "rejected"}:
                synced_ids.append(event_id)
            elif status in {"retryable_failed", "retryable-failed", "transient_failed"}:
                retryable_found = True

        if retryable_found:
            raise TransientSyncError("retryable_failed status in sync response")

        checkpoint_cursor = response.get("checkpoint_cursor") or response.get("cursor")
        return synced_ids, str(checkpoint_cursor) if checkpoint_cursor else None

    synced_ids = response.get("synced_event_ids") or []
    if isinstance(synced_ids, list):
        cleaned = [str(event_id) for event_id in synced_ids if str(event_id)]
        checkpoint_cursor = response.get("checkpoint_cursor") or response.get("cursor")
        return cleaned, str(checkpoint_cursor) if checkpoint_cursor else None

    event_ids = [str(event.get("event_id", "") or "") for event in batch]
    return [event_id for event_id in event_ids if event_id], event_ids[-1] if event_ids else None


class LocalSyncWorker:
    """Consume local outbox batches, push, and advance checkpoint on ACK."""

    def __init__(
        self,
        *,
        send_batch: SyncSender | None = None,
        batch_size: int = 100,
        poll_interval_seconds: float = 2.0,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
        time_fn: Callable[[], float] | None = None,
    ):
        self._send_batch = send_batch or _default_send_batch
        self.batch_size = max(1, int(batch_size))
        self.poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self.base_backoff_seconds = max(0.1, float(base_backoff_seconds))
        self.max_backoff_seconds = max(self.base_backoff_seconds, float(max_backoff_seconds))
        self._time_fn = time_fn or time.monotonic

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._consecutive_failures = 0
        self._next_attempt_at = 0.0

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def next_attempt_at(self) -> float:
        return self._next_attempt_at

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="alarm-sync-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = 3.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def process_once(self) -> bool:
        """Run one sync iteration. Returns True if at least one event was synced."""
        if self._stop_event.is_set():
            return False

        now = self._time_fn()
        if now < self._next_attempt_at:
            return False

        pending = state.load_pending_outbox(limit=self.batch_size * 4)
        if not pending:
            self._reset_backoff()
            return False

        checkpoint = state.load_sync_checkpoint() or {}
        cursor = str(checkpoint.get("cursor", "") or "")
        pending = self._reconcile_pending_with_checkpoint(pending, cursor)
        if not pending:
            self._reset_backoff()
            return False

        batch = pending[: self.batch_size]
        idempotency_key = compute_batch_idempotency_key(batch)
        fallback_cursor = str(batch[-1].get("event_id", "") or "")
        request = {
            "idempotency_key": idempotency_key,
            "checkpoint_cursor": fallback_cursor,
            "events": list(batch),
        }

        try:
            response = self._send_batch(request)
            synced_ids, ack_cursor = _extract_synced_event_ids(batch, response)
            if not synced_ids:
                self._reset_backoff()
                return False
            state.mark_outbox_synced(synced_ids, checkpoint_cursor=ack_cursor or fallback_cursor)
            self._reset_backoff()
            return True
        except TransientSyncError:
            self._schedule_backoff()
            return False
        except Exception:
            self._schedule_backoff()
            return False

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.process_once()
            self._stop_event.wait(self.poll_interval_seconds)

    def _reconcile_pending_with_checkpoint(self, rows: list[dict], cursor: str) -> list[dict]:
        if not cursor:
            return rows

        to_mark_synced: list[str] = []
        tail: list[dict] = []
        found_cursor = False

        for row in rows:
            event_id = str(row.get("event_id", "") or "")
            if found_cursor:
                tail.append(row)
                continue
            if event_id:
                to_mark_synced.append(event_id)
            if event_id == cursor:
                found_cursor = True

        if found_cursor and to_mark_synced:
            state.mark_outbox_synced(to_mark_synced, checkpoint_cursor=cursor)
            return tail

        return rows

    def _reset_backoff(self) -> None:
        self._consecutive_failures = 0
        self._next_attempt_at = 0.0

    def _schedule_backoff(self) -> None:
        self._consecutive_failures += 1
        delay = min(
            self.max_backoff_seconds,
            self.base_backoff_seconds * (2 ** (self._consecutive_failures - 1)),
        )
        self._next_attempt_at = self._time_fn() + delay
