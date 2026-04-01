"""Comprehensive tests for alarm_app.bdt_validator (R1-R10)."""

from datetime import datetime

import pandas as pd

from alarm_app.bdt_parser import BDTData, PhotoSlot
from alarm_app.bdt_validator import (
    _rule_1_photos,
    _rule_2_power_alarm_match,
    _rule_3_duration_match,
    _rule_4_discharge_table,
    _rule_5_start_ampere,
    _rule_6_end_voltage,
    _rule_7_inverse_relationship,
    _rule_8_backup_time,
    _rule_9_discharge_current_tolerance,
    _rule_10_door_alarm_match,
    _theoretical_backup_minutes,
    validate_bdt,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _slot(label: str, category: str | None, image_data: bytes | None) -> PhotoSlot:
    slot = PhotoSlot(label=label, image_data=image_data)
    if category is not None:
        # Parser provides this field in production; attach dynamically for tests.
        setattr(slot, "category", category)
    return slot


def _make_bdt(**kwargs) -> BDTData:
    defaults = dict(
        file_path="tests/fixtures/test.xlsx",
        filename="test.xlsx",
        site_code="SITE001",
        site_name="Test Site",
        test_date=datetime(2026, 1, 15),
        time_in="08:00",
        time_out="10:00",
        discharge_readings=[
            ("30 min", 52.0, 30.0),
            ("60 min", 51.0, 30.5),
            ("90 min", 50.0, 30.8),
            ("120 min", 46.0, 31.0),
        ],
        start_voltage=48.0,
        start_ampere=40.0,
        end_voltage=46.0,
        end_ampere=31.0,
        discharge_minutes=120.0,
        ibat_before_test=0.2,
        battery_brand="Narada",
        battery_ah=100.0,
        battery_voltage=48.0,
        num_strings=1,
        photo_count=2,
        photo_slots=[],
        photos_deferred=False,
        errors=[],
    )
    defaults.update(kwargs)
    return BDTData(**defaults)


def _make_alarm_df(rows: list[dict]) -> pd.DataFrame:
    cols = [
        "site_id",
        "occurred_on",
        "cleared_on",
        "alarm_category",
        "alarm_name",
        "_duration_secs",
        "duration",
        "file_source",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for col in cols:
        if col not in df.columns:
            df[col] = None
    return df[cols]


def _power_alarm(
    site_id: str = "SITE001",
    occurred: str = "2026-01-15 08:00:00",
    cleared: str = "2026-01-15 10:00:00",
    category: str = "Power",
    alarm_name: str = "Mains Failure",
    file_source: str = "power_alarms.csv",
) -> dict:
    occ = pd.Timestamp(occurred)
    clr = pd.Timestamp(cleared)
    secs = max((clr - occ).total_seconds(), 0)
    hrs = int(secs // 3600)
    mins = int((secs % 3600) // 60)
    sec = int(secs % 60)
    return {
        "site_id": site_id,
        "occurred_on": occ,
        "cleared_on": clr,
        "alarm_category": category,
        "alarm_name": alarm_name,
        "_duration_secs": secs,
        "duration": f"{hrs:02d}:{mins:02d}:{sec:02d}",
        "file_source": file_source,
    }


def _door_alarm(
    site_id: str = "SITE001",
    occurred: str = "2026-01-15 09:00:00",
    category: str = "Door",
    alarm_name: str = "Door Open",
    file_source: str = "door_alarms.csv",
) -> dict:
    return {
        "site_id": site_id,
        "occurred_on": pd.Timestamp(occurred),
        "cleared_on": pd.Timestamp(occurred) + pd.Timedelta(minutes=1),
        "alarm_category": category,
        "alarm_name": alarm_name,
        "_duration_secs": 60.0,
        "duration": "00:01:00",
        "file_source": file_source,
    }


# ── validate_bdt overall ─────────────────────────────────────────────────

class TestValidateBDTOverall:

    def test_rules_appended_in_order_and_overall_accepted(self):
        bdt = _make_bdt(
            photo_slots=[
                _slot("Rectifier Photo", "rectifier", b"img"),
                _slot("Batteries Photo", "batteries", b"img"),
            ],
        )
        alarm_df = _make_alarm_df([
            _power_alarm(),
            _door_alarm(),
        ])

        result = validate_bdt(bdt, alarm_df)

        assert [r.rule_id for r in result.rules] == [
            "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"
        ]
        assert result.overall == "Accepted"

    def test_overall_rejected_when_any_rule_rejected(self):
        bdt = _make_bdt(
            photo_slots=[
                _slot("Rectifier", "rectifier", b"img"),
                _slot("Batteries", "batteries", b"img"),
            ],
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 32.2),  # >1A from baseline => R9 reject
                ("90 min", 50.0, 31.0),
            ],
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(bdt, alarm_df)
        assert result.overall == "Rejected"

    def test_overall_revise_when_no_reject_and_one_revise(self):
        bdt = _make_bdt(
            photo_slots=[
                _slot("Rectifier", "rectifier", b"img"),
                _slot("Batteries", "batteries", b"img"),
            ],
        )
        alarm_df = _make_alarm_df([_power_alarm()])  # no door alarm => R10 Revise

        result = validate_bdt(bdt, alarm_df)
        assert any(r.rule_id == "R10" and r.verdict == "Revise" for r in result.rules)
        assert result.overall == "Revise"


# ── R1 Photos ────────────────────────────────────────────────────────────

class TestR1Photos:

    def test_required_categories_filled_accepted(self):
        bdt = _make_bdt(photo_slots=[
            _slot("Rectifier 1", "rectifier", b"img"),
            _slot("Batteries 1", "batteries", b"img"),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert r.passed is True

    def test_missing_required_category_revise(self):
        bdt = _make_bdt(photo_slots=[
            _slot("Rectifier 1", "rectifier", b"img"),
            _slot("Batteries 1", "batteries", None),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Revise"
        assert "Batteries" in r.detail

    def test_no_filled_images_rejected(self):
        bdt = _make_bdt(photo_slots=[
            _slot("Rectifier 1", "rectifier", None),
            _slot("Batteries 1", "batteries", None),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Rejected"
        assert r.passed is False

    def test_no_slots_fallback_photo_count(self):
        bdt = _make_bdt(photo_slots=[], photo_count=1)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"

    def test_deferred_photos_na(self):
        bdt = _make_bdt(photo_slots=[], photos_deferred=True)
        r = _rule_1_photos(bdt)
        assert r.verdict == "N/A"


# ── R2 Power Alarm Match ────────────────────────────────────────────────

class TestR2PowerAlarmMatch:

    def test_time_match_within_five_minutes_accepted(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:04:00", cleared="2026-01-15 09:56:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_time_match_hhmmss_format_accepted(self):
        bdt = _make_bdt(time_in="08:00:30", time_out="10:00:30")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:30", cleared="2026-01-15 10:00:30")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_outside_tolerance_rejected(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:06:00", cleared="2026-01-15 10:00:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"

    def test_invalid_test_times_revise(self):
        bdt = _make_bdt(time_in="invalid", time_out="10:00")
        alarm_df = _make_alarm_df([_power_alarm()])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"
        assert "time_in" in r.detail

    def test_no_alarm_data_na(self):
        bdt = _make_bdt()
        r = _rule_2_power_alarm_match(bdt, None)
        assert r.verdict == "N/A"

    def test_no_power_same_site_date_rejected(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _power_alarm(site_id="SITE999"),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"


# ── R3 Duration Match ───────────────────────────────────────────────────

class TestR3DurationMatch:

    def test_duration_within_tolerance_accepted(self):
        bdt = _make_bdt(discharge_minutes=120.0)
        alarm_df = _make_alarm_df([_power_alarm()])  # 120 min
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Accepted"

    def test_duration_outside_tolerance_rejected(self):
        bdt = _make_bdt(discharge_minutes=120.0)
        alarm_df = _make_alarm_df([
            _power_alarm(cleared="2026-01-15 09:00:00")  # 60 min
        ])
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Rejected"


# ── R4 Discharge Table ──────────────────────────────────────────────────

class TestR4DischargeTable:

    def test_discharge_table_matches_accepted(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.4),
                ("120 min", 46.0, 30.9),
            ],
            discharge_minutes=120.0,
        )
        r = _rule_4_discharge_table(bdt, tolerance=0.15)
        assert r.verdict == "Accepted"

    def test_discharge_table_empty_revise(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", None, None),
                ("60 min", None, None),
            ],
            discharge_minutes=60.0,
        )
        r = _rule_4_discharge_table(bdt, tolerance=0.15)
        assert r.verdict == "Revise"


# ── R5 Starting I-Battery ───────────────────────────────────────────────

class TestR5StartAmpere:

    def test_approx_zero_accepted_with_updated_wording(self):
        bdt = _make_bdt(ibat_before_test=0.4)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Accepted"
        assert r.rule_name == "Starting I-Battery ampere"
        assert "approximate 0A threshold" in r.detail

    def test_threshold_boundary_rejected(self):
        bdt = _make_bdt(ibat_before_test=0.5)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Rejected"

    def test_missing_value_na(self):
        bdt = _make_bdt(ibat_before_test=None)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "N/A"


# ── R6 Completion OR rule ───────────────────────────────────────────────

class TestR6CompletionOrRule:

    def test_discharge_180_or_more_accepts_even_if_voltage_outside(self):
        bdt = _make_bdt(discharge_minutes=180.0, end_voltage=48.5)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"

    def test_voltage_in_range_accepts_even_if_duration_short(self):
        bdt = _make_bdt(discharge_minutes=120.0, end_voltage=46.2)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"

    def test_both_conditions_fail_rejected(self):
        bdt = _make_bdt(discharge_minutes=120.0, end_voltage=44.8)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"

    def test_missing_end_voltage_na(self):
        bdt = _make_bdt(end_voltage=None)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "N/A"


# ── R7 Inverse relationship ─────────────────────────────────────────────

class TestR7InverseRelationship:

    def test_inverse_correlation_accepted_with_updated_detail(self):
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 52.0, 28.0),
            ("60 min", 50.0, 29.5),
            ("90 min", 48.0, 31.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "Accepted"
        assert "expected inverse trend" in r.detail

    def test_direct_correlation_rejected_with_updated_detail(self):
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 46.0, 28.0),
            ("60 min", 48.0, 30.0),
            ("90 min", 50.0, 32.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "Rejected"
        assert "unexpected direct trend" in r.detail


# ── R8 Sizing vs Actual ─────────────────────────────────────────────────

class TestR8SizingVsActual:

    def test_non_lithium_na(self):
        bdt = _make_bdt(battery_brand="Narada", discharge_minutes=120.0)
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "N/A"
        assert "not lithium" in r.detail.lower()

    def test_health_pct_outside_range_na(self):
        bdt = _make_bdt(battery_brand="Lithium", discharge_minutes=120.0)
        r = _rule_8_backup_time(bdt, health_pct=0.90)
        assert r.verdict == "N/A"
        assert "health_pct" in r.detail

    def test_actual_180_or_more_na(self):
        bdt = _make_bdt(battery_brand="Lithium", discharge_minutes=180.0)
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "N/A"
        assert "requires <180" in r.detail

    def test_abs_difference_within_15_accepted(self):
        # theoretical = (100*48*1)/(48*40)*60 = 150 min; actual = 135, diff=15
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
            discharge_minutes=135.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Accepted"

    def test_abs_difference_above_15_rejected(self):
        # theoretical = 150 min; actual = 130, diff=20
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
            discharge_minutes=130.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Rejected"

    def test_missing_specs_na(self):
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=None,
            discharge_minutes=120.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "N/A"


# ── R9 Discharge current tolerance ──────────────────────────────────────

class TestR9DischargeCurrentTolerance:

    def test_within_plus_minus_one_amp_accepted(self):
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 52.0, 30.0),
            ("60 min", 51.0, 31.0),  # boundary
            ("90 min", 50.0, 29.1),
        ])
        r = _rule_9_discharge_current_tolerance(bdt)
        assert r.verdict == "Accepted"

    def test_above_one_amp_rejected(self):
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 52.0, 30.0),
            ("60 min", 51.0, 31.2),
            ("90 min", 50.0, 30.2),
        ])
        r = _rule_9_discharge_current_tolerance(bdt)
        assert r.verdict == "Rejected"
        assert "|Δ|" in r.detail

    def test_insufficient_readings_na(self):
        bdt = _make_bdt(discharge_readings=[("30 min", 52.0, 30.0)])
        r = _rule_9_discharge_current_tolerance(bdt)
        assert r.verdict == "N/A"


# ── R10 Door alarm condition ────────────────────────────────────────────

class TestR10DoorAlarmCondition:

    def test_no_alarm_data_na(self):
        bdt = _make_bdt()
        r = _rule_10_door_alarm_match(bdt, None)
        assert r.verdict == "N/A"

    def test_detect_by_alarm_category_accepted(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([_door_alarm(category="Door", alarm_name="X", file_source="misc.csv")])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_detect_by_alarm_name_accepted(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(category="Security", alarm_name="Main Door Open", file_source="misc.csv")
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_detect_by_file_source_accepted(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(category="Security", alarm_name="Other", file_source="door_events.csv")
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_same_site_and_date_required_revise(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(site_id="SITE999", occurred="2026-01-15 09:00:00"),
            _door_alarm(site_id="SITE001", occurred="2026-01-16 09:00:00"),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"


# ── Helper behavior remains valid ───────────────────────────────────────

class TestTheoreticalBackupMinutes:

    def test_lithium_uses_efficiency_one(self):
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
        )
        result = _theoretical_backup_minutes(bdt, health_pct=0.50)
        expected = (100 * 48 * 1 * 1.0) / (48 * 40) * 60
        assert result is not None
        assert abs(result - expected) < 0.01

    def test_missing_load_returns_none(self):
        bdt = _make_bdt(start_voltage=None, start_ampere=40.0)
        assert _theoretical_backup_minutes(bdt, health_pct=0.95) is None
