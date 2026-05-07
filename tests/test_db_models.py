"""Tests for db/models.py — verify table creation and constraints."""
import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import (
    AlarmRecord,
    BDTTest,
    PMParameterSet,
    PMValidationRun,
    SyncOutboxEvent,
    UIState,
    UploadedFile,
)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    eng = create_engine()
    init_db(eng)
    return eng


def test_all_tables_created(engine):
    tables = inspect(engine).get_table_names()
    expected = [
        "uploaded_files", "alarm_records", "bdt_tests", "bdt_photos",
        "blob_assets", "pm_rule_catalog", "pm_rule_versions",
        "pm_rule_parameter_sets", "pm_validation_runs", "pm_rule_results",
        "ui_state", "review_events", "sync_outbox", "sync_checkpoints",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"


def test_alarm_record_row_hash_unique(engine):
    with Session(engine) as session:
        f = UploadedFile(file_sha256="abc123", original_path="/x", original_name="x.csv")
        session.add(f)
        session.flush()
        r1 = AlarmRecord(row_hash="hash1", site_id="S1", file_id=f.id)
        r2 = AlarmRecord(row_hash="hash1", site_id="S2", file_id=f.id)
        session.add(r1)
        session.flush()
        session.add(r2)
        with pytest.raises(IntegrityError):
            session.flush()


def test_pm_run_idempotency_constraint(engine):
    with Session(engine) as session:
        bdt = BDTTest(site_code="TEST", test_date=datetime.date(2026, 1, 1), content_hash="bdt_hash_1")
        session.add(bdt)
        ps = PMParameterSet(params_sha256="ps_hash_1", params_json='{"a": 1}')
        session.add(ps)
        session.flush()
        run1 = PMValidationRun(
            bdt_test_id=bdt.id, parameter_set_id=ps.id,
            alarm_input_sha256="alarm_hash", validator_code_ref="v1",
            overall_verdict="Accepted",
        )
        session.add(run1)
        session.flush()
        run2 = PMValidationRun(
            bdt_test_id=bdt.id, parameter_set_id=ps.id,
            alarm_input_sha256="alarm_hash", validator_code_ref="v1",
            overall_verdict="Accepted",
        )
        session.add(run2)
        with pytest.raises(IntegrityError):
            session.flush()


def test_ui_state_round_trip(engine):
    with Session(engine) as session:
        session.add(UIState(key="theme", value_json='"dark"'))
        session.commit()
    with Session(engine) as session:
        row = session.get(UIState, "theme")
        assert row is not None
        assert row.value_json == '"dark"'


def test_sync_outbox_event_id_unique(engine):
    with Session(engine) as session:
        e1 = SyncOutboxEvent(event_id="evt-1", entity_type="alarm", entity_local_id="1", op="upsert")
        e2 = SyncOutboxEvent(event_id="evt-1", entity_type="alarm", entity_local_id="2", op="upsert")
        session.add(e1)
        session.flush()
        session.add(e2)
        with pytest.raises(IntegrityError):
            session.flush()
