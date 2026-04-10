"""Tests for alarm_app.bdt_history -- storage and comparison of BDT test records."""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from alarm_app.bdt.history import (
    BDTTestRecord,
    BDTComparison,
    save_test_record,
    load_previous_test,
    compare_tests,
    save_validation_run,
    compute_alarm_input_sha256,
    HISTORY_DIR,
)


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
    """Redirect HISTORY_DIR to a temp directory."""
    import alarm_app.bdt.history as mod
    monkeypatch.setattr(mod, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(mod, "PM_RUNS_DIR", tmp_path / "_pm_runs")
    monkeypatch.setattr(mod, "PM_RULE_RESULTS_DIR", tmp_path / "_pm_rule_results")
    return tmp_path


class TestSaveAndLoad:

    def test_save_creates_json_file(self, history_dir):
        bdt = _FakeBDT(site_code="0167DE", test_date=datetime(2026, 1, 11))
        save_test_record(bdt, "Accepted")

        site_dir = history_dir / "0167DE"
        assert site_dir.exists()
        files = list(site_dir.glob("*.json"))
        assert len(files) == 1
        assert files[0].name == "2026-01-11.json"

        data = json.loads(files[0].read_text())
        assert data["site_code"] == "0167DE"
        assert data["battery_brand"] == "Lithium"
        assert data["overall_verdict"] == "Accepted"

    def test_load_finds_most_recent_before_date(self, history_dir):
        site_dir = history_dir / "0167DE"
        site_dir.mkdir()

        for d, brand in [("2025-06-15", "Narada"), ("2025-12-01", "Lithium")]:
            rec = BDTTestRecord(
                site_code="0167DE", test_date=d, file_path="/fake/f.xlsx",
                battery_brand=brand, battery_ah=100, battery_voltage=48,
                num_strings=2, num_batteries=2, num_modules=3,
                rectifier_brand="Delta 2", overall_verdict="Accepted",
                saved_at="2026-01-01T00:00:00",
            )
            (site_dir / f"{d}.json").write_text(
                json.dumps(rec.__dict__, default=str))

        result = load_previous_test("0167DE", date(2026, 1, 11))
        assert result is not None
        assert result.test_date == "2025-12-01"
        assert result.battery_brand == "Lithium"

    def test_load_returns_none_when_no_history(self, history_dir):
        result = load_previous_test("NOSITE", date(2026, 1, 1))
        assert result is None

    def test_load_skips_future_dates(self, history_dir):
        site_dir = history_dir / "0167DE"
        site_dir.mkdir()

        rec = BDTTestRecord(
            site_code="0167DE", test_date="2026-06-01", file_path="/f.xlsx",
            battery_brand="X", battery_ah=100, battery_voltage=48,
            num_strings=2, num_batteries=2, num_modules=3,
            rectifier_brand="Delta 2", overall_verdict="Accepted",
            saved_at="2026-06-01T00:00:00",
        )
        (site_dir / "2026-06-01.json").write_text(
            json.dumps(rec.__dict__, default=str))

        result = load_previous_test("0167DE", date(2026, 1, 1))
        assert result is None

    def test_missing_site_code_not_saved(self, history_dir):
        bdt = _FakeBDT(site_code="", test_date=datetime(2026, 1, 1))
        save_test_record(bdt, "Accepted")
        assert not any(history_dir.iterdir())


class TestCompareTests:

    def _make_previous(self, **overrides):
        defaults = dict(
            site_code="0167DE", test_date="2025-06-15", file_path="/old.xlsx",
            battery_brand="Lithium", battery_ah=100, battery_voltage=48,
            num_strings=2, num_batteries=2, num_modules=3,
            rectifier_brand="Delta 2", overall_verdict="Accepted",
            saved_at="2025-06-15T00:00:00",
        )
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
            rules = [_Rule(f"R{i}") for i in range(1, 12)]

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
        assert run["rule_count"] == 11
        assert run["is_complete_rule_set"] is True

        import alarm_app.bdt.history as mod
        run_path = mod.PM_RUNS_DIR / f"{run['idempotency_key']}.json"
        assert run_path.exists()

        rule_rows_path = mod.PM_RULE_RESULTS_DIR / f"{run['run_id']}.jsonl"
        assert rule_rows_path.exists()
        rows = [json.loads(line) for line in rule_rows_path.read_text().splitlines() if line.strip()]
        assert len(rows) == 11
        assert rows[0]["run_id"] == run["run_id"]

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

        import alarm_app.bdt.history as mod
        run_files = list(mod.PM_RUNS_DIR.glob("*.json"))
        rules_files = list(mod.PM_RULE_RESULTS_DIR.glob("*.jsonl"))
        assert len(run_files) == 1
        assert len(rules_files) == 1

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
