"""Tests for state persistence (state.py)."""

import json
import os
from pathlib import Path

import pandas as pd
import pytest

import alarm_app.state as state_mod


@pytest.fixture(autouse=True)
def _isolate_state_dir(tmp_path, monkeypatch):
    """Redirect all state module paths to a temp directory for every test."""
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state_mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(state_mod, "CACHE_FILE", tmp_path / "data_cache.parquet")
    monkeypatch.setattr(state_mod, "ALARM_IDS_FILE", tmp_path / "alarm_ids.json")
    monkeypatch.setattr(state_mod, "REVIEW_LOG_FILE", tmp_path / "review_log.jsonl")
    monkeypatch.setattr(state_mod, "OUTBOX_FILE", tmp_path / "sync_outbox.jsonl")
    monkeypatch.setattr(state_mod, "SYNC_CHECKPOINT_FILE", tmp_path / "sync_checkpoint.json")
    monkeypatch.setattr(state_mod, "DEVICE_ID_FILE", tmp_path / "device_id.txt")


# ── save_state / load_state round-trip ─────────────────────────
class TestStatePersistence:
    def test_round_trip(self):
        payload = {"filters": {"vendor": "Huawei"}, "window_w": 1200}
        state_mod.save_state(payload)
        loaded = state_mod.load_state()
        assert loaded is not None
        assert loaded["filters"]["vendor"] == "Huawei"
        assert loaded["window_w"] == 1200
        assert "saved_at" in loaded  # timestamp added by save_state

    def test_load_missing_file_returns_none(self):
        assert state_mod.load_state() is None

    def test_overwrite_preserves_latest(self):
        state_mod.save_state({"version": 1})
        state_mod.save_state({"version": 2})
        loaded = state_mod.load_state()
        assert loaded["version"] == 2


# ── save_dataframe / load_dataframe round-trip ─────────────────
class TestDataFramePersistence:
    def test_round_trip(self):
        df = pd.DataFrame({
            "site_id": ["A001", "B002"],
            "occurred_on": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "duration": ["01:30:00", "02:45:00"],
        })
        state_mod.save_dataframe(df)
        loaded = state_mod.load_dataframe()
        assert loaded is not None
        assert len(loaded) == 2
        assert list(loaded.columns) == ["site_id", "occurred_on", "duration"]

    def test_object_columns_coerced_to_string(self):
        """Mixed-type object columns survive Parquet serialisation."""
        df = pd.DataFrame({"mixed": ["hello", None, 42]})
        state_mod.save_dataframe(df)
        loaded = state_mod.load_dataframe()
        assert loaded is not None
        # None becomes "" then str, 42 becomes "42"
        assert loaded["mixed"].tolist() == ["hello", "", "42"]

    def test_load_missing_file_returns_none(self):
        assert state_mod.load_dataframe() is None


# ── clear_cache ────────────────────────────────────────────────
class TestClearCache:
    def test_removes_both_files(self):
        state_mod.save_state({"x": 1})
        state_mod.save_dataframe(pd.DataFrame({"a": [1]}))
        assert state_mod.STATE_FILE.exists()
        assert state_mod.CACHE_FILE.exists()

        state_mod.clear_cache()

        assert not state_mod.STATE_FILE.exists()
        assert not state_mod.CACHE_FILE.exists()

    def test_no_error_when_files_missing(self):
        """clear_cache must not raise even if files don't exist."""
        state_mod.clear_cache()  # should silently pass


# ── load_alarm_ids / save_alarm_ids ────────────────────────────
class TestAlarmIds:
    def test_round_trip(self):
        ids = {"power": ["1001", "1002"], "down": ["2001"], "door": ["3001"]}
        state_mod.save_alarm_ids(ids)
        loaded = state_mod.load_alarm_ids()
        assert loaded["power"] == ["1001", "1002"]
        assert loaded["down"] == ["2001"]
        assert loaded["door"] == ["3001"]

    def test_load_missing_returns_empty_defaults(self):
        loaded = state_mod.load_alarm_ids()
        assert loaded == {"power": [], "down": [], "door": []}

    def test_strips_whitespace_and_coerces_to_str(self):
        ids = {"power": [" 100 ", 200], "down": [], "door": [" 300 ", 400]}
        state_mod.save_alarm_ids(ids)
        loaded = state_mod.load_alarm_ids()
        assert loaded["power"] == ["100", "200"]
        assert loaded["door"] == ["300", "400"]


