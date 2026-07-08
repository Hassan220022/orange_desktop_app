"""Tests for alarm_app.bdt_history -- storage and comparison of BDT test records."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy.exc import OperationalError

from alarm_app.bdt.history import (
    BDTTestRecord,
    compare_tests,
    compute_alarm_input_sha256,
    load_previous_test,
    save_test_record,
    save_validation_batch,
    save_validation_run,
)
from alarm_app.bdt.parser import PhotoSlot
from alarm_app.constants import BDT_RULES


@dataclass
class _FakeBDT:
    """Minimal BDTData stand-in for history tests."""
    site_code: str = "TEST01"
    test_date: datetime | None = None
    file_path: str = "/fake/test.xlsx"
    battery_brand: str = "Lithium"
    battery_ah: float | None = 100.0
    battery_voltage: float | None = 48.0
    num_strings: int | None = 2
    num_batteries: int | None = 2
    num_modules: int | None = 3
    rectifier_brand: str = "Delta 2"


@pytest.fixture
def history_dir(tmp_path, monkeypatch):
    """Redirect HISTORY_DIR to a temp directory and wire up a fresh DB."""
    import alarm_app.bdt.history as mod
    monkeypatch.setattr(mod, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(mod, "PM_RUNS_DIR", tmp_path / "_pm_runs")
    monkeypatch.setattr(mod, "PM_RULE_RESULTS_DIR", tmp_path / "_pm_rule_results")
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.engine._app_engine", None)
    monkeypatch.setattr("alarm_app.db.engine._app_session_factory", None)
    monkeypatch.setattr("alarm_app.data.state._engine", None)
    monkeypatch.setattr("alarm_app.data.state._SessionFactory", None)
    return tmp_path


class TestSaveAndLoad:

    def test_save_creates_record_in_db(self, history_dir):
        bdt = _FakeBDT(site_code="0167DE", test_date=datetime(2026, 1, 11))
        save_test_record(bdt, "Accepted")

        result = load_previous_test("0167DE", date(2026, 1, 12))
        assert result is not None
        assert result.site_code == "0167DE"
        assert result.battery_brand == "Lithium"
        assert result.test_date == "2026-01-11"

    def test_load_finds_most_recent_before_date(self, history_dir):
        for d, brand in [("2025-06-15", "Narada"), ("2025-12-01", "Lithium")]:
            bdt = _FakeBDT(
                site_code="0167DE",
                test_date=datetime.fromisoformat(d),
                battery_brand=brand,
            )
            save_test_record(bdt, "Accepted")

        result = load_previous_test("0167DE", date(2026, 1, 11))
        assert result is not None
        assert result.test_date == "2025-12-01"
        assert result.battery_brand == "Lithium"

    def test_load_returns_none_when_no_history(self, history_dir):
        result = load_previous_test("NOSITE", date(2026, 1, 1))
        assert result is None

    def test_load_skips_future_dates(self, history_dir):
        bdt = _FakeBDT(
            site_code="0167DE",
            test_date=datetime(2026, 6, 1),
            battery_brand="X",
        )
        save_test_record(bdt, "Accepted")

        result = load_previous_test("0167DE", date(2026, 1, 1))
        assert result is None

    def test_missing_site_code_not_saved(self, history_dir):
        bdt = _FakeBDT(site_code="", test_date=datetime(2026, 1, 1))
        save_test_record(bdt, "Accepted")
        # Nothing stored — load returns None
        result = load_previous_test("", date(2026, 1, 2))
        assert result is None


class TestCompareTests:

    def _make_previous(self, **overrides):
        defaults = {
            "site_code": "0167DE", "test_date": "2025-06-15", "file_path": "/old.xlsx",
            "battery_brand": "Lithium", "battery_ah": 100, "battery_voltage": 48,
            "num_strings": 2, "num_batteries": 2, "num_modules": 3,
            "rectifier_brand": "Delta 2", "overall_verdict": "Accepted",
            "saved_at": "2025-06-15T00:00:00",
        }
        defaults.update(overrides)
        return BDTTestRecord(**defaults)

    def test_identical_tests_no_differences(self):
        bdt = _FakeBDT(test_date=datetime(2026, 1, 11))
        prev = self._make_previous()
        comp = compare_tests(bdt, prev)
        assert comp.differences == []
        assert comp.has_critical_change is False

    def test_battery_brand_changed_flagged_critical(self):
        bdt = _FakeBDT(test_date=datetime(2026, 1, 11), battery_brand="Narada")
        prev = self._make_previous(battery_brand="Lithium")
        comp = compare_tests(bdt, prev)
        assert comp.has_critical_change is True
        assert any("Battery Brand" in d for d in comp.differences)

    def test_num_batteries_changed_flagged_critical(self):
        bdt = _FakeBDT(test_date=datetime(2026, 1, 11), num_batteries=4)
        prev = self._make_previous(num_batteries=2)
        comp = compare_tests(bdt, prev)
        assert comp.has_critical_change is True

    def test_rectifier_changed_flagged_critical(self):
        bdt = _FakeBDT(test_date=datetime(2026, 1, 11), rectifier_brand="Huawei")
        prev = self._make_previous(rectifier_brand="Delta 2")
        comp = compare_tests(bdt, prev)
        assert comp.has_critical_change is True

    def test_num_modules_changed_flagged_critical(self):
        bdt = _FakeBDT(test_date=datetime(2026, 1, 11), num_modules=5)
        prev = self._make_previous(num_modules=3)
        comp = compare_tests(bdt, prev)
        assert comp.has_critical_change is True

    def test_voltage_change_not_critical(self):
        bdt = _FakeBDT(test_date=datetime(2026, 1, 11), battery_voltage=52.0)
        prev = self._make_previous(battery_voltage=48)
        comp = compare_tests(bdt, prev)
        assert comp.has_critical_change is False
        assert any("Battery Voltage" in d for d in comp.differences)

    def test_lead_acid_to_lithium_upgrade_is_classified_not_raw_mismatch_noise(self):
        bdt = _FakeBDT(
            test_date=datetime(2026, 4, 1),
            battery_brand="Lithium-Huawei",
            battery_ah=100,
            battery_voltage=48,
            num_strings=3,
            num_batteries=3,
            num_modules=4,
            rectifier_brand="Huawei",
        )
        prev = self._make_previous(
            test_date="2024-05-26",
            battery_brand="SBS",
            battery_ah=170,
            battery_voltage=12,
            num_strings=4,
            num_batteries=16,
            num_modules=6,
            rectifier_brand="Delta 2",
        )

        comp = compare_tests(bdt, prev)

        assert comp.has_critical_change is True
        assert comp.upgrade_detected is True
        assert comp.change_status == "Battery Technology Upgrade Detected"
        assert any("Lead-acid to lithium upgrade" in d for d in comp.differences)
        assert any("previous string voltage 48V" in d for d in comp.differences)
        assert not any(d.startswith("Battery Voltage: 12") for d in comp.differences)


class TestValidationRunPersistence:
    @staticmethod
    def _make_validation_result(verdict="Accepted"):
        class _Rule:
            def __init__(self, rid):
                self.rule_id = rid
                self.rule_name = f"Rule {rid}"
                self.verdict = verdict
                self.detail = f"detail-{rid}"
                self.passed = True

        class _Res:
            overall = verdict
            rules = [_Rule(code) for code, _ in BDT_RULES]

        return _Res()

    def test_save_validation_run_persists_metadata_and_rule_rows(self, history_dir):
        bdt = _FakeBDT(site_code="0167DE", test_date=datetime(2026, 1, 11))
        result = self._make_validation_result()
        alarm_df = pd.DataFrame(
            [{
                "site_id": "0167DE",
                "alarm_name": "Power alarm",
                "alarm_id": "1001",
                "occurred_on": "2026-01-11 08:00:00",
                "cleared_on": "2026-01-11 10:00:00",
            }]
        )

        run = save_validation_run(
            bdt_data=bdt,
            validation_result=result,
            alarm_df=alarm_df,
            params={"tolerance": 0.15, "health_pct": 0.80},
        )

        assert run is not None
        assert run["site_code"] == "0167DE"
        assert run["rule_count"] == len(BDT_RULES)
        assert run["is_complete_rule_set"] is True

    def test_save_validation_run_is_idempotent_for_same_inputs(self, history_dir):
        bdt = _FakeBDT(site_code="0167DE", test_date=datetime(2026, 1, 11))
        result = self._make_validation_result()
        alarm_df = pd.DataFrame([{"site_id": "0167DE", "occurred_on": "2026-01-11 09:00:00"}])

        first = save_validation_run(
            bdt_data=bdt,
            validation_result=result,
            alarm_df=alarm_df,
            params={"tolerance": 0.15, "health_pct": 0.80},
        )
        second = save_validation_run(
            bdt_data=bdt,
            validation_result=result,
            alarm_df=alarm_df,
            params={"tolerance": 0.15, "health_pct": 0.80},
        )

        assert first is not None and second is not None
        assert first["idempotency_key"] == second["idempotency_key"]
        assert first["run_id"] == second["run_id"]

    def test_save_validation_batch_retries_sqlite_lock_once(self, history_dir, monkeypatch):
        import alarm_app.bdt.history as history_module

        bdt = _FakeBDT(
            site_code="0167DE",
            test_date=datetime(2026, 1, 11),
            file_path=str(history_dir / "retry-bdt.xlsx"),
        )
        Path(bdt.file_path).write_bytes(b"fake")

        result = self._make_validation_result()
        alarm_df = pd.DataFrame([{"site_id": "0167DE", "occurred_on": "2026-01-11 09:00:00"}])

        original_register = history_module._register_bdt_uploaded_file
        calls = {"count": 0}

        def _flaky_register(session, bdt_data):
            calls["count"] += 1
            if calls["count"] == 1:
                raise OperationalError(
                    "INSERT INTO uploaded_files ...",
                    {},
                    Exception("database is locked"),
                )
            return original_register(session, bdt_data)

        monkeypatch.setattr(history_module, "_register_bdt_uploaded_file", _flaky_register)
        monkeypatch.setattr(history_module.time, "sleep", lambda _seconds: None)

        run_payloads, photo_jobs, failed_items = save_validation_batch(
            items=[{"bdt_data": bdt, "validation_result": result}],
            alarm_df=alarm_df,
            params={"tolerance": 0.15, "health_pct": 0.80},
        )

        assert calls["count"] == 2
        assert len(run_payloads) == 1
        assert photo_jobs == []
        assert failed_items == []

    def test_save_validation_batch_queues_photo_copy_and_clears_source_bytes(self, history_dir):
        slot = PhotoSlot(
            label="Rectifier",
            image_data=b"photo-bytes",
            image_ext="jpg",
            category="rectifier",
        )
        bdt = _FakeBDT(
            site_code="0167DE",
            test_date=datetime(2026, 1, 11),
            file_path=str(history_dir / "photo-bdt.xlsx"),
        )
        bdt.photo_slots = [slot]
        Path(bdt.file_path).write_bytes(b"fake")

        result = self._make_validation_result()
        alarm_df = pd.DataFrame([{"site_id": "0167DE", "occurred_on": "2026-01-11 09:00:00"}])

        run_payloads, photo_jobs, failed_items = save_validation_batch(
            items=[{"bdt_data": bdt, "validation_result": result}],
            alarm_df=alarm_df,
            params={"tolerance": 0.15, "health_pct": 0.80},
        )

        assert len(run_payloads) == 1
        assert failed_items == []
        assert len(photo_jobs) == 1
        queued_slot = photo_jobs[0]["photo_slots"][0]
        assert queued_slot is not slot
        assert queued_slot.image_data == b"photo-bytes"
        assert slot.image_data is None

    def test_compute_alarm_input_sha256_deterministic(self):
        df_a = pd.DataFrame(
            [
                {"site_id": "0167DE", "alarm_id": "2", "occurred_on": "2026-01-11 10:00:00"},
                {"site_id": "0167DE", "alarm_id": "1", "occurred_on": "2026-01-11 09:00:00"},
            ]
        )
        df_b = pd.DataFrame(
            [
                {"site_id": "0167DE", "alarm_id": "1", "occurred_on": "2026-01-11 09:00:00"},
                {"site_id": "0167DE", "alarm_id": "2", "occurred_on": "2026-01-11 10:00:00"},
            ]
        )

        h1 = compute_alarm_input_sha256(df_a, "0167DE", "2026-01-11")
        h2 = compute_alarm_input_sha256(df_b, "0167DE", "2026-01-11")
        assert h1 == h2
