"""Tests for photo persistence service."""
import pytest
from dataclasses import dataclass
from datetime import date
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import BDTTest, BDTPhoto, BlobAsset
from alarm_app.db.repos.bdt_repo import save_bdt_test


@dataclass
class FakeSlot:
    image_data: bytes | None = None
    image_ext: str = "jpeg"
    category: str = "other"
    label: str = ""


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.repos.blob_repo.BLOB_DIR",
                        tmp_path / "blobs")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestPersistBdtPhotos:
    def test_stores_photos_and_links(self, session):
        from alarm_app.db.repos.photo_service import persist_bdt_photos

        bdt = save_bdt_test(
            session, {"site_code": "ABC", "test_date": date(2026, 1, 1)},
        )
        session.commit()

        slots = [
            FakeSlot(image_data=b"\x89PNG\r\nfake_rect", category="Rectifier"),
            FakeSlot(image_data=b"\x89PNG\r\nfake_batt", category="Battery"),
            FakeSlot(image_data=None, category="Module"),  # empty slot
        ]
        count = persist_bdt_photos(session, bdt.id, slots)
        assert count == 2  # 2 with data, 1 empty skipped

        photos = session.query(BDTPhoto).filter_by(bdt_test_id=bdt.id).all()
        assert len(photos) == 2
        assert photos[0].blob_asset_id is not None

    def test_deduplicates_identical_images(self, session):
        from alarm_app.db.repos.photo_service import persist_bdt_photos

        bdt1 = save_bdt_test(
            session, {"site_code": "A", "test_date": date(2026, 1, 1)},
        )
        bdt2 = save_bdt_test(
            session, {"site_code": "B", "test_date": date(2026, 2, 1)},
        )
        session.commit()

        same_image = b"\x89PNG\r\nsame_image_data"
        persist_bdt_photos(session, bdt1.id, [FakeSlot(image_data=same_image)])
        persist_bdt_photos(session, bdt2.id, [FakeSlot(image_data=same_image)])

        blobs = session.query(BlobAsset).all()
        assert len(blobs) == 1  # same image, one blob

    def test_empty_slots_ignored(self, session):
        from alarm_app.db.repos.photo_service import persist_bdt_photos

        bdt = save_bdt_test(
            session, {"site_code": "C", "test_date": date(2026, 3, 1)},
        )
        session.commit()

        slots = [FakeSlot(image_data=None)] * 5
        count = persist_bdt_photos(session, bdt.id, slots)
        assert count == 0

    def test_slot_index_matches_position(self, session):
        from alarm_app.db.repos.photo_service import persist_bdt_photos

        bdt = save_bdt_test(
            session, {"site_code": "D", "test_date": date(2026, 4, 1)},
        )
        session.commit()

        slots = [
            FakeSlot(image_data=None),            # index 0, skipped
            FakeSlot(image_data=b"img1"),          # index 1
            FakeSlot(image_data=None),            # index 2, skipped
            FakeSlot(image_data=b"img2"),          # index 3
        ]
        persist_bdt_photos(session, bdt.id, slots)

        photos = (
            session.query(BDTPhoto)
            .filter_by(bdt_test_id=bdt.id)
            .order_by(BDTPhoto.slot_index)
            .all()
        )
        assert [p.slot_index for p in photos] == [1, 3]

    def test_blob_written_to_disk(self, session, tmp_path):
        from alarm_app.db.repos.photo_service import persist_bdt_photos

        bdt = save_bdt_test(
            session, {"site_code": "E", "test_date": date(2026, 5, 1)},
        )
        session.commit()

        image_data = b"\x89PNG\r\ndisk_write_test"
        persist_bdt_photos(
            session, bdt.id, [FakeSlot(image_data=image_data)],
        )

        asset = session.query(BlobAsset).one()
        from pathlib import Path
        assert Path(asset.local_path).exists()
        assert Path(asset.local_path).read_bytes() == image_data
