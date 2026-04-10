"""Tests for db/engine.py."""
import pytest
from sqlalchemy import text


def test_create_engine_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine
    engine = create_engine()

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_init_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    from alarm_app.db.engine import create_engine, init_db
    engine = create_engine()
    init_db(engine)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [r[0] for r in result]
        assert "alarm_records" in table_names
        assert "uploaded_files" in table_names
        assert "bdt_tests" in table_names
        assert "pm_validation_runs" in table_names
        assert "ui_state" in table_names
        assert "sync_outbox" in table_names
        assert "blob_assets" in table_names


def test_sqlite_wal_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine
    engine = create_engine()

    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert mode == "wal"


def test_sqlite_foreign_keys_on(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine
    engine = create_engine()

    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk == 1
