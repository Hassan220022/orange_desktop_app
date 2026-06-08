"""E2E tests for the BDT validation pipeline: parse -> validate -> persist -> load back."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

try:
    from alarm_app.bdt.history import (
        load_previous_test,
        persist_photo_jobs,
        save_test_record,
        save_validation_batch,
    )
    from alarm_app.bdt.parser import parse_bdt_file
    from alarm_app.bdt.validator import BDTTolerances, validate_bdt
    from alarm_app.db.engine import create_engine, get_session_factory, init_db
    from alarm_app.db.models import BDTTest
    from alarm_app.db.repos.pm_repo import load_all_validation_results
except ImportError:
    from bdt.history import (
        load_previous_test,
        persist_photo_jobs,
        save_test_record,
        save_validation_batch,
    )
    from bdt.parser import parse_bdt_file
    from bdt.validator import BDTTolerances, validate_bdt
    from db.engine import create_engine, get_session_factory, init_db
    from db.models import BDTTest
    from db.repos.pm_repo import load_all_validation_results

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    import alarm_app.data.state as state_mod
    import alarm_app.db.engine as engine_mod

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(engine_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(engine_mod, "DB_PATH", db_path)
    engine_mod._app_engine = None
    engine_mod._app_session_factory = None
    state_mod._engine = None
    state_mod._SessionFactory = None

    engine = create_engine()
    init_db(engine)
    engine_mod._app_engine = engine
    engine_mod._app_session_factory = get_session_factory(engine)

    session = engine_mod._app_session_factory()
    yield session
    session.close()


class TestBDTParseToPersistToLoadE2E:

    def test_parse_real_bdt_file_and_persist(self, isolated_db):
        session = isolated_db
        filepath = FIXTURES_DIR / "bdt_layout_a_16photo.xlsx"
        assert filepath.is_file(), f"Fixture missing: {filepath}"

        bdt_data = parse_bdt_file(str(filepath), skip_photos=True)
        assert bdt_data.site_code, "site_code should be populated"
        assert bdt_data.battery_brand, "battery_brand should be populated"
        assert bdt_data.test_date is not None, "test_date should be populated"

        save_test_record(bdt_data, "Accepted")

        if isinstance(bdt_data.test_date, datetime):
            before_date = (bdt_data.test_date + timedelta(days=1)).date()
        elif isinstance(bdt_data.test_date, date):
            before_date = bdt_data.test_date + timedelta(days=1)
        else:
            before_date = date(2099, 1, 1)

        record = load_previous_test(bdt_data.site_code, before_date)
        assert record is not None, "Record should be loaded back from DB"
        assert record.site_code == bdt_data.site_code
        assert record.battery_brand == bdt_data.battery_brand
        if isinstance(bdt_data.test_date, datetime):
            assert record.test_date == bdt_data.test_date.strftime("%Y-%m-%d")
        else:
            assert record.test_date == str(bdt_data.test_date)

        bdt_test = session.query(BDTTest).filter_by(
            site_code=bdt_data.site_code
        ).first()
        assert bdt_test is not None, "BDTTest row should exist in DB"
        assert bdt_test.content_hash, "content_hash should be populated"

    def test_full_validation_pipeline(self, isolated_db):
        session = isolated_db
        filepath = FIXTURES_DIR / "bdt_layout_b.xlsx"
        assert filepath.is_file(), f"Fixture missing: {filepath}"

        bdt_data = parse_bdt_file(str(filepath), skip_photos=True)
        assert bdt_data.errors == [] or not any(
            "Missing" in e for e in bdt_data.errors
        ), f"Parse errors: {bdt_data.errors}"

        result = validate_bdt(
            bdt_data,
            alarm_df=None,
            tolerances=BDTTolerances.defaults(),
            health_pct=80,
        )
        assert result is not None
        assert result.rules, "Validation should produce rule results"

        run_payloads, _photo_jobs, failed = save_validation_batch(
            items=[{"bdt_data": bdt_data, "validation_result": result}],
            alarm_df=None,
            params={},
            validator_code_ref="test_e2e",
        )
        assert len(run_payloads) == 1, "One run payload expected"
        assert failed == [], f"Unexpected failures: {failed}"

        results = load_all_validation_results(session)
        assert len(results) > 0, "Should load at least one validation result"

        for vr in results:
            assert vr.filename, "filename should be populated"
            assert vr.site_code, "site_code should be populated"
            assert vr.test_date, "test_date should be populated"
            assert vr.overall in ("Accepted", "Rejected", "Revise"), f"Unexpected verdict: {vr.overall}"
            assert vr.rules, "rules should be populated"


    def test_validation_db_roundtrip_preserves_insight_and_battery_status(self, isolated_db):
        from alarm_app.bdt.parser import BDTData
        from alarm_app.bdt.validator import RuleResult, ValidationResult, bdt_battery_status

        bdt_data = BDTData(
            file_path="/tmp/roundtrip_bdt.xlsx",
            filename="roundtrip_bdt.xlsx",
            site_code="RT001",
            site_name="Round Trip Site",
            test_date=datetime(2026, 4, 2),
            battery_brand="",
            num_batteries=None,
            num_strings=0,
            summary_data={"No. of Batteries": "0"},
            photo_count=0,
        )
        result = ValidationResult(
            filename="roundtrip_bdt.xlsx",
            site_code="RT001",
            test_date="2026-04-02",
            overall="Rejected",
            rules=[RuleResult("R1", "Photos", False, "Rejected", "No photos embedded in file")],
            bdt_data=bdt_data,
            battery_backup_insight={
                "insight_status": "Network Summary / BDT Mismatch",
                "severity": "high",
                "insight_flags": ["network_bdt_mismatch"],
            },
            validation_context={
                "validation_mode": "component_check_no_backup_battery",
                "display_overall": "Accepted (component check - no backup battery)",
            },
        )

        run_payloads, _photo_jobs, failed = save_validation_batch(
            items=[{"bdt_data": bdt_data, "validation_result": result}],
            alarm_df=None,
            params={},
            validator_code_ref="test_roundtrip",
        )
        assert len(run_payloads) == 1
        assert failed == []

        loaded = load_all_validation_results(isolated_db)
        assert len(loaded) == 1
        loaded_result = loaded[0]

        assert loaded_result.battery_backup_insight["insight_status"] == "Network Summary / BDT Mismatch"
        assert loaded_result.battery_backup_insight["severity"] == "high"
        assert loaded_result.validation_context["validation_mode"] == "component_check_no_backup_battery"
        assert loaded_result.validation_context["display_overall"] == "Accepted (component check - no backup battery)"
        assert bdt_battery_status(loaded_result.bdt_data) == "No Battery"

    def test_photo_persistence_and_load(self, isolated_db):
        session = isolated_db
        filepath = FIXTURES_DIR / "bdt_real_3938ca.xlsx"
        assert filepath.is_file(), f"Fixture missing: {filepath}"

        bdt_data = parse_bdt_file(str(filepath), skip_photos=False)
        assert (
            sum(1 for s in bdt_data.photo_slots if s.image_data) > 0
        ), "Fixture should have embedded photos"

        result = validate_bdt(
            bdt_data,
            alarm_df=None,
            tolerances=BDTTolerances.defaults(),
            health_pct=80,
        )

        run_payloads, photo_jobs, failed = save_validation_batch(
            items=[{"bdt_data": bdt_data, "validation_result": result}],
            alarm_df=None,
            params={},
            validator_code_ref="test_e2e",
        )
        assert len(run_payloads) == 1

        assert photo_jobs, "Photo jobs should be queued for this fixture"
        persisted_count = persist_photo_jobs(photo_jobs)
        assert persisted_count > 0, "Photos should be persisted"

        results = load_all_validation_results(session)
        assert len(results) > 0, "Should load at least one validation result"

        for vr in results:
            if vr.bdt_data is None:
                continue
            assert vr.bdt_data.photo_slots, "photo_slots should be populated"
            photo_count = getattr(vr.bdt_data, "photo_count", 0)
            filled = sum(
                1 for s in vr.bdt_data.photo_slots
                if getattr(s, "image_path", "")
            )
            total = max(photo_count, filled)
            assert total > 0, "At least some photo slots should be filled"
