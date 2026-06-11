"""Comprehensive tests for alarm_app.bdt_validator active rule behavior."""

from datetime import datetime

import pandas as pd

from alarm_app.bdt.parser import BDTData, PhotoSlot
from alarm_app.bdt.validator import (
    BDT_TOLERANCE_PROFILE_VERSION,
    BDT_TOLERANCE_PROFILE_VERSION_KEY,
    BDTTolerances,
    _evaluate_door_evidence,
    _find_door_alarms,
    _rule_1_photos,
    _rule_2_power_alarm_match,
    _rule_3_string_vs_busbar,
    _rule_5_start_ampere,
    _rule_6_end_voltage,
    _rule_7_inverse_relationship,
    _rule_8_backup_time,
    _rule_9_discharge_current_tolerance,
    _rule_10_door_alarm_match,
    _rule_11_summary_checklist,
    _theoretical_backup_minutes,
    bdt_battery_status,
    validate_bdt,
)
from alarm_app.core.battery_backup_insights import resolve_network_battery_context

# ── Helpers ─────────────────────────────────────────────────────────────

def _slot(
    label: str,
    category: str | None,
    image_data: bytes | None,
) -> PhotoSlot:
    slot = PhotoSlot(label=label, image_data=image_data)
    if category is not None:
        # Parser provides this field in production; attach dynamically for tests.
        slot.category = category
    return slot


