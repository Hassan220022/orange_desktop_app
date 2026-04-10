"""Tests for db/repos/alarm_repo.py."""
import pytest
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms, load_alarms_as_df, count_alarms


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
