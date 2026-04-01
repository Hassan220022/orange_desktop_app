"""
Comprehensive tests for alarm_app.bdt_validator.

Covers all 8 validation rules (R1-R8), the overall validate_bdt()
orchestration, and the _theoretical_backup_minutes() helper.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from alarm_app.bdt_parser import BDTData, PhotoSlot
from alarm_app.bdt_validator import (
    validate_bdt,
    _rule_1_photos,
    _rule_2_power_alarm_match,
    _rule_3_duration_match,
    _rule_4_discharge_table,
    _rule_5_start_ampere,
    _rule_6_end_voltage,
    _rule_7_inverse_relationship,
    _rule_8_backup_time,
    _theoretical_backup_minutes,
)


# ── Helpers ──────────────────────────────────────────────────

def _make_bdt(**kwargs) -> BDTData:
    """Build a BDTData with sensible defaults, overridable via kwargs."""
    defaults = dict(
        file_path="/tmp/test.xlsx",
        filename="test.xlsx",
        site_code="SITE001",
        site_name="Test Site",
        test_date=datetime(2026, 1, 15),
        discharge_minutes=120.0,
        start_voltage=52.0,
        start_ampere=30.0,
        end_voltage=46.0,
        end_ampere=35.0,
        ibat_before_test=0.2,
        battery_brand="Narada",
        battery_ah=200.0,
        battery_voltage=48.0,
        num_strings=2,
        photo_count=5,
        photo_slots=[],
        photos_deferred=False,
        discharge_readings=[],
        errors=[],
    )
    defaults.update(kwargs)
    return BDTData(**defaults)


def _make_alarm_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal alarm DataFrame from a list of row dicts."""
    cols = [
        "site_id", "occurred_on", "cleared_on",
        "alarm_category", "_duration_secs", "duration", "file_source",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def _power_alarm(site_id: str, occurred: str, duration_secs: float,
                 file_source: str = "power_alarms.csv") -> dict:
    """Convenience: build one Power alarm row dict."""
    occ = pd.Timestamp(occurred)
    secs = duration_secs
    hrs = int(secs // 3600)
    mins = int((secs % 3600) // 60)
    sec = int(secs % 60)
    return dict(
        site_id=site_id,
        occurred_on=occ,
        cleared_on=occ + pd.Timedelta(seconds=secs),
        alarm_category="Power",
        _duration_secs=secs,
        duration=f"{hrs:02d}:{mins:02d}:{sec:02d}",
        file_source=file_source,
    )


# ── 1. validate_bdt() overall ───────────────────────────────

class TestValidateBDTOverall:

    def test_all_rules_pass_accepted(self):
        """When every rule passes, overall should be Accepted."""
        bdt = _make_bdt(
            photo_count=5,
            photo_slots=[
                PhotoSlot(label="A", image_data=b"img"),
                PhotoSlot(label="B", image_data=b"img"),
            ],
            discharge_readings=[
                ("30 min", 51.0, 31.0),
                ("60 min", 50.0, 32.0),
                ("90 min", 49.0, 33.0),
                ("120 min", 46.0, 35.0),
            ],
            discharge_minutes=120.0,
            end_voltage=46.0,
            ibat_before_test=0.2,
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            battery_brand="Narada",
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 7200.0),
        ])
        result = validate_bdt(bdt, alarm_df)
        assert result.overall == "Accepted"

    def test_one_rejected_overall_rejected(self):
        """If any rule is Rejected, overall should be Rejected."""
        bdt = _make_bdt(
            photo_count=0,
            photo_slots=[],
            discharge_readings=[
                ("30 min", 51.0, 31.0),
                ("60 min", 50.0, 32.0),
                ("90 min", 49.0, 33.0),
                ("120 min", 46.0, 35.0),
            ],
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 7200.0),
        ])
        result = validate_bdt(bdt, alarm_df)
        assert result.overall == "Rejected"

    def test_no_reject_one_revise_overall_revise(self):
        """If no Rejected but at least one Revise, overall should be Revise."""
        bdt = _make_bdt(
            photo_slots=[
                PhotoSlot(label="A", image_data=b"img"),
                PhotoSlot(label="B", image_data=None),
            ],
            discharge_readings=[
                ("30 min", 51.0, 31.0),
                ("60 min", 50.0, 32.0),
                ("90 min", 49.0, 33.0),
                ("120 min", 46.0, 35.0),
            ],
            discharge_minutes=120.0,
            end_voltage=46.0,
            ibat_before_test=0.2,
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 7200.0),
        ])
        result = validate_bdt(bdt, alarm_df)
        # R1 should be Revise (partial photos)
        r1 = next(r for r in result.rules if r.rule_id == "R1")
        assert r1.verdict == "Revise"
        # Make sure nothing else is Rejected that would override
        rejects = [r for r in result.rules if r.verdict == "Rejected"]
        if not rejects:
            assert result.overall == "Revise"

    def test_no_alarm_data_r2_r3_na(self):
        """R2 and R3 return N/A when alarm data is None."""
        bdt = _make_bdt()
        result = validate_bdt(bdt, None)
        r2 = next(r for r in result.rules if r.rule_id == "R2")
        r3 = next(r for r in result.rules if r.rule_id == "R3")
        assert r2.verdict == "N/A"
        assert r3.verdict == "N/A"


