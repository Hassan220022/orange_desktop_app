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


def test_init_db_runs_without_error(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine, init_db
    engine = create_engine()
    init_db(engine)  # should not raise with stub models


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
