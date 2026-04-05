"""Comprehensive tests for alarm_app.bdt_validator (R1-R10)."""

from datetime import datetime

import pandas as pd

from alarm_app.bdt_parser import BDTData, PhotoSlot
from alarm_app.bdt_validator import (
    _rule_1_photos,
    _rule_2_power_alarm_match,
    _rule_3_string_vs_busbar,
    _rule_4_discharge_table,
    _rule_5_start_ampere,
    _rule_6_end_voltage,
    _rule_7_inverse_relationship,
    _rule_8_backup_time,
    _rule_9_discharge_current_tolerance,
    _rule_10_door_alarm_match,
    _rule_11_summary_checklist,
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
        summary_data={},
        num_batteries=None,
        num_modules=None,
        rectifier_brand="",
        pld_value="",
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


def _down_alarm(
    site_id: str = "SITE001",
    occurred: str = "2026-01-15 09:30:00",
    category: str = "Down",
    alarm_name: str = "Site Down",
    file_source: str = "down_alarms.csv",
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
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(),
            _door_alarm(),
        ])

        result = validate_bdt(bdt, alarm_df)

        assert [r.rule_id for r in result.rules] == [
            "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11"
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

    def test_overall_rejected_when_r10_no_door_alarm(self):
        bdt = _make_bdt(
            photo_slots=[
                _slot("Rectifier", "rectifier", b"img"),
                _slot("Batteries", "batteries", b"img"),
            ],
        )
        alarm_df = _make_alarm_df([_power_alarm()])  # no door alarm => R10 Rejected

        result = validate_bdt(bdt, alarm_df)
        assert any(r.rule_id == "R10" and r.verdict == "Rejected" for r in result.rules)
        assert result.overall == "Rejected"

    def test_overall_revise_when_only_na_and_accepted(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(photo_slots=slots, photo_count=16)
        # No alarm data -> alarm-dependent rules become N/A
        result = validate_bdt(bdt, None)
        assert any(r.verdict == "N/A" for r in result.rules)
        assert result.overall == "Revise"


# ── R1 Photos ────────────────────────────────────────────────────────────

class TestR1Photos:

    def test_all_16_photos_accepted(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(photo_slots=slots)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert r.passed is True

    def test_partial_photos_revise_even_if_categories_present(self):
        bdt = _make_bdt(photo_slots=[
            _slot("Rectifier 1", "rectifier", b"img"),
            _slot("Batteries 1", "batteries", b"img"),
        ], photo_count=16)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Revise"
        assert r.passed is False

    def test_slot_data_takes_precedence_over_photo_count(self):
        bdt = _make_bdt(photo_slots=[
            _slot("Rectifier 1", "rectifier", b"img"),
            _slot("Batteries 1", "batteries", None),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Revise"
        assert r.passed is False

    def test_no_filled_images_rejected(self):
        bdt = _make_bdt(photo_slots=[
            _slot("Rectifier 1", "rectifier", None),
            _slot("Batteries 1", "batteries", None),
        ], photo_count=0)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Rejected"
        assert r.passed is False

    def test_no_slots_fallback_photo_count(self):
        bdt = _make_bdt(photo_slots=[], photo_count=1)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Revise"
        assert r.passed is False

    def test_no_slots_fallback_photo_count_accepted_when_16(self):
        bdt = _make_bdt(photo_slots=[], photo_count=16)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert r.passed is True

    def test_16_photos_all_rectifier_no_batteries_revise(self):
        """16 photos but all rectifier category — missing batteries = Revise."""
        slots = [_slot(f"Slot {i+1}", "rectifier", b"img") for i in range(16)]
        bdt = _make_bdt(photo_slots=slots)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Revise"
        assert "missing category: batteries" in r.detail

    def test_16_photos_both_categories_accepted(self):
        """16 photos with both rectifier and batteries categories = Accepted."""
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 10 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(photo_slots=slots)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert "rectifier" in r.detail
        assert "batteries" in r.detail

    def test_deferred_photos_na(self):
        bdt = _make_bdt(photo_slots=[], photos_deferred=True)
        r = _rule_1_photos(bdt)
        assert r.verdict == "N/A"


# ── R2 Power Alarm + Duration ───────────────────────────────────────────

class TestR2PowerAlarmMatch:

    def test_time_match_within_five_minutes_accepted(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:04:00", cleared="2026-01-15 10:04:00")
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

    def test_ampm_time_format_accepted(self):
        """12-hour AM/PM format like '12:31:10PM' from real BDT files."""
        bdt = _make_bdt(
            time_in="12:31:10PM", time_out="2:31:10PM",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("90 min", 50.0, 30.8),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 12:31:00", cleared="2026-01-15 14:31:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_ampm_with_space_accepted(self):
        """12-hour AM/PM with space like '8:00:00 AM'."""
        bdt = _make_bdt(
            time_in="8:00:00 AM", time_out="10:00:00 AM",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("90 min", 50.0, 30.8),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:00", cleared="2026-01-15 10:00:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_outside_tolerance_rejected(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:11:00", cleared="2026-01-15 10:00:00")
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

    def test_power_to_down_path_accepted_when_clear_mismatch(self):
        bdt = _make_bdt(
            time_in="08:00",
            time_out="10:00",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.0),
                ("120 min", 49.0, 30.0),
                ("123 min", 48.9, 29.9),
            ],
            discharge_minutes=10.0,  # should be ignored by R2; max reached is 123
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:00", cleared="2026-01-15 09:20:00"),
            _down_alarm(occurred="2026-01-15 10:03:00"),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_duration_mismatch_rejected_even_with_start_end_match(self):
        bdt = _make_bdt(
            time_in="08:00",
            time_out="10:00",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.0),
                ("120 min", 49.0, 30.0),
            ],
            discharge_minutes=90.0,  # ignored in R2
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:09:00", cleared="2026-01-15 10:40:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert "duration" in r.detail.lower()

    def test_reject_when_max_reached_exceeds_180_minutes(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("120 min", 49.0, 30.0),
                ("180 min", 48.7, 29.8),
                ("210 min", 48.6, 29.7),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([_power_alarm()])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert "must not exceed 180 min" in r.detail

    def test_revise_when_no_reached_discharge_minute_found(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", None, None),
                ("60 min", None, None),
                ("90 min", None, None),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([_power_alarm()])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"
        assert "no reached minute found" in r.detail.lower()

    def test_revise_when_matched_power_has_no_end_event(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00", discharge_minutes=120.0)
        alarm_df = _make_alarm_df([{
            "site_id": "SITE001",
            "occurred_on": pd.Timestamp("2026-01-15 08:00:00"),
            "cleared_on": pd.NaT,
            "alarm_category": "Power",
            "alarm_name": "Mains Failure",
            "_duration_secs": None,
            "duration": None,
            "file_source": "power_alarms.csv",
        }])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"

    def test_uses_discharge_table_max_even_with_empty_trailing_rows(self):
        bdt = _make_bdt(
            time_in="08:00",
            discharge_readings=[
                ("10 Mins", 49.9, 25.0),
                ("30 Mins", 49.2, 25.5),
                ("60 Mins", 49.5, 25.5),
                ("90 Mins", 49.1, 25.5),
                ("120 Mins", 49.0, 25.8),
                ("150 Mins", 48.8, 25.8),
                ("180 Mins", 48.7, 25.8),
                ("210 Mins", None, None),
                ("240 Mins", None, None),
                ("270 Mins", None, None),
                ("300 Mins", None, None),
            ],
            discharge_minutes=300.0,  # ignored by R2
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:00", cleared="2026-01-15 11:00:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_duration_uses_discharge_table_not_checkin_time(self):
        """time_out - time_in = 330 min, discharge table max = 180 min.
        R2 uses discharge table max (180), not check-in duration (330)."""
        bdt = _make_bdt(
            time_in="11:00", time_out="16:30",
            discharge_readings=[
                ("10 Mins", 49.9, 25.0),
                ("30 Mins", 49.2, 25.5),
                ("180 Mins", 48.7, 25.8),
            ],
            discharge_minutes=180.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 11:00:00",
                         cleared="2026-01-15 14:00:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_batteries_with_duration_but_no_power_alarm_rejected(self):
        """Site has discharge data but no power alarm at all."""
        bdt = _make_bdt(discharge_minutes=120.0)
        alarm_df = _make_alarm_df([_door_alarm()])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert "No Power alarms" in r.detail

    def test_power_cleared_no_site_down_accepted(self):
        """Case A: Power alarm clears (grid restores), no Down alarm."""
        bdt = _make_bdt(time_in="08:00", time_out="11:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:00",
                         cleared="2026-01-15 10:05:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_variable_tolerance_override(self):
        """Custom tolerance overrides the constant."""
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:04:00",
                         cleared="2026-01-15 10:04:00")
        ])
        # With 3-minute tolerance, 4-minute offset should fail
        r = _rule_2_power_alarm_match(bdt, alarm_df, tol_override=3.0)
        assert r.verdict == "Rejected"
        # With 5-minute tolerance, 4-minute offset should pass
        r = _rule_2_power_alarm_match(bdt, alarm_df, tol_override=5.0)
        assert r.verdict == "Accepted"


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
        assert r.rule_name == "End Voltage Range"


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

    def test_non_lithium_is_evaluated_not_na(self):
        bdt = _make_bdt(
            battery_brand="Narada",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
            discharge_minutes=120.0,  # theoretical=120 with health_pct=0.80
        )
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"
        assert "Theoretical: 120" in r.detail

    def test_theoretical_over_180_requires_cap_reached_rejected(self):
        # theoretical = (100*48*1)/(48*30)*60 = 200 min (>180 cap)
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=30.0,
            discharge_minutes=170.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Rejected"
        assert "short by" in r.detail

    def test_theoretical_over_180_accepts_when_cap_reached(self):
        # theoretical = 200 min (>180 cap), actual reaches cap
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=30.0,
            discharge_minutes=180.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Accepted"
        assert "reached cap" in r.detail

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

    def test_missing_specs_rejected_not_na(self):
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=None,
            discharge_minutes=120.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Rejected"
        assert "Cannot compute theoretical duration" in r.detail


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

    def test_same_site_and_date_required_rejected(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(site_id="SITE999", occurred="2026-01-15 09:00:00"),
            _door_alarm(site_id="SITE001", occurred="2026-01-16 09:00:00"),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"


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


# ── R11 Summary Checklist ─────────────────────────────────────────────────

class TestR11SummaryChecklist:

    def test_all_fields_match_accepted(self):
        bdt = _make_bdt(
            site_code="0167DE",
            pld_value="44",
            rectifier_brand="Delta 2",
            num_modules=3,
            battery_brand="Lithium",
            battery_voltage=48.0,
            num_strings=2,
            num_batteries=2,
            start_voltage=54.10,
            start_ampere=23.30,
            end_voltage=48.70,
            end_ampere=25.80,
            discharge_minutes=180.0,
            test_date=datetime(2026, 1, 11),
            ibat_before_test=None,
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Battery Brand": "Lithium",
                "Battery Volt": "48",
                "No of String": "2",
                "No of Batteries": "2",
                "Start Volt": "54.10",
                "Start Amp": "23.30",
                "End Volt": "48.70",
                "End Amp": "25.80",
                "Discharge time( Mins)": "180",
                "Test Date": "2026-01-11",
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_no_summary_data_na(self):
        bdt = _make_bdt(summary_data={})
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "N/A"

    def test_one_mismatch_revise(self):
        bdt = _make_bdt(
            site_code="0167DE",
            battery_brand="Lithium",
            battery_voltage=None,
            num_strings=None,
            start_voltage=None,
            start_ampere=None,
            end_voltage=None,
            end_ampere=None,
            discharge_minutes=0.0,
            ibat_before_test=None,
            test_date=None,
            summary_data={
                "Short Code": "0167DE",
                "Battery Brand": "NARADA",  # mismatch
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Revise"
        assert "Battery Brand" in r.detail

    def test_four_mismatches_rejected(self):
        bdt = _make_bdt(
            site_code="0167DE",
            battery_brand="Lithium",
            num_strings=2,
            num_modules=3,
            start_voltage=54.0,
            summary_data={
                "Short Code": "WRONG",
                "Battery Brand": "WRONG",
                "No of String": "99",
                "# of Modules": "99",
                "Start Volt": "99.99",
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Rejected"

    def test_numeric_tolerance_applied(self):
        bdt = _make_bdt(
            site_code="",
            battery_brand="",
            battery_voltage=None,
            num_strings=None,
            start_voltage=54.10,
            start_ampere=None,
            end_voltage=None,
            end_ampere=None,
            discharge_minutes=0.0,
            ibat_before_test=None,
            test_date=None,
            summary_data={"Start Volt": "54.1"},
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_unit_suffixes_stripped(self):
        bdt = _make_bdt(
            site_code="",
            battery_brand="",
            battery_voltage=48.0,
            num_strings=None,
            start_voltage=None,
            start_ampere=None,
            end_voltage=None,
            end_ampere=None,
            discharge_minutes=0.0,
            ibat_before_test=None,
            test_date=None,
            summary_data={"Battery Volt": "48V"},
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_case_insensitive_match(self):
        bdt = _make_bdt(
            site_code="",
            battery_brand="zte",
            battery_voltage=None,
            num_strings=None,
            start_voltage=None,
            start_ampere=None,
            end_voltage=None,
            end_ampere=None,
            discharge_minutes=0.0,
            ibat_before_test=None,
            test_date=None,
            summary_data={"Battery Brand": "ZTE"},
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"


# ── R3 String vs Bus Bar Ampere ────────────────────────────────

class TestR3StringVsBusbar:
    """R3 tests match real parser output: string_discharge_readings[0] is the
    'Before disconnecting' row, discharge_readings starts at the first timed row.
    R3 slices off string_discharge_readings[0] to align the two lists."""

    def test_two_strings_within_tolerance_accepted(self):
        """Real pattern from 0167DE: string sums +0.9 to +1.8 above bus bar."""
        bdt = _make_bdt(
            discharge_readings=[
                ("10 Mins", 49.90, 25.00),
                ("30 Mins", 49.20, 25.50),
                ("180 Mins", 48.70, 25.80),
            ],
            string_discharge_readings=[
                [(53.90, 0.20), (54.10, 0.20)],      # Before (sliced off by R3)
                [(50.10, 12.70), (50.20, 14.10)],     # 10 min: sum=26.80, bus=25.00, diff=+1.80
                [(49.40, 14.50), (49.50, 12.80)],     # 30 min: sum=27.30, bus=25.50, diff=+1.80
                [(48.90, 13.90), (49.00, 12.80)],     # 180 min: sum=26.70, bus=25.80, diff=+0.90
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Accepted"

    def test_string_sum_3a_below_busbar_boundary_accepted(self):
        """Exactly -3.0 is the boundary -- should pass."""
        bdt = _make_bdt(
            discharge_readings=[
                ("30 Mins", 49.0, 30.0),
            ],
            string_discharge_readings=[
                [(54.0, 0.0), (54.0, 0.0)],           # Before (sliced off)
                [(49.0, 12.0), (49.0, 15.0)],          # sum=27.0, bus=30.0, diff=-3.0
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Accepted"

    def test_string_sum_more_than_3a_below_rejected(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 Mins", 49.0, 30.0),
            ],
            string_discharge_readings=[
                [(54.0, 0.0), (54.0, 0.0)],           # Before (sliced off)
                [(49.0, 12.0), (49.0, 14.0)],          # sum=26.0, bus=30.0, diff=-4.0
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Rejected"
        assert "-4.0" in r.detail or "-4.00" in r.detail

    def test_no_string_readings_na(self):
        bdt = _make_bdt(string_discharge_readings=[])
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "N/A"

    def test_high_load_site_accepted(self):
        """Real pattern from 3422DE: high load, diffs +1.3 to +4.1."""
        bdt = _make_bdt(
            discharge_readings=[
                ("10 Mins", 48.60, 66.10),
                ("60 Mins", 48.20, 73.10),
                ("160 Mins", 44.90, 75.90),
            ],
            string_discharge_readings=[
                [(54.50, 0.10), (52.50, 0.20)],        # Before (sliced off)
                [(49.00, 35.20), (49.00, 33.50)],      # sum=68.70, bus=66.10, diff=+2.60
                [(48.50, 37.40), (48.50, 39.10)],      # sum=76.50, bus=73.10, diff=+3.40
                [(45.10, 38.10), (45.40, 39.10)],      # sum=77.20, bus=75.90, diff=+1.30
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Accepted"

    def test_mixed_none_values_skipped(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 Mins", None, None),
                ("60 Mins", 49.0, 25.0),
            ],
            string_discharge_readings=[
                [(54.0, 0.0)],                          # Before (sliced off)
                [(None, None)],                         # skipped (None bus bar)
                [(49.0, 13.0)],                         # sum=13.0, bus=25.0, diff=-12.0
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Rejected"