# ── 2. R1 Photos ────────────────────────────────────────────

class TestR1Photos:

    def test_all_slots_filled_accepted(self):
        bdt = _make_bdt(photo_slots=[
            PhotoSlot(label="A", image_data=b"img1"),
            PhotoSlot(label="B", image_data=b"img2"),
            PhotoSlot(label="C", image_data=b"img3"),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_no_slots_filled_rejected(self):
        bdt = _make_bdt(photo_slots=[
            PhotoSlot(label="A", image_data=None),
            PhotoSlot(label="B", image_data=None),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_partial_slots_revise(self):
        bdt = _make_bdt(photo_slots=[
            PhotoSlot(label="A", image_data=b"img"),
            PhotoSlot(label="B", image_data=None),
            PhotoSlot(label="C", image_data=b"img"),
        ])
        r = _rule_1_photos(bdt)
        assert r.verdict == "Revise"
        assert not r.passed
        assert "B" in r.detail

    def test_no_slots_photo_count_positive_accepted(self):
        bdt = _make_bdt(photo_slots=[], photo_count=3)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_no_slots_photo_count_zero_rejected(self):
        bdt = _make_bdt(photo_slots=[], photo_count=0)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_deferred_photos_returns_na(self):
        bdt = _make_bdt(photo_slots=[], photo_count=0, photos_deferred=True)
        r = _rule_1_photos(bdt)
        assert r.verdict == "N/A"
        assert r.passed is None


# ── 3. R2 Power Alarm Match ─────────────────────────────────

class TestR2PowerAlarmMatch:

    def test_power_alarm_on_test_date_accepted(self):
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 3600.0),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_no_power_alarm_on_date_rejected(self):
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-20 08:00", 3600.0),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_no_test_date_rejected(self):
        bdt = _make_bdt(site_code="SITE001", test_date=None)
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 3600.0),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_no_alarm_data_na(self):
        bdt = _make_bdt(site_code="SITE001")
        r = _rule_2_power_alarm_match(bdt, None)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_empty_alarm_df_na(self):
        bdt = _make_bdt(site_code="SITE001")
        r = _rule_2_power_alarm_match(bdt, _make_alarm_df([]))
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_different_site_rejected(self):
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE999", "2026-01-15 08:00", 3600.0),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"

    def test_file_source_fallback(self):
        """When alarm_category is not Power, falls back to file_source."""
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
        )
        alarm_df = _make_alarm_df([dict(
            site_id="SITE001",
            occurred_on=pd.Timestamp("2026-01-15 08:00"),
            cleared_on=pd.Timestamp("2026-01-15 10:00"),
            alarm_category="Unknown",
            _duration_secs=7200.0,
            duration="02:00:00",
            file_source="power_alarms_jan.csv",
        )])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"


# ── 4. R3 Duration Match ────────────────────────────────────

class TestR3DurationMatch:

    def test_duration_within_tolerance_accepted(self):
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
            discharge_minutes=120.0,
        )
        # 7200 secs = 120 mins, exact match
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 7200.0),
        ])
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_duration_exceeds_tolerance_rejected(self):
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
            discharge_minutes=120.0,
        )
        # 3600 secs = 60 mins vs 120 bdt → 100% diff
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 3600.0),
        ])
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_no_matching_power_alarm_rejected(self):
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm("SITE999", "2026-01-15 08:00", 7200.0),
        ])
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_no_alarm_data_na(self):
        bdt = _make_bdt(discharge_minutes=120.0)
        r = _rule_3_duration_match(bdt, None, tolerance=0.15)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_no_test_date_rejected(self):
        bdt = _make_bdt(test_date=None, discharge_minutes=120.0)
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 7200.0),
        ])
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Rejected"

    def test_within_boundary_tolerance(self):
        """Duration at exactly 15% difference should be accepted."""
        bdt = _make_bdt(
            site_code="SITE001",
            test_date=datetime(2026, 1, 15),
            discharge_minutes=115.0,
        )
        # 100 min alarm, 115 BDT → 15% diff = at boundary
        alarm_df = _make_alarm_df([
            _power_alarm("SITE001", "2026-01-15 08:00", 6000.0),
        ])
        r = _rule_3_duration_match(bdt, alarm_df, tolerance=0.15)
        assert r.verdict == "Accepted"


