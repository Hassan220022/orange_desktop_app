"""Tests for db/repos/state_repo.py."""
import pytest
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.state_repo import get_value, load_state, save_state, set_value


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestStateRepo:
    def test_save_and_load_round_trip(self, session):
        save_state(session, {"theme": "dark", "zoom": 120})
        result = load_state(session)
        assert result == {"theme": "dark", "zoom": 120}

    def test_load_empty_returns_none(self, session):
        assert load_state(session) is None

    def test_save_overwrites_existing(self, session):
        save_state(session, {"theme": "dark"})
        save_state(session, {"theme": "light"})
        result = load_state(session)
        assert result["theme"] == "light"

    def test_get_value(self, session):
        set_value(session, "zoom", 150)
        assert get_value(session, "zoom") == 150

    def test_get_value_missing_returns_default(self, session):
        assert get_value(session, "missing", "fallback") == "fallback"

    def test_set_value_overwrites(self, session):
        set_value(session, "zoom", 100)
        set_value(session, "zoom", 200)
        assert get_value(session, "zoom") == 200
