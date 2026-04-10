"""Integration test: parse -> DB insert -> dedup -> reload."""
import pytest
import pandas as pd
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms, load_alarms_as_df, count_alarms
from alarm_app.db.repos.file_repo import file_exists, register_file
from alarm_app.db.hashing import compute_file_sha256


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


def _sample_df():
    return pd.DataFrame([
        {"site_id": "S1", "alarm_name": "Power Fail",
         "occurred_on": datetime(2026, 1, 1, 10, 0),
         "cleared_on": datetime(2026, 1, 1, 11, 0),
         "vendor": "Huawei", "_category": "Power",
         "duration": "01:00:00", "_duration_secs": 3600.0},
        {"site_id": "S2", "alarm_name": "Site Down",
         "occurred_on": datetime(2026, 1, 2, 8, 0),
         "cleared_on": datetime(2026, 1, 2, 9, 30),
         "vendor": "Nokia", "_category": "Down",
         "duration": "01:30:00", "_duration_secs": 5400.0},
    ])


class TestDedupIntegration:
    def test_file_level_dedup(self, session, tmp_path):
        f = tmp_path / "alarms.csv"
        f.write_text("site_id,alarm_name\nS1,Power")
        sha = compute_file_sha256(f)
        assert not file_exists(session, sha)
        register_file(session, file_sha256=sha, original_path=str(f),
                      original_name="alarms.csv", source_kind="alarm_csv")
        session.commit()
        assert file_exists(session, sha)

    def test_row_level_dedup(self, session):
        df = _sample_df()
        ins1, skip1 = bulk_upsert_alarms(session, df)
        assert ins1 == 2
        assert skip1 == 0
        ins2, skip2 = bulk_upsert_alarms(session, df)
        assert ins2 == 0
        assert skip2 == 2

    def test_round_trip_preserves_data(self, session):
        df = _sample_df()
        bulk_upsert_alarms(session, df)
        loaded = load_alarms_as_df(session)
        assert len(loaded) == 2
        assert set(loaded["site_id"]) == {"S1", "S2"}

    def test_mixed_new_and_duplicate(self, session):
        df1 = _sample_df()
        bulk_upsert_alarms(session, df1)
        df2 = pd.DataFrame([
            {"site_id": "S1", "alarm_name": "Power Fail",
             "occurred_on": datetime(2026, 1, 1, 10, 0),
             "cleared_on": datetime(2026, 1, 1, 11, 0),
             "vendor": "Huawei", "_category": "Power",
             "duration": "01:00:00", "_duration_secs": 3600.0},
            {"site_id": "S3", "alarm_name": "New Alarm",
             "occurred_on": datetime(2026, 1, 3),
             "vendor": "Huawei", "_category": "Unknown"},
        ])
        ins, skip = bulk_upsert_alarms(session, df2)
        assert ins == 1
        assert skip == 1
        assert count_alarms(session) == 3