# ── 5. R4 Discharge Table ───────────────────────────────────

class TestR4DischargeTable:

    def test_readings_match_reported_accepted(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", 51.0, 31.0),
                ("60 min", 50.0, 32.0),
                ("90 min", 49.0, 33.0),
                ("120 min", 46.0, 35.0),
            ],
            discharge_minutes=120.0,
        )
        r = _rule_4_discharge_table(bdt, tolerance=0.15)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_readings_diverge_revise(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", 51.0, 31.0),
                ("60 min", 50.0, 32.0),
            ],
            discharge_minutes=120.0,  # reported 120 but table only goes to 60
        )
        r = _rule_4_discharge_table(bdt, tolerance=0.15)
        assert r.verdict == "Revise"
        assert not r.passed

    def test_no_readings_na(self):
        bdt = _make_bdt(discharge_readings=[], discharge_minutes=120.0)
        r = _rule_4_discharge_table(bdt, tolerance=0.15)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_readings_all_empty_revise(self):
        """Readings exist but all V/A are None → last_mins=0 → Revise."""
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", None, None),
                ("60 min", None, None),
                ("90 min", None, None),
            ],
            discharge_minutes=120.0,
        )
        r = _rule_4_discharge_table(bdt, tolerance=0.15)
        assert r.verdict == "Revise"
        assert not r.passed


# ── 6. R5 I Battery ──────────────────────────────────────────

class TestR5IBattery:

    def test_low_current_accepted(self):
        bdt = _make_bdt(ibat_before_test=0.2)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_high_current_rejected(self):
        bdt = _make_bdt(ibat_before_test=0.8)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_exactly_at_threshold_rejected(self):
        """0.5 is not < 0.5, so rejected."""
        bdt = _make_bdt(ibat_before_test=0.5)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_zero_current_accepted(self):
        bdt = _make_bdt(ibat_before_test=0.0)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_none_na(self):
        bdt = _make_bdt(ibat_before_test=None)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_negative_small_accepted(self):
        """Negative small value: abs(-0.3) < 0.5 → accepted."""
        bdt = _make_bdt(ibat_before_test=-0.3)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Accepted"


# ── 7. R6 End Voltage ────────────────────────────────────────

