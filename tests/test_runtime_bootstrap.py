from pathlib import Path

import alarm_app.data.state as state_mod
from alarm_app.runtime.bootstrap import bootstrap_local_runtime


def test_bootstrap_local_runtime_creates_state_db_blob_and_duckdb(tmp_path, monkeypatch):
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state_mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(state_mod, "ALARM_IDS_FILE", tmp_path / "alarm_ids.json")
    monkeypatch.setattr(state_mod, "REVIEW_LOG_FILE", tmp_path / "review_log.jsonl")
    monkeypatch.setattr(state_mod, "OUTBOX_FILE", tmp_path / "sync_outbox.jsonl")
    monkeypatch.setattr(state_mod, "SYNC_CHECKPOINT_FILE", tmp_path / "sync_checkpoint.json")
    monkeypatch.setattr(state_mod, "DEVICE_ID_FILE", tmp_path / "device_id.txt")
    monkeypatch.setattr(state_mod, "ALARM_DB_FILE", tmp_path / "alarms.duckdb")
    monkeypatch.setattr(state_mod, "ALARM_DB_FALLBACK_FILE", tmp_path / "alarms.local.duckdb")

    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "alarm_viewer.db")
    monkeypatch.setattr("alarm_app.db.repos.blob_repo.BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr("alarm_app.data.alarm_store.ALARM_DB_FILE", tmp_path / "alarms.duckdb")
    monkeypatch.setattr("alarm_app.logging_config.LOG_DIR", tmp_path / "logs")

    monkeypatch.setattr(state_mod, "_engine", None)
    monkeypatch.setattr(state_mod, "_SessionFactory", None)

    result = bootstrap_local_runtime()

    assert Path(result["state_dir"]).exists()
    assert Path(result["sqlite_db"]).exists()
    assert Path(result["duckdb"]).exists()
    assert Path(result["blob_dir"]).exists()
    assert Path(result["logs_dir"]).exists()
    assert Path(tmp_path / "device_id.txt").exists()