# ── review log / daily report ────────────────────────────────
class TestReviewLog:
    def test_append_and_summarize_by_day(self):
        state_mod.append_review_event(
            username="alice",
            filename="a.xlsx",
            site_code="0167DE",
            test_date="2026-01-11",
            verdict="Accepted",
            reviewed_at="2026-04-06T08:15:00",
        )
        state_mod.append_review_event(
            username="alice",
            filename="b.xlsx",
            site_code="0168DE",
            test_date="2026-01-12",
            verdict="Rejected",
            reviewed_at="2026-04-06T09:30:00",
        )
        state_mod.append_review_event(
            username="bob",
            filename="c.xlsx",
            site_code="0169DE",
            test_date="2026-01-13",
            verdict="Revise",
            reviewed_at="2026-04-05T10:00:00",
        )

        events = state_mod.load_review_events()
        assert len(events) == 3

        summary = state_mod.summarize_review_events_by_day(events)
        assert summary[0]["date"] == "2026-04-06"
        assert summary[0]["tests_reviewed"] == 2
        assert summary[0]["Accepted"] == 1
        assert summary[0]["Rejected"] == 1
        assert summary[0]["users"] == "alice"
        assert summary[1]["date"] == "2026-04-05"
        assert summary[1]["Revise"] == 1
        assert summary[1]["users"] == "bob"


# ── compute_file_hashes ───────────────────────────────────────
class TestComputeFileHashes:
    def test_returns_sha256_for_existing_files(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f1.write_text("hello", encoding="utf-8")
        f2 = tmp_path / "b.csv"
        f2.write_text("world", encoding="utf-8")

        hashes = state_mod.compute_file_hashes([str(f1), str(f2)])
        assert str(f1) in hashes
        assert str(f2) in hashes
        assert len(hashes[str(f1)]) == 64  # SHA-256 hex length
        assert hashes[str(f1)] != hashes[str(f2)]

    def test_skips_nonexistent_files(self, tmp_path):
        missing = str(tmp_path / "nope.csv")
        hashes = state_mod.compute_file_hashes([missing])
        assert hashes == {}

    def test_deterministic(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("consistent", encoding="utf-8")
        h1 = state_mod.compute_file_hashes([str(f)])
        h2 = state_mod.compute_file_hashes([str(f)])
        assert h1 == h2


# ── files_changed ─────────────────────────────────────────────
class TestFilesChanged:
    def test_detects_added_file(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f1.write_text("data", encoding="utf-8")
        saved = state_mod.compute_file_hashes([str(f1)])

        f2 = tmp_path / "b.csv"
        f2.write_text("new", encoding="utf-8")

        assert state_mod.files_changed(saved, [str(f1), str(f2)]) is True

    def test_detects_removed_file(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f1.write_text("data", encoding="utf-8")
        f2 = tmp_path / "b.csv"
        f2.write_text("more", encoding="utf-8")
        saved = state_mod.compute_file_hashes([str(f1), str(f2)])

        assert state_mod.files_changed(saved, [str(f1)]) is True

    def test_detects_modified_file(self, tmp_path):
        f = tmp_path / "a.csv"
        f.write_text("original", encoding="utf-8")
        saved = state_mod.compute_file_hashes([str(f)])

        f.write_text("modified", encoding="utf-8")
        assert state_mod.files_changed(saved, [str(f)]) is True

    def test_no_change_returns_false(self, tmp_path):
        f = tmp_path / "a.csv"
        f.write_text("stable", encoding="utf-8")
        saved = state_mod.compute_file_hashes([str(f)])

        assert state_mod.files_changed(saved, [str(f)]) is False

    def test_empty_saved_hashes_returns_true(self, tmp_path):
        f = tmp_path / "a.csv"
        f.write_text("data", encoding="utf-8")
        assert state_mod.files_changed({}, [str(f)]) is True


class TestSyncOutboxAndCheckpoint:
    def test_append_and_load_pending_outbox(self):
        event = state_mod.append_outbox_event(
            entity_type="alarm_record_batch",
            entity_local_id="batch-1",
            op="upsert",
            entity_hash="abc123",
            payload={"rows": 10},
        )
        pending = state_mod.load_pending_outbox()
        assert len(pending) == 1
        assert pending[0]["event_id"] == event["event_id"]
        assert pending[0]["payload"]["rows"] == 10

    def test_mark_outbox_synced_and_checkpoint(self):
        e1 = state_mod.append_outbox_event(
            entity_type="uploaded_file",
            entity_local_id="/tmp/a.csv",
            op="upsert",
            entity_hash="hash-a",
            payload={"file_sha256": "hash-a"},
        )
        e2 = state_mod.append_outbox_event(
            entity_type="uploaded_file",
            entity_local_id="/tmp/b.csv",
            op="upsert",
            entity_hash="hash-b",
            payload={"file_sha256": "hash-b"},
        )

        synced = state_mod.mark_outbox_synced([e1["event_id"]], checkpoint_cursor=e1["event_id"])
        assert synced == 1

        pending = state_mod.load_pending_outbox()
        assert len(pending) == 1
        assert pending[0]["event_id"] == e2["event_id"]

        checkpoint = state_mod.load_sync_checkpoint()
        assert checkpoint is not None
        assert checkpoint["cursor"] == e1["event_id"]

    def test_get_or_create_device_id_stable(self):
        d1 = state_mod.get_or_create_device_id()
        d2 = state_mod.get_or_create_device_id()
        assert d1
        assert d1 == d2
