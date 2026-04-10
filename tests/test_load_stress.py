"""Load and stress tests for the DB layer."""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms, load_alarms_as_df, count_alarms
from alarm_app.db.repos.file_repo import register_file, file_exists
from alarm_app.db.repos.sync_repo import append_outbox_event, load_pending_outbox
from alarm_app.db.hashing import compute_row_hash


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


def _generate_alarms(n: int, site_prefix: str = "SITE") -> pd.DataFrame:
    """Generate n alarm records with unique site/time combinations."""
    base = datetime(2026, 1, 1)
    rows = []
    for i in range(n):
        rows.append({
            "site_id": f"{site_prefix}-{i % 100:03d}",
            "alarm_name": f"Alarm-{i % 10}",
            "occurred_on": base + timedelta(minutes=i),
            "cleared_on": base + timedelta(minutes=i, hours=1),
            "vendor": "Huawei" if i % 2 == 0 else "Nokia",
            "_category": ["Power", "Down", "Door", "Unknown"][i % 4],
            "duration": "01:00:00",
            "_duration_secs": 3600.0,
        })
    return pd.DataFrame(rows)


class TestBulkInsertPerformance:
    def test_insert_1000_alarms(self, session):
        df = _generate_alarms(1000)
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 1000
        assert skipped == 0
        assert count_alarms(session) == 1000

    def test_insert_5000_alarms(self, session):
        df = _generate_alarms(5000)
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 5000
        assert count_alarms(session) == 5000

    def test_reload_5000_alarms_as_df(self, session):
        df = _generate_alarms(5000)
        bulk_upsert_alarms(session, df)
        loaded = load_alarms_as_df(session)
        assert len(loaded) == 5000
        assert "site_id" in loaded.columns

    def test_dedup_on_reingest_5000(self, session):
        df = _generate_alarms(5000)
        bulk_upsert_alarms(session, df)
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 0
        assert skipped == 5000
        assert count_alarms(session) == 5000


class TestConcurrentFileRegistration:
    def test_register_100_files(self, session):
        for i in range(100):
            register_file(session, file_sha256=f"sha-{i:04d}",
                          original_path=f"/data/file_{i}.csv",
                          original_name=f"file_{i}.csv",
                          source_kind="alarm_csv")
        session.commit()
        for i in range(100):
            assert file_exists(session, f"sha-{i:04d}")

    def test_duplicate_files_not_double_counted(self, session):
        for _ in range(10):
            register_file(session, file_sha256="same-hash",
                          original_path="/data/a.csv",
                          original_name="a.csv")
        session.commit()
        from alarm_app.db.models import UploadedFile
        count = session.query(UploadedFile).filter_by(file_sha256="same-hash").count()
        assert count == 1


class TestOutboxScale:
    def test_append_500_events(self, session):
        for i in range(500):
            append_outbox_event(session, entity_type="alarm_record",
                                entity_local_id=str(i), op="upsert",
                                entity_hash=f"h{i}", payload={"i": i})
        pending = load_pending_outbox(session)
        assert len(pending) == 500

    def test_load_pending_with_limit(self, session):
        for i in range(200):
            append_outbox_event(session, entity_type="alarm_record",
                                entity_local_id=str(i), op="upsert",
                                entity_hash=f"h{i}", payload={})
        batch = load_pending_outbox(session, limit=50)
        assert len(batch) == 50


class TestMalformedData:
    def test_null_site_id_still_inserts(self, session):
        df = pd.DataFrame([{
            "site_id": None, "alarm_name": "Power",
            "occurred_on": datetime(2026, 1, 1),
        }])
        inserted, _ = bulk_upsert_alarms(session, df)
        assert inserted == 1

    def test_empty_dataframe_no_crash(self, session):
        df = pd.DataFrame()
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 0
        assert skipped == 0

    def test_missing_columns_no_crash(self, session):
        df = pd.DataFrame([{"site_id": "S1"}])
        inserted, _ = bulk_upsert_alarms(session, df)
        assert inserted == 1

    def test_nat_dates_handled(self, session):
        df = pd.DataFrame([{
            "site_id": "S1", "alarm_name": "Test",
            "occurred_on": pd.NaT, "cleared_on": pd.NaT,
        }])
        inserted, _ = bulk_upsert_alarms(session, df)
        assert inserted == 1
