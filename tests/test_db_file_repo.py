"""Tests for db/repos/file_repo.py."""
import pytest
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.file_repo import file_exists, get_file_by_hash, register_file


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestFileRepo:
    def test_file_not_exists_initially(self, session):
        assert file_exists(session, "abc123") is False

    def test_register_and_check_exists(self, session):
        register_file(session, file_sha256="abc123",
                      original_path="/tmp/x.csv", original_name="x.csv")
        session.commit()
        assert file_exists(session, "abc123") is True

    def test_register_duplicate_returns_existing(self, session):
        r1 = register_file(session, file_sha256="abc123",
                           original_path="/tmp/x.csv", original_name="x.csv")
        session.commit()
        r2 = register_file(session, file_sha256="abc123",
                           original_path="/tmp/y.csv", original_name="y.csv")
        assert r1.id == r2.id

    def test_get_file_by_hash(self, session):
        register_file(session, file_sha256="abc123",
                      original_path="/tmp/x.csv", original_name="x.csv",
                      source_kind="alarm_csv")
        session.commit()
        f = get_file_by_hash(session, "abc123")
        assert f is not None
        assert f.source_kind == "alarm_csv"

    def test_get_file_by_hash_missing(self, session):
        assert get_file_by_hash(session, "missing") is None
