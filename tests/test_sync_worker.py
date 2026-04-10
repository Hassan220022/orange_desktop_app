"""Tests for local sync worker state machine behavior."""

import alarm_app.data.state as state_mod
from alarm_app.data.sync import (
    LocalSyncWorker,
    TransientSyncError,
    compute_batch_idempotency_key,
)


def _append_event(event_id: str, created_at: str, local_id: str) -> dict:
    return state_mod.append_outbox_event(
        entity_type="alarm_record_batch",
        entity_local_id=local_id,
        op="upsert",
        entity_hash=f"hash-{event_id}",
        payload={"rows": 1, "local_id": local_id},
        event_id=event_id,
        created_at=created_at,
    )


def _success_response(request: dict) -> dict:
    return {
        "items": [
            {
                "event_id": event["event_id"],
                "status": "applied",
            }
            for event in request["events"]
        ],
        "checkpoint_cursor": request["checkpoint_cursor"],
    }


def _isolate_state_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state_mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(state_mod, "CACHE_FILE", tmp_path / "data_cache.parquet")
    monkeypatch.setattr(state_mod, "ALARM_IDS_FILE", tmp_path / "alarm_ids.json")
    monkeypatch.setattr(state_mod, "REVIEW_LOG_FILE", tmp_path / "review_log.jsonl")
    monkeypatch.setattr(state_mod, "OUTBOX_FILE", tmp_path / "sync_outbox.jsonl")
    monkeypatch.setattr(state_mod, "SYNC_CHECKPOINT_FILE", tmp_path / "sync_checkpoint.json")
    monkeypatch.setattr(state_mod, "DEVICE_ID_FILE", tmp_path / "device_id.txt")


def test_process_once_success_marks_synced_and_advances_checkpoint(tmp_path, monkeypatch):
    _isolate_state_paths(tmp_path, monkeypatch)
    e1 = _append_event("e-1", "2026-04-08T09:00:00", "batch-1")
    e2 = _append_event("e-2", "2026-04-08T09:01:00", "batch-2")
    e3 = _append_event("e-3", "2026-04-08T09:02:00", "batch-3")

    sent_requests: list[dict] = []

    def send_batch(request: dict) -> dict:
        sent_requests.append(request)
        return _success_response(request)

    worker = LocalSyncWorker(send_batch=send_batch, batch_size=2)

    assert worker.process_once() is True

    assert len(sent_requests) == 1
    first_request = sent_requests[0]
    assert [event["event_id"] for event in first_request["events"]] == [
        e1["event_id"],
        e2["event_id"],
    ]
    assert first_request["idempotency_key"] == compute_batch_idempotency_key(first_request["events"])

    pending = state_mod.load_pending_outbox()
    assert [event["event_id"] for event in pending] == [e3["event_id"]]

    checkpoint = state_mod.load_sync_checkpoint()
    assert checkpoint is not None
    assert checkpoint["cursor"] == e2["event_id"]


def test_process_once_retries_transient_failure_with_exponential_backoff(tmp_path, monkeypatch):
    _isolate_state_paths(tmp_path, monkeypatch)
    event = _append_event("retry-1", "2026-04-08T09:00:00", "retry-batch")

    clock = {"now": 100.0}

    def time_fn() -> float:
        return clock["now"]

    calls = {"count": 0}

    def flaky_send(request: dict) -> dict:
        calls["count"] += 1
        if calls["count"] <= 2:
            raise TransientSyncError("temporary network failure")
        return _success_response(request)

    worker = LocalSyncWorker(
        send_batch=flaky_send,
        batch_size=1,
        base_backoff_seconds=2.0,
        max_backoff_seconds=30.0,
        time_fn=time_fn,
    )

    assert worker.process_once() is False
    assert calls["count"] == 1
    assert worker.next_attempt_at == 102.0

    # Backoff gate blocks immediate retry.
    assert worker.process_once() is False
    assert calls["count"] == 1

    clock["now"] = 102.0
    assert worker.process_once() is False
    assert calls["count"] == 2
    assert worker.next_attempt_at == 106.0

    clock["now"] = 106.0
    assert worker.process_once() is True
    assert calls["count"] == 3
    assert worker.consecutive_failures == 0

    pending = state_mod.load_pending_outbox()
    assert pending == []

    checkpoint = state_mod.load_sync_checkpoint()
    assert checkpoint is not None
    assert checkpoint["cursor"] == event["event_id"]


def test_process_once_resumes_from_checkpoint_cursor(tmp_path, monkeypatch):
    _isolate_state_paths(tmp_path, monkeypatch)
    e1 = _append_event("cp-1", "2026-04-08T09:00:00", "cp-batch-1")
    e2 = _append_event("cp-2", "2026-04-08T09:01:00", "cp-batch-2")
    e3 = _append_event("cp-3", "2026-04-08T09:02:00", "cp-batch-3")
    state_mod.save_sync_checkpoint(e2["event_id"])

    sent_requests: list[dict] = []

    def send_batch(request: dict) -> dict:
        sent_requests.append(request)
        return _success_response(request)

    worker = LocalSyncWorker(send_batch=send_batch, batch_size=10)

    assert worker.process_once() is True

    assert len(sent_requests) == 1
    assert [event["event_id"] for event in sent_requests[0]["events"]] == [e3["event_id"]]

    # cp-1 and cp-2 are reconciled from checkpoint; cp-3 is synced via send.
    assert state_mod.load_pending_outbox() == []

    checkpoint = state_mod.load_sync_checkpoint()
    assert checkpoint is not None
    assert checkpoint["cursor"] == e3["event_id"]