class TestR6EndVoltage:

    def test_in_range_accepted(self):
        bdt = _make_bdt(end_voltage=46.0, discharge_minutes=120.0)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_below_range_rejected(self):
        bdt = _make_bdt(end_voltage=44.0, discharge_minutes=120.0)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_above_range_rejected(self):
        bdt = _make_bdt(end_voltage=48.0, discharge_minutes=120.0)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_boundary_low_accepted(self):
        bdt = _make_bdt(end_voltage=45.0, discharge_minutes=120.0)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"

    def test_boundary_high_accepted(self):
        bdt = _make_bdt(end_voltage=47.0, discharge_minutes=120.0)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"

    def test_auto_accept_cutoff_with_remaining_capacity(self):
        """discharge >= 180 min, theoretical > reported, end_voltage above
        normal range → auto-accepted because battery had remaining capacity."""
        bdt = _make_bdt(
            end_voltage=48.7,
            discharge_minutes=180.0,
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            battery_brand="Narada",  # non-lithium, efficiency = health_pct
        )
        # theoretical = (200 * 48 * 2 * 0.80) / (52 * 30) * 60
        #             = 15360 / 1560 * 60 = ~590.77 min > 180
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"
        assert "cutoff" in r.detail.lower() or "remaining capacity" in r.detail.lower()

    def test_none_na(self):
        bdt = _make_bdt(end_voltage=None)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_no_auto_accept_when_theoretical_less_than_reported(self):
        """Even at >=180 min, if theoretical <= reported, no auto-accept."""
        bdt = _make_bdt(
            end_voltage=48.7,
            discharge_minutes=600.0,  # reported > theoretical
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=50.0,   # small capacity
            battery_voltage=48.0,
            num_strings=1,
            battery_brand="Narada",
        )
        # theoretical = (50 * 48 * 1 * 0.8) / (52 * 30) * 60 = 1920/1560*60=~73.8 min
        # 73.8 < 600 → no auto-accept, falls through to range check
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"  # 48.7 outside 45-47


# ── 8. R7 V/A Inverse ───────────────────────────────────────

