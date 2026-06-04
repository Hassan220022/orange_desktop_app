"""Tests for the persistence-layer engine factory."""

import pytest

from services.persistence import engine as engine_module


@pytest.fixture
def temp_state_dir(tmp_path, monkeypatch):
    """Redirect STATE_DIR to a temp directory for the test."""
    monkeypatch.setattr(engine_module, "STATE_DIR", tmp_path)
    return tmp_path


def test_default_engine_is_sqlite(temp_state_dir):
    """With no URL override, engine uses local SQLite under STATE_DIR."""
    eng = engine_module.create_engine()
    assert eng.dialect.name == "sqlite"
    db_file = temp_state_dir / "alarm_viewer.db"
    # SQLAlchemy creates the file lazily on first connection; force a
    # connection so the file actually exists for the assertion below.
    with eng.connect() as conn:
        from sqlalchemy import text
        conn.execute(text("SELECT 1"))
    assert db_file.exists()
    assert str(db_file) in str(eng.url)
    eng.dispose()


def test_engine_sets_sqlite_pragmas(temp_state_dir):
    """WAL journal mode and foreign keys must be enabled on connect."""
    eng = engine_module.create_engine()
    try:
        with eng.connect() as conn:
            from sqlalchemy import text

            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert mode.lower() == "wal"
        assert int(fk) == 1
    finally:
        eng.dispose()


def test_get_app_engine_is_singleton(temp_state_dir):
    """Repeated calls return the same engine instance."""
    # Reset the singleton state so this test is hermetic
    engine_module._app_engine = None
    engine_module._app_session_factory = None
    a = engine_module.get_app_engine()
    b = engine_module.get_app_engine()
    assert a is b
    a.dispose()
    engine_module._app_engine = None
    engine_module._app_session_factory = None
