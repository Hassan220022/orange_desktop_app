"""Tests for db/repos/catalog_repo.py."""

import json
from datetime import date

import pytest
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import BDTSummaryCatalog
from alarm_app.db.repos.catalog_repo import (
    delete_bdt_period,
    insert_bdt_rows,
    merge_bdt_period,
    query_site_metadata,
    replace_all_site_metadata,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestSiteMetadataRepo:
    def test_replace_all_and_query(self, session):
        rows = [
            {
                "site_id": "ABC123",
                "original_headers_json": json.dumps({"Code": "code", "Site Name": "site_name"}),
                "raw_data_json": json.dumps({"Code": "ABC123", "Site Name": "Test Site"}),
            },
            {
                "site_id": "XYZ456",
                "original_headers_json": json.dumps({"Code": "code", "Area": "area"}),
                "raw_data_json": json.dumps({"Code": "XYZ456", "Area": "North"}),
            },
        ]
        count = replace_all_site_metadata(session, rows)
        session.commit()
        assert count == 2

        result = query_site_metadata(session, "ABC123")
        assert result is not None
        assert result.site_id == "ABC123"
        raw = json.loads(result.raw_data_json)
        assert raw["Site Name"] == "Test Site"

    def test_replace_clears_previous(self, session):
        rows_a = [
            {
                "site_id": "S1",
                "original_headers_json": "{}",
                "raw_data_json": '{"a": 1}',
            },
        ]
        replace_all_site_metadata(session, rows_a)
        session.commit()

        rows_b = [
            {
                "site_id": "S2",
                "original_headers_json": "{}",
                "raw_data_json": '{"b": 2}',
            },
        ]
        replace_all_site_metadata(session, rows_b)
        session.commit()

        assert query_site_metadata(session, "S1") is None
        assert query_site_metadata(session, "S2") is not None

    def test_query_missing_returns_none(self, session):
        assert query_site_metadata(session, "NOPE") is None


class TestBDTSummaryRepo:
    def _make_bdt_row(
        self,
        site_id: str,
        period: str,
        week: str,
        test_date: date,
    ) -> dict:
        raw = {
            "site_id": site_id,
            "reporting_period": period,
            "week": week,
            "test_date": str(test_date),
            "test_year": test_date.year,
        }
        return {
            "site_id": site_id,
            "reporting_period": period,
            "week": week,
            "test_date": test_date,
            "test_year": test_date.year,
            "content_hash": f"hash_{site_id}_{period}_{week}",
            "original_headers_json": json.dumps({}),
            "raw_data_json": json.dumps(raw, default=str),
        }

    def test_delete_and_insert(self, session):
        rows = [
            self._make_bdt_row("S1", "W27-24", "W27", date(2024, 7, 1)),
            self._make_bdt_row("S2", "W27-24", "W27", date(2024, 7, 2)),
        ]
        insert_bdt_rows(session, rows)
        session.commit()

        all_rows = session.query(BDTSummaryCatalog).all()
        assert len(all_rows) == 2

        deleted = delete_bdt_period(session, "W27-24")
        assert deleted == 2
        session.commit()

        all_rows = session.query(BDTSummaryCatalog).all()
        assert len(all_rows) == 0

    def test_merge_replaces_period(self, session):
        # insert initial rows for two periods
        rows_a = [self._make_bdt_row("S1", "P1", "W1", date(2024, 1, 1))]
        rows_b = [self._make_bdt_row("S2", "P2", "W2", date(2024, 2, 1))]
        insert_bdt_rows(session, rows_a)
        insert_bdt_rows(session, rows_b)
        session.commit()

        # merge P1 with new data
        new_p1 = [
            self._make_bdt_row("S3", "P1", "W1", date(2024, 1, 3)),
            self._make_bdt_row("S4", "P1", "W1", date(2024, 1, 4)),
        ]
        merge_bdt_period(session, "P1", new_p1)
        session.commit()

        all_rows = session.query(BDTSummaryCatalog).all()
        # P2 should still have S2, P1 should now have S3 and S4
        site_ids = {r.site_id for r in all_rows}
        assert site_ids == {"S2", "S3", "S4"}

    def test_insert_duplicate_skipped(self, session):
        row = self._make_bdt_row("S1", "P1", "W1", date(2024, 1, 1))
        insert_bdt_rows(session, [row])
        session.commit()

        # same content_hash, site_id, period → unique constraint skips
        insert_bdt_rows(session, [row])
        session.commit()

        all_rows = session.query(BDTSummaryCatalog).all()
        assert len(all_rows) == 1