class TestR7InverseRelationship:

    def test_negative_correlation_accepted(self):
        """Voltage decreases while ampere increases → negative corr."""
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 52.0, 28.0),
            ("60 min", 50.0, 30.0),
            ("90 min", 48.0, 32.0),
            ("120 min", 46.0, 34.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_positive_correlation_rejected(self):
        """Voltage and ampere both increase → positive corr."""
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 46.0, 28.0),
            ("60 min", 48.0, 30.0),
            ("90 min", 50.0, 32.0),
            ("120 min", 52.0, 34.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_fewer_than_3_pairs_na(self):
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 52.0, 28.0),
            ("60 min", 50.0, 30.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_no_readings_na(self):
        bdt = _make_bdt(discharge_readings=[])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "N/A"

    def test_partial_none_values_still_evaluates(self):
        """Only pairs where both V and A exist are used."""
        bdt = _make_bdt(discharge_readings=[
            ("15 min", None, 28.0),    # skipped — no V
            ("30 min", 52.0, None),    # skipped — no A
            ("60 min", 52.0, 28.0),
            ("90 min", 50.0, 30.0),
            ("120 min", 48.0, 32.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        # 3 valid pairs with inverse relationship
        assert r.verdict == "Accepted"

    def test_constant_values_na(self):
        """Constant V or A → correlation is NaN → N/A."""
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 50.0, 30.0),
            ("60 min", 50.0, 30.0),
            ("90 min", 50.0, 30.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "N/A"


# ── 9. R8 Theoretical BT ────────────────────────────────────

class TestR8TheoreticalBT:

    def test_reported_within_theoretical_accepted(self):
        bdt = _make_bdt(
            discharge_minutes=120.0,
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            battery_brand="Narada",
        )
        # theoretical = (200 * 48 * 2 * 0.80) / (52 * 30) * 60 = ~590.8 min
        # reported 120 < 590.8 → accepted
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"
        assert r.passed

    def test_reported_exceeds_theoretical_rejected(self):
        bdt = _make_bdt(
            discharge_minutes=800.0,
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            battery_brand="Narada",
        )
        # theoretical = ~590.8 min, reported=800 > 590.8*1.15=~679.4 → rejected
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"
        assert not r.passed

    def test_3_hour_cutoff_rejected(self):
        """theoretical > 180 and reported ~180 → suspected cutoff."""
        bdt = _make_bdt(
            discharge_minutes=180.0,
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            battery_brand="Narada",
        )
        # theoretical = ~590.8 min > 180, and abs(180-180)=0 <=5 → cutoff
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"
        assert "cutoff" in r.detail.lower()

    def test_missing_battery_ah_na(self):
        bdt = _make_bdt(battery_ah=None)
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "N/A"
        assert r.passed is None

    def test_missing_battery_voltage_na(self):
        bdt = _make_bdt(battery_voltage=None)
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "N/A"

    def test_missing_num_strings_na(self):
        bdt = _make_bdt(num_strings=None)
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "N/A"

    def test_missing_load_data_na(self):
        """start_voltage or start_ampere missing → can't compute theoretical."""
        bdt = _make_bdt(
            start_voltage=None,
            start_ampere=None,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "N/A"

    def test_3_hour_cutoff_boundary(self):
        """reported=185 → abs(185-180)=5 <=5 → still detected as cutoff."""
        bdt = _make_bdt(
            discharge_minutes=185.0,
            start_voltage=52.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            battery_brand="Narada",
        )
        r = _rule_8_backup_time(bdt, health_pct=0.80)
        assert r.verdict == "Rejected"
        assert "cutoff" in r.detail.lower()


# ── 10. _theoretical_backup_minutes() ───────────────────────

class TestTheoreticalBackupMinutes:

    def test_lithium_efficiency_1(self):
        """Lithium batteries use efficiency=1.0 regardless of health_pct."""
        bdt = _make_bdt(
            battery_brand="Lithium Ion 48V",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=2,
            start_voltage=52.0,
            start_ampere=20.0,
        )
        result = _theoretical_backup_minutes(bdt, health_pct=0.50)
        # efficiency = 1.0 (lithium)
        # capacity_wh = 100 * 48 * 2 * 1.0 = 9600
        # load_w = 52 * 20 = 1040
        # result = (9600 / 1040) * 60 = ~553.85 min
        expected = (100 * 48 * 2 * 1.0) / (52 * 20) * 60
        assert result is not None
        assert abs(result - expected) < 0.01

    def test_non_lithium_uses_health_pct(self):
        """Non-lithium batteries use efficiency=health_pct."""
        bdt = _make_bdt(
            battery_brand="Narada VRLA",
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
            start_voltage=52.0,
            start_ampere=30.0,
        )
        health = 0.80
        result = _theoretical_backup_minutes(bdt, health_pct=health)
        expected = (200 * 48 * 2 * health) / (52 * 30) * 60
        assert result is not None
        assert abs(result - expected) < 0.01

    def test_missing_load_voltage_returns_none(self):
        bdt = _make_bdt(
            start_voltage=None,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
        )
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_missing_load_ampere_returns_none(self):
        bdt = _make_bdt(
            start_voltage=52.0,
            start_ampere=None,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
        )
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_zero_load_voltage_returns_none(self):
        bdt = _make_bdt(
            start_voltage=0.0,
            start_ampere=30.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
        )
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_zero_load_ampere_returns_none(self):
        bdt = _make_bdt(
            start_voltage=52.0,
            start_ampere=0.0,
            battery_ah=200.0,
            battery_voltage=48.0,
            num_strings=2,
        )
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_missing_battery_ah_returns_none(self):
        bdt = _make_bdt(battery_ah=None, battery_voltage=48.0, num_strings=2)
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_missing_battery_voltage_returns_none(self):
        bdt = _make_bdt(battery_ah=200.0, battery_voltage=None, num_strings=2)
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_missing_num_strings_returns_none(self):
        bdt = _make_bdt(battery_ah=200.0, battery_voltage=48.0, num_strings=None)
        assert _theoretical_backup_minutes(bdt, health_pct=0.80) is None

    def test_lith_keyword_detection(self):
        """'lith' substring in brand triggers lithium efficiency."""
        bdt = _make_bdt(
            battery_brand="BYD Lith-Ion",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=50.0,
            start_ampere=10.0,
        )
        result = _theoretical_backup_minutes(bdt, health_pct=0.50)
        # Lithium → efficiency=1.0
        expected = (100 * 48 * 1 * 1.0) / (50 * 10) * 60
        assert result is not None
        assert abs(result - expected) < 0.01
