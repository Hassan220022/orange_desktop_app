"""Tests for db/repos/pm_repo.py."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from alarm_app.constants import BDT_RULES
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import BDTTest, UploadedFile
from alarm_app.db.repos.pm_repo import (
    get_or_create_rule_catalog,
    load_all_validation_results,
    save_validation_run,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def bdt_test(session):
    bdt = BDTTest(site_code="TEST", test_date=date(2026, 1, 1),
                  content_hash="test_hash_1")
    session.add(bdt)
    session.flush()
    return bdt


class TestPMRepo:
    def test_get_or_create_catalog(self, session):
        catalog = get_or_create_rule_catalog(session)
        session.commit()
        assert len(catalog) == len(BDT_RULES)
        assert "R1" in catalog
        assert "R11" in catalog

    def test_save_run_with_rules(self, session, bdt_test):
        rules = [
            {"rule_code": code, "verdict": "Accepted", "detail": f"{code} OK"}
            for code, _ in BDT_RULES
        ]
        run = save_validation_run(
            session,
            bdt_test_id=bdt_test.id,
            alarm_input_sha256="alarm_hash_1",
            validator_code_ref="v1.0",
            overall_verdict="Accepted",
            rule_results=rules,
        )
        assert run is not None
        assert run.overall_verdict == "Accepted"
        assert len(run.rule_results) == len(BDT_RULES)

    def test_idempotent_duplicate_returns_none(self, session, bdt_test):
        rules = [{"rule_code": code, "verdict": "Accepted"} for code, _ in BDT_RULES]
        run1 = save_validation_run(
            session, bdt_test_id=bdt_test.id,
            alarm_input_sha256="alarm_hash_1",
            validator_code_ref="v1.0",
            overall_verdict="Accepted", rule_results=rules,
        )
        run2 = save_validation_run(
            session, bdt_test_id=bdt_test.id,
            alarm_input_sha256="alarm_hash_1",
            validator_code_ref="v1.0",
            overall_verdict="Accepted", rule_results=rules,
        )
        assert run1 is not None
        assert run2 is None

    def test_load_all_validation_results_restores_bdt_file_path(self, session):
        uploaded = UploadedFile(
            file_sha256="bdt_file_sha_1",
            original_path="/tmp/original_test_bdt.xlsx",
            original_name="original_test_bdt.xlsx",
            source_kind="bdt_xlsx",
        )
        session.add(uploaded)
        session.flush()

        bdt = BDTTest(
            site_code="TEST",
            test_date=date(2026, 1, 1),
            content_hash="test_hash_with_file",
            file_id=uploaded.id,
        )
        session.add(bdt)
        session.flush()

        rules = [{"rule_code": code, "verdict": "Accepted", "detail": f"{code} OK"} for code, _ in BDT_RULES]
        save_validation_run(
            session,
            bdt_test_id=bdt.id,
            alarm_input_sha256="alarm_hash_with_file",
            validator_code_ref="v1.0",
            overall_verdict="Accepted",
            rule_results=rules,
        )

        results = load_all_validation_results(session)
        assert len(results) == 1
        assert results[0].filename == "original_test_bdt.xlsx"
        assert results[0].bdt_data is not None
        assert results[0].bdt_data.file_path == "/tmp/original_test_bdt.xlsx"
        assert results[0].rules[0].rule_id == "R1"
        assert results[0].rules[0].rule_name == "Photos"
