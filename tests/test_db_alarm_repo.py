"""Tests for db/repos/alarm_repo.py."""
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.alarm_repo import (
    _sqlite_max_multi_rows,
    bulk_upsert_alarms,
    count_alarms,
    load_alarms_as_df,
)
from alarm_app.db.repos.file_repo import register_file


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


def _make_df(rows):
    return pd.DataFrame(rows)


class TestAlarmRepo:
    def test_bulk_insert(self, session):
        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1),
             "cleared_on": datetime(2026, 1, 1, 1), "vendor": "Huawei",
             "_category": "Power", "duration": "01:00:00", "_duration_secs": 3600.0},
        ])
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 1
        assert skipped == 0

    def test_duplicate_rows_skipped(self, session):
        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1),
             "vendor": "Huawei", "_category": "Power"},
        ])
        bulk_upsert_alarms(session, df)
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 0
        assert skipped == 1

    def test_load_round_trip(self, session):
        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1),
             "vendor": "Huawei", "_category": "Power", "duration": "01:00:00",
             "_duration_secs": 3600.0},
            {"site_id": "S2", "alarm_name": "Down", "occurred_on": datetime(2026, 1, 2),
             "vendor": "Nokia", "_category": "Down", "duration": "00:30:00",
             "_duration_secs": 1800.0},
        ])
        bulk_upsert_alarms(session, df)
        loaded = load_alarms_as_df(session)
        assert len(loaded) == 2
        assert set(loaded["site_id"]) == {"S1", "S2"}

    def test_count_alarms(self, session):
        assert count_alarms(session) == 0
        df = _make_df([
            {"site_id": "S1", "alarm_name": "A1"},
            {"site_id": "S2", "alarm_name": "A2"},
        ])
        bulk_upsert_alarms(session, df)
        assert count_alarms(session) == 2

    def test_empty_df_returns_empty(self, session):
        loaded = load_alarms_as_df(session)
        assert loaded.empty

    def test_sqlite_multi_insert_chunk_uses_compile_option_limit(self, session, monkeypatch):
        engine = session.get_bind()

        class _FakeResult:
            def fetchall(self):
                return [("MAX_VARIABLE_NUMBER=32766",)]

        class _FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def exec_driver_sql(self, sql):
                assert sql == "PRAGMA compile_options"
                return _FakeResult()

        monkeypatch.setattr(engine, "connect", lambda: _FakeConn())
        assert _sqlite_max_multi_rows(engine, 18) == 1820

    def test_bulk_insert_uses_same_session_connection_as_pending_writes(self, session):
        register_file(
            session,
            file_sha256="pending-file-sha",
            original_path="/tmp/alarms.csv",
            original_name="alarms.csv",
            source_kind="alarm_csv",
        )

        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1)},
            {"site_id": "S2", "alarm_name": "Door", "occurred_on": datetime(2026, 1, 1, 0, 1)},
        ])

        inserted, skipped = bulk_upsert_alarms(session, df)

        assert inserted == 2
        assert skipped == 0
        session.commit()
        assert count_alarms(session) == 2
