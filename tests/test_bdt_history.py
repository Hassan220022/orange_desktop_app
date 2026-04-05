"""Tests for alarm_app.bdt_history -- storage and comparison of BDT test records."""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pytest

from alarm_app.bdt_history import (
    BDTTestRecord,
    BDTComparison,
    save_test_record,
    load_previous_test,
    compare_tests,
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
    import alarm_app.bdt_history as mod
    monkeypatch.setattr(mod, "HISTORY_DIR", tmp_path)
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
