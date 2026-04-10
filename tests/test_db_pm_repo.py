"""Tests for db/repos/pm_repo.py."""
import pytest
from datetime import date
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import BDTTest, PMValidationRun
from alarm_app.db.repos.pm_repo import save_validation_run, get_or_create_rule_catalog


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
        assert len(catalog) == 11
        assert "R1" in catalog
        assert "R11" in catalog

    def test_save_run_with_rules(self, session, bdt_test):
        rules = [
            {"rule_code": f"R{i}", "verdict": "Accepted", "detail": f"Rule {i} OK"}
            for i in range(1, 12)
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
        assert len(run.rule_results) == 11

    def test_idempotent_duplicate_returns_none(self, session, bdt_test):
        rules = [{"rule_code": f"R{i}", "verdict": "Accepted"} for i in range(1, 12)]
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
