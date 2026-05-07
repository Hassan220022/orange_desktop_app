"""Tests for data/bootstrap.py — bootstrap backfill of outbox events."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from alarm_app.data.bootstrap import (
    bootstrap_alarm_records,
    bootstrap_bdt_tests,
    bootstrap_validation_runs,
    run_bootstrap,
)
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import (
    AlarmRecord,
    BDTTest,
    PMValidationRun,
    SyncOutboxEvent,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.data.state._engine", None)
    monkeypatch.setattr("alarm_app.data.state._SessionFactory", None)
    monkeypatch.setattr("alarm_app.data.state.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.data.state.DEVICE_ID_FILE", tmp_path / "device_id.txt")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestBootstrapAlarms:
    def test_queues_unsynced_records(self, session):
        session.add(AlarmRecord(row_hash="h1", site_id="S1"))
        session.add(AlarmRecord(row_hash="h2", site_id="S2"))
        session.commit()

        count = bootstrap_alarm_records(session)
        assert count == 2

        events = (
            session.query(SyncOutboxEvent)
            .filter_by(entity_type="alarm_record")
            .count()
        )
        assert events == 2

    def test_skips_already_synced(self, session):
        session.add(AlarmRecord(row_hash="h1", site_id="S1"))
        session.commit()

        record = session.query(AlarmRecord).first()
        session.add(
            SyncOutboxEvent(
                event_id="existing",
                entity_type="alarm_record",
                entity_local_id=str(record.id),
                op="upsert",
            )
        )
        session.commit()

        count = bootstrap_alarm_records(session)
        assert count == 0

    def test_empty_table_returns_zero(self, session):
        assert bootstrap_alarm_records(session) == 0


class TestBootstrapBDT:
    def test_queues_unsynced_tests(self, session):
        session.add(
            BDTTest(site_code="A", test_date=date(2026, 1, 1), content_hash="ch1")
        )
        session.commit()

        count = bootstrap_bdt_tests(session)
        assert count == 1

    def test_skips_already_synced(self, session):
        session.add(
            BDTTest(site_code="B", test_date=date(2026, 2, 1), content_hash="ch2")
        )
        session.commit()

        test_row = session.query(BDTTest).first()
        session.add(
            SyncOutboxEvent(
                event_id="existing-bdt",
                entity_type="bdt_test",
                entity_local_id=str(test_row.id),
                op="upsert",
            )
        )
        session.commit()

        count = bootstrap_bdt_tests(session)
        assert count == 0


class TestBootstrapValidationRuns:
    def test_queues_unsynced_runs(self, session):
        bdt = BDTTest(site_code="C", test_date=date(2026, 3, 1), content_hash="ch3")
        session.add(bdt)
        session.flush()

        session.add(
            PMValidationRun(
                bdt_test_id=bdt.id,
                alarm_input_sha256="abc123",
                overall_verdict="pass",
            )
        )
        session.commit()

        count = bootstrap_validation_runs(session)
        assert count == 1

    def test_empty_table_returns_zero(self, session):
        assert bootstrap_validation_runs(session) == 0


class TestRunBootstrap:
    def test_full_bootstrap(self, session):
        session.add(AlarmRecord(row_hash="h1", site_id="S1"))
        session.add(
            BDTTest(site_code="A", test_date=date(2026, 1, 1), content_hash="ch1")
        )
        session.commit()

        counts = run_bootstrap(session)
        assert counts["alarm_records"] == 1
        assert counts["bdt_tests"] == 1
        assert counts["validation_runs"] == 0

    def test_idempotent_on_rerun(self, session):
        session.add(AlarmRecord(row_hash="h1", site_id="S1"))
        session.commit()

        run_bootstrap(session)
        counts = run_bootstrap(session)
        assert counts["alarm_records"] == 0  # already queued
        assert counts["bdt_tests"] == 0
        assert counts["validation_runs"] == 0