def _make_bdt(**kwargs) -> BDTData:
    defaults = {
        "file_path": "tests/fixtures/test.xlsx",
        "filename": "test.xlsx",
        "site_code": "SITE001",
        "site_name": "Test Site",
        "test_date": datetime(2026, 1, 15),
        "time_in": "08:00",
        "time_out": "10:00",
        "discharge_readings": [
            ("30 min", 52.0, 30.0),
            ("60 min", 51.0, 30.5),
            ("90 min", 50.0, 30.8),
            ("120 min", 46.0, 31.0),
        ],
        "start_voltage": 48.0,
        "start_ampere": 40.0,
        "end_voltage": 46.0,
        "end_ampere": 31.0,
        "discharge_minutes": 120.0,
        "ibat_before_test": 0.2,
        "battery_brand": "Narada",
        "battery_ah": 100.0,
        "battery_voltage": 48.0,
        "num_strings": 1,
        "photo_count": 2,
        "photo_slots": [],
        "photos_deferred": False,
        "errors": [],
        "summary_data": {},
        "num_batteries": None,
        "num_modules": None,
        "rectifier_brand": "",
        "pld_value": "",
    }
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
    cleared: str | None = None,
    category: str = "Door",
    alarm_name: str = "Door Open",
    file_source: str = "door_alarms.csv",
) -> dict:
    cleared_ts = pd.Timestamp(cleared) if cleared is not None else pd.Timestamp(occurred) + pd.Timedelta(minutes=1)
    return {
        "site_id": site_id,
        "occurred_on": pd.Timestamp(occurred),
        "cleared_on": cleared_ts,
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
            "R1", "R2", "R3", "R5", "R6", "R7", "R8", "R9",
            "R10", "R11"
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

    def test_overall_rejected_when_no_alarm_data_loaded(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(photo_slots=slots, photo_count=16)
        result = validate_bdt(bdt, None)
        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert verdicts["R2"] == "N/A"
        assert verdicts["R10"] == "Revise"
        assert result.overall == "Revise"

    def test_overall_revise_when_power_evidence_revise_and_door_accepted(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            discharge_minutes=120.0,
            summary_data={
                "Short Code": "SITE001",
                "Battery Brand": "Narada",
                "Battery Voltage": "48",
                "Number of Strings": "1",
                "Start Voltage": "48.0",
                "End Voltage": "46.0",
                "Discharge Time (mins)": "120",
                "Test Date": "2026-01-15",
            },
        )
        alarm_df = _make_alarm_df([_door_alarm()])

        result = validate_bdt(bdt, alarm_df)

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert verdicts["R2"] == "Revise"
        assert verdicts["R10"] == "Accepted"
        assert not any(r.verdict == "Rejected" for r in result.rules)
        assert result.overall == "Revise"

    def test_overall_rejected_without_door_even_when_battery_rules_accepted(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            discharge_minutes=120.0,
            summary_data={
                "Short Code": "SITE001",
                "Battery Brand": "Narada",
                "Battery Voltage": "48",
                "Number of Strings": "1",
                "Start Voltage": "48.0",
                "End Voltage": "46.0",
                "Discharge Time (mins)": "120",
                "Test Date": "2026-01-15",
            },
        )
        alarm_df = _make_alarm_df([_power_alarm()])

        result = validate_bdt(bdt, alarm_df)

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert verdicts["R2"] == "Accepted"
        assert verdicts["R10"] == "Rejected"
        assert result.overall == "Rejected"

    def test_no_battery_skips_battery_dependent_rules_and_declines_bdt(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(photo_slots=slots, photo_count=16, num_batteries=0)
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(bdt, alarm_df)

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert verdicts["R1"] == "Accepted"
        assert verdicts["R10"] == "Accepted"
        assert verdicts["R11"] == "N/A"
        assert all(verdicts[r] == "Skipped" for r in ["R2", "R3", "R5", "R6", "R7", "R8", "R9"])
        assert result.overall == "Rejected"

    def test_faulty_battery_skips_battery_dependent_rules_only(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            summary_data={"Reason for Stop BDT": "Faulty battery"},
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(bdt, alarm_df)

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert all(verdicts[r] == "Skipped" for r in ["R2", "R3", "R5", "R6", "R7", "R8", "R9"])
        assert verdicts["R1"] == "Accepted"
        assert verdicts["R10"] == "Accepted"
        assert result.overall == "Rejected"

    def test_bdt_battery_skip_takes_precedence_but_records_network_agreement(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            summary_data={"Reason for Stop BDT": "Faulty battery"},
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(
            bdt,
            alarm_df,
            network_no_usable_backup=True,
            network_backup_minutes=0.0,
            network_backup_reasons=["Network Summary backup status is ZERO BACKUP"],
        )

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert all(verdicts[r] == "Skipped" for r in ["R2", "R3", "R5", "R6", "R7", "R8", "R9"])
        assert result.overall == "Rejected"
        assert result.validation_context["network_no_usable_backup_also"] is True
        assert result.validation_context["network_backup_reasons"] == [
            "Network Summary backup status is ZERO BACKUP"
        ]
        assert "display_overall" not in result.validation_context

    def test_summary_zero_batteries_skips_battery_dependent_rules(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            summary_data={"No. of Batteries": "0"},
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(bdt, alarm_df)

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert all(verdicts[r] == "Skipped" for r in ["R2", "R3", "R5", "R6", "R7", "R8", "R9"])
        assert result.overall == "Rejected"

    def test_empty_network_summary_context_runs_full_validation(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])
        network_context = resolve_network_battery_context([], min_backup_minutes=10.0)

        result = validate_bdt(
            bdt,
            alarm_df,
            network_no_usable_backup=network_context.no_usable_backup,
            network_backup_minutes=network_context.backup_minutes,
            network_backup_reasons=network_context.reasons,
        )

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert network_context.has_network_summary is False
        assert all(verdicts[r] != "Skipped" for r in ["R2", "R3", "R5", "R6", "R7", "R8", "R9"])
        assert verdicts["R2"] == "Accepted"
        assert result.validation_context == {}
        assert result.overall == "Accepted"

    def test_network_no_usable_backup_accepts_component_check_when_infrastructure_passes(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            site_code="0167DE",
            pld_value="44",
            rectifier_brand="Delta 2",
            num_modules=3,
            test_date=datetime(2026, 1, 11),
            battery_brand="Lithium",
            battery_voltage=48.0,
            num_strings=2,
            num_batteries=2,
            start_voltage=54.10,
            start_ampere=23.30,
            end_voltage=48.70,
            end_ampere=25.80,
            discharge_minutes=180.0,
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Test Date": "2026-01-11",
                "Battery Brand": "WRONG",
                "Start Volt": "99.99",
            },
        )
        alarm_df = _make_alarm_df([
            _power_alarm(site_id="0167DE", occurred="2026-01-11 08:05:00", cleared="2026-01-11 11:05:00"),
            _door_alarm(site_id="0167DE", occurred="2026-01-11 08:00:00", cleared="2026-01-11 08:01:00"),
        ])

        result = validate_bdt(
            bdt,
            alarm_df,
            network_no_usable_backup=True,
            network_backup_minutes=0.0,
            network_backup_reasons=["Network Summary backup status is ZERO BACKUP"],
        )

        verdicts = {r.rule_id: r.verdict for r in result.rules}
        assert all(verdicts[r] == "Skipped" for r in ["R2", "R3", "R5", "R6", "R7", "R8", "R9"])
        assert verdicts["R1"] == "Accepted"
        assert verdicts["R10"] == "Accepted"
        assert verdicts["R11"] == "Accepted"
        assert result.overall == "Accepted"
        assert result.validation_context["validation_mode"] == "component_check_no_backup_battery"
        assert result.validation_context["display_overall"] == "Accepted (component check - no backup battery)"
        assert result.validation_context["network_backup_minutes"] == 0.0
        assert "component check only" in next(r.detail for r in result.rules if r.rule_id == "R2")
        r11_detail = next(r.detail for r in result.rules if r.rule_id == "R11")
        assert "Group A" in r11_detail
        assert "skipped Group B1" in r11_detail
        assert "skipped Group B2" in r11_detail

    def test_network_component_check_keeps_failed_infrastructure_verdict(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            summary_data={"Short Code": "SITE001", "Test Date": "2026-01-15"},
        )

        result = validate_bdt(
            bdt,
            _make_alarm_df([]),
            network_no_usable_backup=True,
            network_backup_reasons=["Network Summary strings are zero"],
        )

        assert result.overall == "Rejected"
        assert result.validation_context["validation_mode"] == "component_check_no_backup_battery"
        assert "display_overall" not in result.validation_context
        assert any(r.rule_id == "R10" and r.verdict == "Rejected" for r in result.rules)

    def test_faulty_battery_runs_r11_infrastructure_and_inventory_only(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
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
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Battery Brand": "Lithium",
                "Battery Volt": "48",
                "No of String": "2",
                "No of Batteries": "2",
                "Start Volt": "99.99",
                "Reason for Stop BDT": "Faulty battery",
                "Test Date": "2026-01-11",
            },
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(bdt, alarm_df)

        r11 = next(r for r in result.rules if r.rule_id == "R11")
        assert result.overall == "Rejected"
        assert r11.verdict == "Accepted"
        assert "Group A" in r11.detail
        assert "Group B1" in r11.detail
        assert "skipped Group B2" in r11.detail

    def test_no_battery_runs_r11_infrastructure_only(self):
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 8 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(
            photo_slots=slots,
            photo_count=16,
            site_code="0167DE",
            pld_value="44",
            rectifier_brand="Delta 2",
            num_modules=3,
            num_batteries=0,
            battery_brand="Lithium",
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Test Date": "2026-01-15",
                "Battery Brand": "WRONG",
                "No of Batteries": "99",
            },
        )
        alarm_df = _make_alarm_df([_power_alarm(), _door_alarm()])

        result = validate_bdt(bdt, alarm_df)

        r11 = next(r for r in result.rules if r.rule_id == "R11")
        assert result.overall == "Rejected"
        assert r11.verdict == "Accepted"
        assert "Group A" in r11.detail
        assert "skipped Group B1" in r11.detail

    def test_battery_status_labels_battery_state(self):
        assert bdt_battery_status(_make_bdt()) == "Has Battery"
        assert bdt_battery_status(_make_bdt(num_batteries=0)) == "No Battery"
        assert bdt_battery_status(_make_bdt(summary_data={"Reason for Stop BDT": "Faulty battery"})) == "Faulty Battery"
        assert bdt_battery_status(None) == "--"


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

    def test_16_photos_all_rectifier_no_batteries_accepted(self):
        """16 photos — count is sufficient, categories are informational."""
        slots = [_slot(f"Slot {i+1}", "rectifier", b"img") for i in range(16)]
        bdt = _make_bdt(photo_slots=slots)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert "16/16" in r.detail

    def test_16_photos_both_categories_accepted(self):
        """16 photos with both rectifier and batteries — count path, Accepted."""
        slots = [
            _slot(f"Slot {i+1}", "rectifier" if i < 10 else "batteries", b"img")
            for i in range(16)
        ]
        bdt = _make_bdt(photo_slots=slots)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Accepted"
        assert "16/16" in r.detail

    def test_deferred_photos_na(self):
        # deferred mode now uses count-based fallback; photo_count=0 → Rejected
        bdt = _make_bdt(photo_slots=[], photos_deferred=True, photo_detection_mode="deferred", photo_count=0)
        r = _rule_1_photos(bdt)
        assert r.verdict == "Rejected"
        assert r.passed is False


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

    def test_ampm_with_non_breaking_space_accepted(self):
        """12-hour AM/PM values can include non-breaking spaces from Excel."""
        bdt = _make_bdt(
            time_in="2:00\u00a0PM", time_out="4:00\u00a0PM",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("90 min", 50.0, 30.8),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 14:00:00", cleared="2026-01-15 16:00:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_excel_datetime_like_time_string_accepted(self):
        """Excel-exported datetime-like time strings are accepted for Time In."""
        bdt = _make_bdt(
            time_in="1900-01-01 14:00:00", time_out="1900-01-01 16:00:00",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("90 min", 50.0, 30.8),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 14:00:00", cleared="2026-01-15 16:00:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_outside_tolerance_revise(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:16:00", cleared="2026-01-15 10:16:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"

    def test_default_tolerance_15_minutes_accepted(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:15:00", cleared="2026-01-15 10:15:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

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

    def test_no_power_same_site_date_revise(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _power_alarm(site_id="SITE999"),
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"

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

    def test_duration_mismatch_revise_even_with_start_end_match(self):
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
        assert r.verdict == "Revise"
        assert "duration" in r.detail.lower()

    def test_duration_over_180_minutes_no_longer_auto_rejected(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("120 min", 49.0, 30.0),
                ("180 min", 48.7, 29.8),
                ("210 min", 48.6, 29.7),
            ],
            discharge_minutes=210.0,
        )
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:00", cleared="2026-01-15 11:30:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"
        assert "210.0 min" in r.detail

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

    def test_batteries_with_duration_but_no_power_alarm_revise(self):
        """Site has discharge data but no power alarm at all."""
        bdt = _make_bdt(discharge_minutes=120.0)
        alarm_df = _make_alarm_df([_door_alarm()])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"
        assert "Power alarm evidence" in r.detail

    def test_power_cleared_no_site_down_accepted(self):
        """Case A: Power alarm clears (grid restores), no Down alarm."""
        bdt = _make_bdt(time_in="08:00", time_out="11:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:00:00",
                         cleared="2026-01-15 10:05:00")
        ])
        r = _rule_2_power_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"

    def test_power_clear_after_time_out_within_discharge_duration_is_accepted(self):
        bdt = _make_bdt(
            time_in="08:00",
            time_out="09:30",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _door_alarm(occurred="2026-01-15 08:00:00"),
            _power_alarm(occurred="2026-01-15 08:05:00", cleared="2026-01-15 10:05:00"),
        ])

        r = _rule_2_power_alarm_match(bdt, alarm_df)

        assert r.verdict == "Accepted"

    def test_power_clear_far_beyond_discharge_duration_remains_revise(self):
        bdt = _make_bdt(
            time_in="08:00",
            time_out="09:30",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _door_alarm(occurred="2026-01-15 08:00:00"),
            _power_alarm(occurred="2026-01-15 08:05:00", cleared="2026-01-15 11:30:00"),
        ])

        r = _rule_2_power_alarm_match(bdt, alarm_df)

        assert r.verdict == "Revise"

    def test_power_clear_far_beyond_discharge_duration_does_not_extend_down_interval(self):
        bdt = _make_bdt(
            time_in="08:00",
            time_out="10:30",
            discharge_readings=[
                ("30 min", 52.0, 30.0),
                ("60 min", 51.0, 30.5),
                ("120 min", 46.0, 31.0),
            ],
            discharge_minutes=120.0,
        )
        alarm_df = _make_alarm_df([
            _door_alarm(occurred="2026-01-15 08:00:00"),
            _power_alarm(occurred="2026-01-15 08:05:00", cleared="2026-01-15 11:30:00"),
            _down_alarm(occurred="2026-01-15 10:03:00"),
        ])

        r = _rule_2_power_alarm_match(bdt, alarm_df)

        assert r.verdict == "Revise"

    def test_variable_tolerance_override(self):
        """Custom tolerance overrides the constant."""
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _power_alarm(occurred="2026-01-15 08:04:00",
                         cleared="2026-01-15 10:04:00")
        ])
        # With 3-minute tolerance, 4-minute offset needs review
        r = _rule_2_power_alarm_match(bdt, alarm_df, tol_override=3.0)
        assert r.verdict == "Revise"
        # With 5-minute tolerance, 4-minute offset should pass
        r = _rule_2_power_alarm_match(bdt, alarm_df, tol_override=5.0)
        assert r.verdict == "Accepted"



# ── R5 Starting I-Battery ───────────────────────────────────────────────

class TestR5StartAmpere:

    def test_default_accepts_human_review_start_current(self):
        bdt = _make_bdt(ibat_before_test=0.9)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Accepted"
        assert r.rule_name == "Starting I-Battery ampere"
        assert "|I| <= 1.00A" in r.detail

    def test_threshold_boundary_accepted(self):
        bdt = _make_bdt(ibat_before_test=1.0)
        r = _rule_5_start_ampere(bdt)
        assert r.verdict == "Accepted"

    def test_above_threshold_rejected(self):
        bdt = _make_bdt(ibat_before_test=1.01)
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

    def test_low_voltage_accepts_as_depleted_battery_evidence(self):
        bdt = _make_bdt(discharge_minutes=65.0, end_voltage=43.0)
        r = _rule_6_end_voltage(bdt, health_pct=0.80)
        assert r.verdict == "Accepted"
        assert "depleted" in r.detail or "weak" in r.detail

    def test_short_duration_with_high_voltage_rejected(self):
        bdt = _make_bdt(discharge_minutes=120.0, end_voltage=48.5)
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

    def test_constant_series_returns_na_without_corrcoef_warning(self):
        bdt = _make_bdt(discharge_readings=[
            ("30 min", 48.0, 10.0),
            ("60 min", 48.0, 12.0),
            ("90 min", 48.0, 14.0),
        ])
        r = _rule_7_inverse_relationship(bdt)
        assert r.verdict == "N/A"
        assert "Cannot compute correlation" in r.detail


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

    def test_theoretical_over_180_accepts_short_as_weak_backup_evidence(self):
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
        assert r.verdict == "Accepted"
        assert "weak" in r.detail or "short backup" in r.detail
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

    def test_actual_below_theoretical_accepted_as_weak_backup_evidence(self):
        # theoretical = 150 min; actual = 120 is weak/short backup evidence, not fraud.
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
            discharge_minutes=120.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Accepted"
        assert "weak" in r.detail or "short backup" in r.detail

    def test_actual_above_theoretical_beyond_tolerance_rejected(self):
        # theoretical = 150 min; default upper window = 172.5 min; actual = 180 is suspicious.
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
            discharge_minutes=180.0,
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Rejected"
        assert "over-performance" in r.detail

    def test_tolerance_floor_15_minutes_for_short_tests(self):
        # theoretical ≈ 60 min; theoretical * 0.15 = 9 min, but floor is 15 min;
        # diff = 14 → Accepted (would have been rejected without floor)
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=100.0,  # makes theoretical = 60 min
            discharge_minutes=46.0,  # diff = 14
        )
        r = _rule_8_backup_time(bdt, health_pct=0.95)
        assert r.verdict == "Accepted"
        # When the floor wins, detail should not claim a fractional window
        assert "min floor" in r.detail
        assert "% of theoretical" not in r.detail

    def test_tolerance_parameter_widens_window(self):
        # theoretical = 150 min; with tolerance=0.30, window = 45 min;
        # actual = 190, over by 40 → Rejected at 0.15 (window 22.5),
        # but Accepted at 0.30 (window 45)
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0,
            battery_voltage=48.0,
            num_strings=1,
            start_voltage=48.0,
            start_ampere=40.0,
            discharge_minutes=190.0,
        )
        strict = _rule_8_backup_time(bdt, health_pct=0.95, tolerance=0.15)
        loose = _rule_8_backup_time(bdt, health_pct=0.95, tolerance=0.30)
        assert strict.verdict == "Rejected"
        assert loose.verdict == "Accepted"

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

    def test_no_alarm_data_revise(self):
        bdt = _make_bdt()
        r = _rule_10_door_alarm_match(bdt, None)
        assert r.verdict == "Revise"
        assert "required" in r.detail.lower()
        assert "no alarm data" in r.detail.lower()

    def test_detect_by_alarm_category_accepted(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([_door_alarm(category="Door", alarm_name="X", file_source="misc.csv")])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"
        assert "entry" in r.detail.lower()

    def test_strict_category_rejects_name_only_match(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(category="Security", alarm_name="Main Door Open", file_source="misc.csv")
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"

    def test_strict_category_rejects_file_source_only_match(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(category="Security", alarm_name="Other", file_source="door_events.csv")
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"

    def test_same_site_and_date_required_rejected(self):
        bdt = _make_bdt()
        alarm_df = _make_alarm_df([
            _door_alarm(site_id="SITE999", occurred="2026-01-15 09:00:00"),
            _door_alarm(site_id="SITE001", occurred="2026-01-16 09:00:00"),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"

    def test_find_door_alarms_lists_all_strict_candidates(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _door_alarm(site_id="SITE001", occurred="2026-01-15 06:30:00"),
            _door_alarm(site_id="SITE001", occurred="2026-01-15 09:15:00"),
        ])
        doors = _find_door_alarms(
            alarm_df,
            bdt.site_code,
            pd.Timestamp(bdt.test_date).normalize(),
        )

        assert len(doors) == 2

    def test_r10_contained_accepted(self):
        bdt = _make_bdt(time_in="11:05", time_out="13:42")
        alarm_df = _make_alarm_df([
            _door_alarm(
                occurred="2026-01-15 11:10:00",
                cleared="2026-01-15 13:30:00",
            ),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Accepted"
        assert "inside onsite window" in r.detail
        assert "entry" in r.detail.lower()

    def test_r10_4528ca_pattern_revise(self):
        bdt = _make_bdt(
            site_code="4528CA",
            time_in="11:05",
            time_out="13:42",
            test_date=datetime(2026, 4, 2),
        )
        alarm_df = _make_alarm_df([
            _door_alarm(
                site_id="4528CA",
                occurred="2026-04-02 10:51:00",
                cleared="2026-04-02 13:44:00",
                alarm_name="Shelter Door Alarm",
            ),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"
        assert "overlap" in r.detail.lower()
        assert "entry" in r.detail.lower()
        assert "exit" in r.detail.lower()
        assert "reviewer decision" in r.detail.lower()

    def test_r10_no_overlap_rejected(self):
        bdt = _make_bdt(time_in="11:05", time_out="13:42")
        alarm_df = _make_alarm_df([
            _door_alarm(
                occurred="2026-01-15 08:00:00",
                cleared="2026-01-15 09:00:00",
            ),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert "none overlap onsite window" in r.detail.lower()

    def test_r10_missing_cleared_revise(self):
        bdt = _make_bdt(time_in="11:05", time_out="13:42")
        alarm_df = _make_alarm_df([
            {
                "site_id": "SITE001",
                "occurred_on": pd.Timestamp("2026-01-15 11:10:00"),
                "cleared_on": pd.NaT,
                "alarm_category": "Door",
                "alarm_name": "Shelter Door Alarm",
                "_duration_secs": 60.0,
                "duration": "00:01:00",
                "file_source": "door_alarms.csv",
            },
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"
        assert "cleared_on is missing" in r.detail.lower()

    def test_r10_overlap_but_not_contained_revise(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _door_alarm(
                occurred="2026-01-15 06:30:00",
                cleared="2026-01-15 09:00:00",
            ),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Revise"
        assert "reviewer decision" in r.detail.lower()

    def test_r10_no_overlap_when_only_early_visit_rejected(self):
        bdt = _make_bdt(time_in="08:00", time_out="10:00")
        alarm_df = _make_alarm_df([
            _door_alarm(
                occurred="2026-01-15 06:30:00",
                cleared="2026-01-15 07:00:00",
            ),
        ])
        r = _rule_10_door_alarm_match(bdt, alarm_df)
        assert r.verdict == "Rejected"
        assert "none overlap onsite window" in r.detail.lower()

    def test_r10_overall_revise_not_rejected_on_edge(self):
        bdt = _make_bdt(
            site_code="4528CA",
            time_in="11:05",
            time_out="13:42",
            test_date=datetime(2026, 4, 2),
            battery_brand="Lithium - Huawei",
            battery_voltage=48.0,
            num_strings=2,
            num_batteries=2,
            num_modules=5,
            rectifier_brand="Huawei",
            summary_data={
                "Short Code": "4528CA",
                "Battery Brand": "Lithium - Huawei",
                "Battery Voltage": "48",
                "Number of Strings": "2",
                "Number of Batteries": "2",
                "Number of Modules": "5",
                "Rectifier Brand": "Huawei",
                "Test Date": "2026-04-02",
                "Start Voltage": "48.0",
                "Start Amp": "40.0",
                "End Voltage": "46.0",
                "End Amp": "31.0",
                "Discharge Time (mins)": "120.0",
            },
        )
        alarm_df = _make_alarm_df([
            _door_alarm(
                site_id="4528CA",
                occurred="2026-04-02 10:51:00",
                cleared="2026-04-02 13:44:00",
            ),
            _power_alarm(
                site_id="4528CA",
                occurred="2026-04-02 11:05:00",
                cleared="2026-04-02 13:05:00",
            ),
        ])
        result = validate_bdt(bdt, alarm_df)
        r10 = next(r for r in result.rules if r.rule_id == "R10")
        assert r10.verdict == "Revise"
        rejected = [r.rule_id for r in result.rules if r.verdict == "Rejected"]
        assert "R10" not in rejected
        assert result.overall == "Revise"

    def test_evaluate_door_evidence_rows_share_r10_status_labels(self):
        bdt = _make_bdt(time_in="11:05", time_out="13:42")
        alarm_df = _make_alarm_df([
            _door_alarm(
                occurred="2026-01-15 11:10:00",
                cleared="2026-01-15 13:30:00",
            ),
            _door_alarm(
                occurred="2026-01-15 08:00:00",
                cleared="2026-01-15 09:00:00",
            ),
        ])
        evidence = _evaluate_door_evidence(bdt, alarm_df)
        statuses = {row.status_label for row in evidence.rows}
        assert "Accepted" in statuses
        assert "No overlap" in statuses


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

    def test_lead_acid_uses_normalized_string_voltage_from_block_count(self):
        bdt = _make_bdt(
            battery_brand="SBS",
            battery_ah=170.0,
            battery_voltage=12.0,
            num_batteries=16,
            num_strings=4,
            start_voltage=48.0,
            start_ampere=40.0,
        )

        result = _theoretical_backup_minutes(bdt, health_pct=0.80)

        expected = (170 * 48 * 4 * 0.80) / (48 * 40) * 60
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

    def test_alias_headers_and_date_format_match(self):
        bdt = _make_bdt(
            site_code="3868DE",
            pld_value="44",
            rectifier_brand="Delta 3",
            num_modules=4,
            battery_brand="Huawei-Lithium",
            battery_voltage=48.0,
            num_strings=2,
            num_batteries=2,
            start_voltage=54.14,
            start_ampere=72.9,
            end_voltage=46.1,
            end_ampere=109.0,
            discharge_minutes=120.0,
            test_date=datetime(2026, 1, 5),
            summary_data={
                "Short Code": "3868DE",
                "PLD Value": "44",
                "Rectifier Brand": "Delta 3",
                "Number of Modules": "4",
                "Battery Brand": "Huawei-Lithium",
                "Battery Voltage": "48 V",
                "Number of Strings": "2",
                "Number of Batteries": "2",
                "Start Voltage": "54.14",
                "Start Amp": "72.9",
                "End Voltage": "46.1",
                "End Amp": "109",
                "Discharge Time (mins)": "120",
                "Test Date": "5-Jan-26",
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_verbose_summary_header_prefix_matches(self):
        bdt = _make_bdt(
            site_code="",
            pld_value="47.5",
            rectifier_brand="",
            battery_brand="",
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
                "PLVD Value (LLVD For Huawei) adjusted after finishing the test ": "47.5",
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_site_id_summary_header_matches_short_code(self):
        bdt = _make_bdt(
            site_code="0704UP",
            pld_value="",
            rectifier_brand="",
            battery_brand="",
            battery_voltage=None,
            num_strings=None,
            start_voltage=None,
            start_ampere=None,
            end_voltage=None,
            end_ampere=None,
            discharge_minutes=0.0,
            ibat_before_test=None,
            test_date=None,
            summary_data={"Site ID": "0704UP"},
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_missing_bdt_pld_value_does_not_force_revise(self):
        bdt = _make_bdt(
            site_code="0704UP",
            pld_value="",
            rectifier_brand="",
            battery_brand="",
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
                "Site ID": "0704UP",
                "PLVD Value (LLVD For Huawei) adjusted after finishing the test ": "40.5",
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_verbose_summary_header_prefix_requires_boundary(self):
        bdt = _make_bdt(
            site_code="",
            pld_value="47.5",
            rectifier_brand="",
            battery_brand="",
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
                "PLVD Valued By": "wrong",
                "PLVD Value (LLVD For Huawei) adjusted after finishing the test ": "47.5",
            },
        )
        r = _rule_11_summary_checklist(bdt)
        assert r.verdict == "Accepted"

    def test_active_group_a_only_skips_battery_inventory_and_discharge_groups(self):
        bdt = _make_bdt(
            site_code="0167DE",
            pld_value="44",
            rectifier_brand="Delta 2",
            num_modules=3,
            battery_brand="Lithium",
            start_voltage=54.10,
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Battery Brand": "WRONG",
                "Start Volt": "99.99",
                "Test Date": "2026-01-15",
            },
        )

        r = _rule_11_summary_checklist(bdt, active_groups={"A"})

        assert r.verdict == "Accepted"
        assert "Group A" in r.detail
        assert "skipped Group B1" in r.detail
        assert "skipped Group B2" in r.detail
        assert "Battery Brand" not in r.detail

    def test_active_groups_a_b1_skip_discharge_results_only(self):
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
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Battery Brand": "Lithium",
                "Battery Volt": "48",
                "No of String": "2",
                "No of Batteries": "2",
                "Start Volt": "99.99",
                "Test Date": "2026-01-15",
            },
        )

        r = _rule_11_summary_checklist(bdt, active_groups={"A", "B1"})

        assert r.verdict == "Accepted"
        assert "Group A" in r.detail
        assert "Group B1" in r.detail
        assert "skipped Group B2" in r.detail
        assert "Start Voltage" not in r.detail

    def test_active_group_threshold_applies_only_to_checked_fields(self):
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
            summary_data={
                "Short Code": "0167DE",
                "PLVD Value": "44",
                "Rectifier Brand": "Delta 2",
                "# of Modules": "3",
                "Battery Brand": "WRONG",
                "Battery Volt": "99",
                "No of String": "99",
                "No of Batteries": "99",
                "Start Volt": "99.99",
                "Start Amp": "99.99",
                "End Volt": "99.99",
                "End Amp": "99.99",
                "Discharge time( Mins)": "999",
                "Test Date": "2026-01-11",
            },
        )

        a_only = _rule_11_summary_checklist(bdt, active_groups={"A"})
        all_groups = _rule_11_summary_checklist(bdt)

        assert a_only.verdict == "Accepted"
        assert all_groups.verdict == "Rejected"


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

    def test_string_sum_3a_above_busbar_boundary_accepted(self):
        """Boundary case: E-(G+I) == -3.0 should pass."""
        bdt = _make_bdt(
            discharge_readings=[
                ("30 Mins", 49.0, 30.0),
            ],
            string_discharge_readings=[
                [(54.0, 0.0), (54.0, 0.0)],           # Before (sliced off)
                [(49.0, 16.0), (49.0, 17.0)],          # sum=33.0, bus=30.0, E-(G+I)=-3.0
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Accepted"

    def test_string_sum_below_busbar_rejected(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 Mins", 49.0, 30.0),
            ],
            string_discharge_readings=[
                [(54.0, 0.0), (54.0, 0.0)],           # Before (sliced off)
                [(49.0, 14.0), (49.0, 15.0)],          # sum=29.0, bus=30.0, E-(G+I)=+1.0
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Rejected"
        assert "Batteries Amp not matched" in r.detail
        assert "1.00A" in r.detail or "1.0A" in r.detail

    def test_string_sum_more_than_3a_above_busbar_rejected(self):
        bdt = _make_bdt(
            discharge_readings=[
                ("30 Mins", 49.0, 30.0),
            ],
            string_discharge_readings=[
                [(54.0, 0.0), (54.0, 0.0)],           # Before (sliced off)
                [(49.0, 17.0), (49.0, 17.0)],          # sum=34.0, bus=30.0, E-(G+I)=-4.0
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Rejected"
        assert "Batteries Amp not matched" in r.detail
        assert "-4.00A" in r.detail or "-4.0A" in r.detail

    def test_no_string_readings_na(self):
        bdt = _make_bdt(string_discharge_readings=[])
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "N/A"

    def test_high_load_site_rejected_when_beyond_neg3_limit(self):
        """Real pattern from 3422DE includes points below -3.0A on E-(G+I)."""
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
        assert r.verdict == "Rejected"

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


# ── User-configurable tolerance parameter tests ─────────────────────────


class TestBDTTolerancesDataclass:
    def test_defaults_match_constants(self):
        tol = BDTTolerances.defaults()
        assert tol.sizing_fractional_tolerance == 0.15
        assert tol.sizing_minutes_floor == 15.0
        assert tol.power_timing_min == 15.0
        assert tol.string_ampere_a == 3.0
        assert tol.string_ampere_pos_a == 0.5
        assert tol.discharge_current_a == 1.0
        assert tol.discharge_current_pct == 0.03
        assert tol.start_ampere_a == 1.0
        assert tol.end_voltage_min == 45.0
        assert tol.end_voltage_max == 47.0
        assert tol.completion_minutes == 180.0
        assert tol.min_backup_minutes_for_battery_rules == 10.0

    def test_from_dict_overrides_defaults(self):
        tol = BDTTolerances.from_dict(
            {"discharge_current_a": 2.5, "string_ampere_a": "4.5"})
        assert tol.discharge_current_a == 2.5
        assert tol.string_ampere_a == 4.5
        # untouched fields keep defaults
        assert tol.sizing_fractional_tolerance == 0.15

    def test_from_dict_ignores_unknown_keys_and_bad_types(self):
        tol = BDTTolerances.from_dict(
            {"unknown": 1.0, "discharge_current_a": "not-a-number", "start_ampere_a": None})
        assert tol.discharge_current_a == 1.0  # invalid, falls back
        assert tol.start_ampere_a == 1.0       # None ignored

    def test_from_dict_migrates_legacy_start_ampere_default(self):
        tol = BDTTolerances.from_dict({"start_ampere_a": 0.5})
        assert tol.start_ampere_a == 1.0

    def test_from_dict_preserves_custom_start_ampere(self):
        tol = BDTTolerances.from_dict({"start_ampere_a": 0.75})
        assert tol.start_ampere_a == 0.75

    def test_from_dict_preserves_versioned_start_ampere_half_ampere(self):
        tol = BDTTolerances.from_dict({
            BDT_TOLERANCE_PROFILE_VERSION_KEY: BDT_TOLERANCE_PROFILE_VERSION,
            "start_ampere_a": 0.5,
        })
        assert tol.start_ampere_a == 0.5

    def test_to_dict_round_trips(self):
        tol = BDTTolerances(
            discharge_current_a=2.5,
            string_ampere_a=4.5,
            min_backup_minutes_for_battery_rules=12.5,
        )
        roundtrip = BDTTolerances.from_dict(tol.to_dict())
        assert roundtrip == tol

    def test_current_defaults_to_dict_round_trips(self):
        roundtrip = BDTTolerances.from_dict(BDTTolerances.defaults().to_dict())
        assert roundtrip == BDTTolerances.defaults()

    def test_from_dict_none_returns_defaults(self):
        assert BDTTolerances.from_dict(None) == BDTTolerances.defaults()


class TestR3ConfigurableStringAmpereTolerance:
    def _build_bdt(self):
        # rectifier=25.0, strings_sum=22.0 → diff=+3.0
        return _make_bdt(
            discharge_readings=[("30 Mins", 49.0, 25.0)],
            string_discharge_readings=[
                [(54.0, 0.0)],
                [(49.0, 22.0)],
            ],
        )

    def test_large_positive_diff_rejected(self):
        # diff=+3.0A clearly exceeds the +0.5A positive epsilon → Rejected
        r = _rule_3_string_vs_busbar(self._build_bdt())
        assert r.verdict == "Rejected"

    def test_small_positive_diff_within_epsilon_accepted(self):
        # diff=+0.1A (measurement noise, bus barely above strings) → Accepted
        bdt = _make_bdt(
            discharge_readings=[("10 Mins", 49.0, 30.1)],
            string_discharge_readings=[
                [(54.0, 0.0)],
                [(49.0, 30.0)],   # sum=30.0, bus=30.1, diff=+0.1 ≤ +0.5A
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Accepted"

    def test_positive_diff_just_above_epsilon_rejected(self):
        # diff=+0.6A is just over the +0.5A epsilon → Rejected
        bdt = _make_bdt(
            discharge_readings=[("10 Mins", 49.0, 30.6)],
            string_discharge_readings=[
                [(54.0, 0.0)],
                [(49.0, 30.0)],   # sum=30.0, bus=30.6, diff=+0.6 > +0.5A
            ],
        )
        r = _rule_3_string_vs_busbar(bdt)
        assert r.verdict == "Rejected"

    def test_widened_band_accepts_diff_within(self):
        # rectifier=20.0, strings_sum=23.0 → diff=-3.0 (just inside default 3A)
        bdt = _make_bdt(
            discharge_readings=[("30 Mins", 49.0, 20.0)],
            string_discharge_readings=[
                [(54.0, 0.0)],
                [(49.0, 23.0)],
            ],
        )
        strict = _rule_3_string_vs_busbar(
            bdt, tolerances=BDTTolerances(string_ampere_a=2.0))
        loose = _rule_3_string_vs_busbar(
            bdt, tolerances=BDTTolerances(string_ampere_a=5.0))
        assert strict.verdict == "Rejected"
        assert loose.verdict == "Accepted"


class TestR5ConfigurableStartAmpereThreshold:
    def test_threshold_widened_accepts_higher_current(self):
        bdt = _make_bdt(ibat_before_test=0.9)
        strict = _rule_5_start_ampere(
            bdt, tolerances=BDTTolerances(start_ampere_a=0.5))
        loose = _rule_5_start_ampere(
            bdt, tolerances=BDTTolerances(start_ampere_a=1.0))
        assert strict.verdict == "Rejected"
        assert loose.verdict == "Accepted"


class TestR6ConfigurableVoltageBandAndCompletion:
    def test_widened_voltage_band_accepts_high_voltage(self):
        bdt = _make_bdt(end_voltage=48.0, discharge_minutes=120.0)
        strict = _rule_6_end_voltage(
            bdt, health_pct=0.95,
            tolerances=BDTTolerances(end_voltage_min=45.0, end_voltage_max=47.0))
        loose = _rule_6_end_voltage(
            bdt, health_pct=0.95,
            tolerances=BDTTolerances(end_voltage_min=45.0, end_voltage_max=49.0))
        assert strict.verdict == "Rejected"
        assert loose.verdict == "Accepted"

    def test_lowered_completion_minutes_accepts_short_test(self):
        bdt = _make_bdt(end_voltage=48.5, discharge_minutes=100.0)
        strict = _rule_6_end_voltage(
            bdt, health_pct=0.95,
            tolerances=BDTTolerances(completion_minutes=180.0))
        loose = _rule_6_end_voltage(
            bdt, health_pct=0.95,
            tolerances=BDTTolerances(completion_minutes=90.0))
        assert strict.verdict == "Rejected"
        assert loose.verdict == "Accepted"


class TestR9ConfigurableDischargeCurrentBand:
    def test_widened_band_accepts_drift(self):
        # baseline=25.0, follow-up=27.0 → drift=2.0A
        # 3% of 25.0=0.75A < floor 1.0A → band=1.0A → still Rejected with default floor
        bdt = _make_bdt(
            discharge_readings=[
                ("Before", 53.0, 25.0),
                ("30 Mins", 50.0, 27.0),
            ],
        )
        strict = _rule_9_discharge_current_tolerance(
            bdt, tolerances=BDTTolerances(discharge_current_a=1.0))
        loose = _rule_9_discharge_current_tolerance(
            bdt, tolerances=BDTTolerances(discharge_current_a=2.5))
        assert strict.verdict == "Rejected"
        assert loose.verdict == "Accepted"

    def test_high_baseline_pct_tolerance_accepts_small_relative_drift(self):
        # baseline=90.0A, drift=+1.8A → 3% of 90=2.7A → band=2.7A → 1.8 ≤ 2.7 → Accepted
        # (mirrors real 0704UP data that human reviewers accepted)
        bdt = _make_bdt(
            discharge_readings=[
                ("10 Mins", 49.0, 90.0),
                ("30 Mins", 48.5, 91.8),
            ],
        )
        r = _rule_9_discharge_current_tolerance(bdt)
        assert r.verdict == "Accepted"

    def test_low_baseline_floor_still_rejects_just_above_1a(self):
        # baseline=20.0A, drift=+1.2A → 3% of 20=0.6A < floor 1.0A → band=1.0A → Rejected
        bdt = _make_bdt(
            discharge_readings=[
                ("10 Mins", 52.0, 20.0),
                ("30 Mins", 51.0, 21.2),
            ],
        )
        r = _rule_9_discharge_current_tolerance(bdt)
        assert r.verdict == "Rejected"


class TestValidateBdtPlumbsTolerances:
    """End-to-end: validate_bdt should pass tolerances to rules."""

    def test_tolerances_dict_overrides_legacy_args(self):
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0, battery_voltage=48.0, num_strings=1,
            start_voltage=48.0, start_ampere=40.0,
            discharge_minutes=190.0,  # over by 40 vs theoretical=150
            ibat_before_test=0.0,
            end_voltage=46.0,
        )
        # Default fractional 0.15 → upper window 22.5 → over by 40 rejected
        result_default = validate_bdt(bdt, alarm_df=None,
                                       tolerances=BDTTolerances.defaults())
        r8_default = next(r for r in result_default.rules if r.rule_id == "R8")
        assert r8_default.verdict == "Rejected"

        # Loosen via dataclass
        result_loose = validate_bdt(
            bdt, alarm_df=None,
            tolerances=BDTTolerances(sizing_fractional_tolerance=0.30))
        r8_loose = next(r for r in result_loose.rules if r.rule_id == "R8")
        assert r8_loose.verdict == "Accepted"

    def test_legacy_tolerance_arg_still_honoured(self):
        bdt = _make_bdt(
            battery_brand="Lithium",
            battery_ah=100.0, battery_voltage=48.0, num_strings=1,
            start_voltage=48.0, start_ampere=40.0,
            discharge_minutes=190.0,
            ibat_before_test=0.0,
            end_voltage=46.0,
        )
        # Legacy positional tolerance=0.30 should still widen the window
        result = validate_bdt(bdt, alarm_df=None, tolerance=0.30)
        r8 = next(r for r in result.rules if r.rule_id == "R8")
        assert r8.verdict == "Accepted"
