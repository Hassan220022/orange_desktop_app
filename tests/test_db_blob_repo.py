"""Tests for db/repos/blob_repo.py."""
import pytest
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.blob_repo import store_blob, get_blob_by_sha256, blob_exists


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.repos.blob_repo.BLOB_DIR", tmp_path / "blobs")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestBlobRepo:
    def test_store_and_retrieve(self, session):
        data = b"\x89PNG\r\nfake_image_data"
        asset = store_blob(session, data, mime_type="image/png",
                           width=100, height=200)
        session.commit()
        assert asset.sha256 is not None
        assert asset.file_size == len(data)

        loaded = get_blob_by_sha256(session, asset.sha256)
        assert loaded is not None
        assert loaded.mime_type == "image/png"

    def test_duplicate_returns_existing(self, session):
        data = b"same_image"
        a1 = store_blob(session, data)
        session.commit()
        a2 = store_blob(session, data)
        assert a1.id == a2.id

    def test_blob_exists(self, session):
        data = b"test_blob"
        asset = store_blob(session, data)
        session.commit()
        assert blob_exists(session, asset.sha256) is True
        assert blob_exists(session, "nonexistent") is False

    def test_file_written_to_disk(self, session, tmp_path):
        data = b"disk_test_blob"
        asset = store_blob(session, data)
        session.commit()
        blob_path = tmp_path / "blobs" / asset.sha256[:2] / asset.sha256
        assert blob_path.exists()
        assert blob_path.read_bytes() == data
