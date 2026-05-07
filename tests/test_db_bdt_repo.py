"""Tests for db/repos/bdt_repo.py."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import UploadedFile
from alarm_app.db.repos.bdt_repo import load_previous_test, save_bdt_photo, save_bdt_test


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestBDTRepo:
    def test_save_and_dedup(self, session):
        bdt = {"site_code": "ABC", "test_date": date(2026, 1, 1),
               "battery_brand": "Narada", "battery_ah": 200}
        r1 = save_bdt_test(session, bdt)
        session.commit()
        r2 = save_bdt_test(session, bdt)
        assert r1.id == r2.id

    def test_different_tests_different_records(self, session):
        b1 = {"site_code": "ABC", "test_date": date(2026, 1, 1),
              "battery_brand": "Narada"}
        b2 = {"site_code": "ABC", "test_date": date(2026, 6, 1),
              "battery_brand": "Narada"}
        r1 = save_bdt_test(session, b1)
        session.commit()
        r2 = save_bdt_test(session, b2)
        session.commit()
        assert r1.id != r2.id

    def test_load_previous_test(self, session):
        save_bdt_test(session, {"site_code": "ABC", "test_date": date(2025, 6, 1),
                                "battery_brand": "X"})
        save_bdt_test(session, {"site_code": "ABC", "test_date": date(2026, 1, 1),
                                "battery_brand": "Y"})
        session.commit()

        prev = load_previous_test(session, "ABC", date(2026, 1, 1))
        assert prev is not None
        assert prev.test_date == date(2025, 6, 1)

    def test_load_previous_test_none(self, session):
        assert load_previous_test(session, "XYZ", date(2026, 1, 1)) is None

    def test_duplicate_backfills_missing_file_id(self, session):
        file_row = UploadedFile(
            file_sha256="file_sha_1",
            original_path="/tmp/test_bdt.xlsx",
            original_name="test_bdt.xlsx",
        )
        session.add(file_row)
        session.flush()

        first = save_bdt_test(session, {
            "site_code": "ABC",
            "test_date": date(2026, 1, 1),
            "battery_brand": "Narada",
        })
        assert first.file_id is None

        second = save_bdt_test(session, {
            "site_code": "ABC",
            "test_date": date(2026, 1, 1),
            "battery_brand": "Narada",
        }, file_id=file_row.id)
        assert second.id == first.id
        assert second.file_id == file_row.id

    def test_save_photo(self, session):
        bdt = save_bdt_test(session, {"site_code": "ABC",
                                       "test_date": date(2026, 1, 1)})
        session.commit()
        photo = save_bdt_photo(session, bdt.id, slot_index=0,
                               slot_category="Rectifier")
        session.commit()
        assert photo.bdt_test_id == bdt.id
        assert photo.slot_category == "Rectifier"
