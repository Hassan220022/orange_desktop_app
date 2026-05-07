"""Tests for PM rule versioning and seeding."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from alarm_app.constants import BDT_RULES
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import BDTTest, PMRuleVersion
from alarm_app.db.repos.pm_repo import (
    get_or_create_parameter_set,
    load_validation_history,
    save_validation_run,
    seed_rule_versions,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestRuleVersioning:
    def test_seed_creates_11_versions(self, session):
        versions = session.query(PMRuleVersion).all()
        assert len(versions) == len(BDT_RULES)

    def test_seed_is_idempotent(self, session):
        seed_rule_versions(session)  # call again
        versions = session.query(PMRuleVersion).all()
        assert len(versions) == len(BDT_RULES)

    def test_versions_have_code_ref(self, session):
        versions = session.query(PMRuleVersion).all()
        for v in versions:
            assert v.code_ref.startswith("alarm_app.bdt.validator")


class TestParameterSets:
    def test_create_parameter_set(self, session):
        ps_id = get_or_create_parameter_set(session, {"tolerance": 0.1, "health_pct": 80})
        session.commit()
        assert ps_id > 0

    def test_same_params_same_id(self, session):
        p1 = get_or_create_parameter_set(session, {"a": 1, "b": 2})
        session.commit()
        p2 = get_or_create_parameter_set(session, {"b": 2, "a": 1})  # different key order
        assert p1 == p2  # canonical JSON hash is order-independent

    def test_different_params_different_id(self, session):
        p1 = get_or_create_parameter_set(session, {"tolerance": 0.1})
        session.commit()
        p2 = get_or_create_parameter_set(session, {"tolerance": 0.2})
        session.commit()
        assert p1 != p2


class TestValidationHistory:
    def test_load_history_empty(self, session):
        assert load_validation_history(session, "NOSITE") == []

    def test_load_history_returns_runs(self, session):
        bdt = BDTTest(site_code="HIST", test_date=date(2026, 1, 1), content_hash="h1")
        session.add(bdt)
        session.flush()

        rules = [{"rule_code": code, "verdict": "Accepted"} for code, _ in BDT_RULES]
        save_validation_run(session, bdt_test_id=bdt.id,
                            alarm_input_sha256="ah1", validator_code_ref="v1",
                            overall_verdict="Accepted", rule_results=rules)

        history = load_validation_history(session, "HIST")
        assert len(history) == 1
        assert history[0]["overall_verdict"] == "Accepted"
        assert history[0]["rule_count"] == len(BDT_RULES)
