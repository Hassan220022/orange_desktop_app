"""
Tests for alarm_app.parsers — pure functions only (no Qt / QThread).

Every test is self-contained with synthetic data.
"""

import datetime
import math

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

# We import only the pure helpers and functions, not the QThread classes.
# The module-level import of PyQt5 inside parsers.py is unavoidable, but
# we only exercise functions that never touch Qt.
from alarm_app.parsers import (
    _is_alarm_header,
    _duration_to_secs,
    _secs_to_hhmmss,
    _load_external_summary_lookup,
    _match_external_summary_row,
    parse_alarm_file,
    classify_by_alarm_id,
    compute_site_down_flag,
)
from alarm_app.constants import (
    ALL_INTERNAL_COLS,
    SCHEMA_1_MAP,
    SCHEMA_2_MAP,
)


class TestBDTValidationThreadFiltering:
    def test_skips_missing_bdt_sheet_results(self):
        # Import here so test_parsers can remain mostly pure-function focused.
        from alarm_app.parsers import BDTValidationThread

        class _FakeBdtData:
            def __init__(self, filename, errors):
                self.filename = filename
                self.file_path = f"/fake/{filename}"
                self.site_code = ""
                self.test_date = None
                self.errors = errors
                self.photos_deferred = False

        bad = _FakeBdtData("bad.xlsx", ["Missing 'BDT sheet'"])
        good = _FakeBdtData("good.xlsx", [])
        good.site_code = "4415DE"

        def fake_parse(fp, skip_photos=True):
            return bad if fp.endswith("bad.xlsx") else good

        def fake_validate(bdt_data, alarm_df, tolerance, health_pct):
            class _Rule:
                rule_id = "R1"
                verdict = "Accepted"
                detail = ""
            class _Res:
                def __init__(self, b):
                    self.filename = b.filename
                    self.site_code = b.site_code
                    self.test_date = "Unknown"
                    self.overall = "Accepted"
                    self.rules = [_Rule()]
                    self.parse_errors = list(b.errors)
                    self.bdt_data = b
            return _Res(bdt_data)

        files = ["/fake/bad.xlsx", "/fake/good.xlsx"]
        th = BDTValidationThread(files, None, 0.15, 0.80)
        captured = {}
        th.finished.connect(lambda results, by_site: captured.update(
            {"results": results, "by_site": by_site}))

        with patch("alarm_app.bdt_parser.parse_bdt_file", side_effect=fake_parse), \
             patch("alarm_app.bdt_validator.validate_bdt", side_effect=fake_validate), \
             patch("alarm_app.bdt_parser.load_bdt_photos", side_effect=lambda b: None):
            th.run()

        assert "results" in captured
        assert len(captured["results"]) == 1
        assert captured["results"][0].filename == "good.xlsx"
        assert "4415DE" in captured["by_site"]

    def test_keeps_partially_parsed_file_with_nonfatal_errors(self):
        from alarm_app.parsers import BDTValidationThread

        class _FakeBdtData:
            def __init__(self, filename, errors):
                self.filename = filename
                self.file_path = f"/fake/{filename}"
                self.site_code = "0630UP"
                self.test_date = None
                self.errors = errors
                self.photos_deferred = False
                self.discharge_readings = [("30 min", 52.0, 25.0)]
                self.start_voltage = 54.0
                self.start_ampere = 23.0

        partial = _FakeBdtData("partial.xlsx", ["Missing 'BDT sheet'"])

        def fake_parse(_fp, skip_photos=True):
            return partial

        def fake_validate(bdt_data, alarm_df, tolerance, health_pct):
            class _Rule:
                rule_id = "R1"
                verdict = "Accepted"
                detail = ""
            class _Res:
                def __init__(self, b):
                    self.filename = b.filename
                    self.site_code = b.site_code
                    self.test_date = "Unknown"
                    self.overall = "Accepted"
                    self.rules = [_Rule()]
                    self.parse_errors = list(b.errors)
                    self.bdt_data = b
            return _Res(bdt_data)

        th = BDTValidationThread(["/fake/partial.xlsx"], None, 0.15, 0.80)
        captured = {}
        th.finished.connect(lambda results, by_site: captured.update(
            {"results": results, "by_site": by_site}))

        with patch("alarm_app.bdt_parser.parse_bdt_file", side_effect=fake_parse), \
             patch("alarm_app.bdt_validator.validate_bdt", side_effect=fake_validate), \
             patch("alarm_app.bdt_parser.load_bdt_photos", side_effect=lambda b: None):
            th.run()

        assert "results" in captured
        assert len(captured["results"]) == 1
        assert captured["results"][0].filename == "partial.xlsx"
        assert "0630UP" in captured["by_site"]

    def test_applies_external_summary_lookup_before_validation(self):
        from alarm_app.parsers import BDTValidationThread

        class _FakeBdtData:
            def __init__(self, filename):
                self.filename = filename
                self.file_path = f"/fake/{filename}"
                self.site_code = "3868DE"
                self.test_date = datetime.datetime(2026, 1, 5)
                self.errors = []
                self.photos_deferred = False
                self.discharge_readings = [("30 min", 52.0, 25.0)]
                self.start_voltage = 54.0
                self.start_ampere = 23.0
                self.summary_data = {}

        parsed = _FakeBdtData("good.xlsx")

        def fake_parse(_fp, skip_photos=True):
            return parsed

        observed = {}

        def fake_validate(bdt_data, alarm_df, tolerance, health_pct):
            observed["summary_data"] = dict(getattr(bdt_data, "summary_data", {}))

            class _Rule:
                rule_id = "R11"
                verdict = "Accepted"
                detail = ""

            class _Res:
                def __init__(self, b):
                    self.filename = b.filename
                    self.site_code = b.site_code
                    self.test_date = "2026-01-05"
                    self.overall = "Accepted"
                    self.rules = [_Rule()]
                    self.parse_errors = list(b.errors)
                    self.bdt_data = b

            return _Res(bdt_data)

        lookup = {
            "by_site_date": {
                ("3868DE", "2026-01-05"): {
                    "Short Code": "3868DE",
                    "PLVD Value": "44",
                    "Rectifier Brand": "Delta 3",
                    "Test Date": "2026-01-05",
                }
            },
            "by_site": {
                "3868DE": {
                    "2026-01-05": {
                        "Short Code": "3868DE",
                        "PLVD Value": "44",
                        "Rectifier Brand": "Delta 3",
                        "Test Date": "2026-01-05",
                    }
                }
            },
        }

        th = BDTValidationThread(["/fake/good.xlsx"], None, 0.15, 0.80)
        captured = {}
        th.finished.connect(lambda results, by_site: captured.update(
            {"results": results, "by_site": by_site}))

        with patch("alarm_app.parsers._load_external_summary_lookup", return_value=lookup), \
             patch("alarm_app.bdt_parser.parse_bdt_file", side_effect=fake_parse), \
             patch("alarm_app.bdt_validator.validate_bdt", side_effect=fake_validate), \
             patch("alarm_app.bdt_parser.load_bdt_photos", side_effect=lambda b: None):
            th.run()

        assert "results" in captured
        assert len(captured["results"]) == 1
        assert observed["summary_data"]["PLVD Value"] == "44"
        assert observed["summary_data"]["Rectifier Brand"] == "Delta 3"


class TestExternalSummaryHelpers:
    def test_load_external_summary_lookup_maps_alias_headers(self, tmp_path):
        bdt_file = tmp_path / "SITE_BDT.xlsx"
        bdt_file.touch()
        summary_file = tmp_path / "Weekly Battery Update.xlsx"

        df = pd.DataFrame([{
            "Short Code": "3868DE",
            "PLD Value": "44",
            "Rectifier Brand": "Delta 3",
            "Number of Modules": 4,
            "Battery Brand": "Huawei-Lithium",
            "Battery Voltage": "48 V",
            "Number of Strings": 2,
            "Number of Batteries": 2,
            "Start Voltage": 54.14,
            "Start Amp": 72.9,
            "End Voltage": 46.1,
            "End Amp": 109,
            "Discharge Time (mins)": 120,
            "Test Date": "5-Jan-26",
        }])
        df.to_excel(summary_file, index=False, sheet_name="BDT 2025-2026")

        lookup = _load_external_summary_lookup([str(bdt_file)])
        key = ("3868DE", "2026-01-05")
        assert key in lookup["by_site_date"]

        row = lookup["by_site_date"][key]
        assert row["Short Code"] == "3868DE"
        assert row["PLVD Value"] == "44"
        assert row["# of Modules"] == "4"
        assert row["Battery Volt"] == "48 V"
        assert row["No of String"] == "2"
        assert row["No of Batteries"] == "2"
        assert row["Start Volt"] == "54.14"
        assert row["End Volt"] == "46.1"
        assert row["Discharge time( Mins)"] == "120"
        assert row["Test Date"] == "2026-01-05"

    def test_match_external_summary_row_uses_site_date_key(self):
        class _FakeBdtData:
            site_code = "3868DE"
            test_date = datetime.datetime(2026, 1, 5)

        row = {"Short Code": "3868DE", "Test Date": "2026-01-05"}
        lookup = {
            "by_site_date": {("3868DE", "2026-01-05"): row},
            "by_site": {"3868DE": {"2026-01-05": row}},
        }

        matched = _match_external_summary_row(_FakeBdtData(), lookup)
        assert matched == row


# ═══════════════════════════════════════════════════════════════════
# 1. _is_alarm_header
# ═══════════════════════════════════════════════════════════════════
class TestIsAlarmHeader:
    """Validate the quick header-sniffing logic."""

    def test_huawei_columns_detected(self):
        cols = list(SCHEMA_1_MAP.keys())  # all Huawei columns
        assert _is_alarm_header(cols) is True

    def test_nokia_columns_detected(self):
        cols = list(SCHEMA_2_MAP.keys())  # all Nokia columns
        assert _is_alarm_header(cols) is True

    def test_random_columns_rejected(self):
        cols = ["Foo", "Bar", "Baz", "Qux"]
        assert _is_alarm_header(cols) is False

    def test_empty_columns_rejected(self):
        assert _is_alarm_header([]) is False

    def test_minimum_match_threshold_met(self):
        # Exactly 3 Huawei columns should pass (_MIN_MATCH == 3)
        cols = ["Alarm Source", "Site Name", "Alarm ID"]
        assert _is_alarm_header(cols) is True

    def test_below_minimum_match_threshold(self):
        # Only 2 Huawei columns -- should fail
        cols = ["Alarm Source", "Site Name"]
        assert _is_alarm_header(cols) is False

    def test_mixed_valid_and_random(self):
        # 3 valid Huawei + random junk -- should still pass
        cols = ["Alarm Source", "Site Name", "Alarm ID", "Nonsense", "Junk"]
        assert _is_alarm_header(cols) is True

    def test_whitespace_stripped(self):
        cols = ["  Alarm Source ", " Site Name", "Alarm ID "]
        assert _is_alarm_header(cols) is True

    def test_nokia_minimum_match(self):
        cols = ["Site ID", "Alarm ID", "Vendor"]
        assert _is_alarm_header(cols) is True


# ═══════════════════════════════════════════════════════════════════
# 2. _duration_to_secs
# ═══════════════════════════════════════════════════════════════════
class TestDurationToSecs:
    """Convert heterogeneous duration representations to seconds."""

    def test_string_hhmmss(self):
        assert _duration_to_secs("01:30:45") == 5445.0

    def test_string_short(self):
        assert _duration_to_secs("00:00:09") == 9.0

    def test_datetime_time(self):
        assert _duration_to_secs(datetime.time(0, 5, 10)) == 310.0

    def test_pd_timestamp(self):
        ts = pd.Timestamp("1900-01-01 00:02:20")
        assert _duration_to_secs(ts) == 140.0

    def test_none(self):
        assert _duration_to_secs(None) == 0.0

    def test_nan(self):
        assert _duration_to_secs(float("nan")) == 0.0

    def test_empty_string(self):
        assert _duration_to_secs("") == 0.0

    def test_malformed_string(self):
        assert _duration_to_secs("abc") == 0.0

    def test_np_nan(self):
        assert _duration_to_secs(np.nan) == 0.0

    def test_pd_nat(self):
        assert _duration_to_secs(pd.NaT) == 0.0

    def test_large_hours(self):
        # "100:00:00" = 360000s
        assert _duration_to_secs("100:00:00") == 360000.0


# ═══════════════════════════════════════════════════════════════════
# 3. _secs_to_hhmmss
# ═══════════════════════════════════════════════════════════════════
class TestSecsToHhmmss:
    """Convert numeric seconds back to display strings."""

    def test_normal(self):
        assert _secs_to_hhmmss(5445) == "01:30:45"

    def test_zero(self):
        assert _secs_to_hhmmss(0) == ""

    def test_negative(self):
        assert _secs_to_hhmmss(-1) == ""

    def test_exact_hour(self):
        assert _secs_to_hhmmss(3661) == "01:01:01"

    def test_large_value(self):
        # 100 hours
        assert _secs_to_hhmmss(360000) == "100:00:00"

    def test_one_second(self):
        assert _secs_to_hhmmss(1) == "00:00:01"

    def test_zero_padded(self):
        assert _secs_to_hhmmss(61) == "00:01:01"


# ═══════════════════════════════════════════════════════════════════
# 4. parse_alarm_file
# ═══════════════════════════════════════════════════════════════════
class TestParseAlarmFile:
    """Parse CSV files with Huawei / Nokia schemas."""

    @staticmethod
    def _write_csv(tmp_path, filename, columns, rows):
        """Helper: write a CSV and return an info dict like discover_alarm_files."""
        path = tmp_path / filename
        df = pd.DataFrame(rows, columns=columns)
        df.to_csv(path, index=False)
        return {
            "path": str(path),
            "ext": ".csv",
            "filename": filename,
            "size_kb": path.stat().st_size / 1024,
        }

    def test_huawei_csv_parsed(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "SiteA", "2024-01-01 10:00", "2024-01-01 11:00",
                 "01:00:00", "100", "Power Fail", "Cleared", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "power_alarm.csv", cols, rows)
        result = parse_alarm_file(info)

        assert result is not None
        assert not result.empty
        assert list(result.columns) == ALL_INTERNAL_COLS
        assert result.iloc[0]["site_id"] == "SiteA"
        assert str(result.iloc[0]["alarm_id"]) == "100"

    def test_nokia_csv_parsed(self, tmp_path):
        cols = list(SCHEMA_2_MAP.keys())
        rows = [["Active", "SiteN1", "200", "Nokia", "nsrc",
                 "Link Down", "3G", "2024-02-01 08:00", "2024-02-01 09:00"]]
        info = self._write_csv(tmp_path, "down_alarm.csv", cols, rows)
        result = parse_alarm_file(info)

        assert result is not None
        assert not result.empty
        assert list(result.columns) == ALL_INTERNAL_COLS
        assert result.iloc[0]["site_id"] == "SiteN1"
        assert result.iloc[0]["vendor"] == "Nokia"

    def test_random_columns_returns_none(self, tmp_path):
        cols = ["Foo", "Bar", "Baz"]
        rows = [["x", "y", "z"]]
        info = self._write_csv(tmp_path, "random.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is None

    def test_category_power_from_filename(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "SiteA", "2024-01-01 10:00", "2024-01-01 11:00",
                 "01:00:00", "100", "Power Fail", "Cleared", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "power_alarms_2024.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert (result["alarm_category"] == "Power").all()

    def test_category_down_from_filename(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "SiteA", "2024-01-01 10:00", "2024-01-01 11:00",
                 "01:00:00", "100", "Power Fail", "Cleared", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "down_alarms_2024.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert (result["alarm_category"] == "Down").all()

    def test_category_door_from_filename(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "SiteA", "2024-01-01 10:00", "2024-01-01 11:00",
                 "01:00:00", "100", "Main Door Open", "Cleared", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "door_alarms_2024.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert (result["alarm_category"] == "Door").all()

    def test_category_empty_when_no_keyword(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "SiteA", "2024-01-01 10:00", "2024-01-01 11:00",
                 "01:00:00", "100", "Power Fail", "Cleared", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "alarms_misc.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert (result["alarm_category"] == "").all()

    def test_empty_file_returns_none(self, tmp_path):
        # Write a CSV with only a header but no data rows
        path = tmp_path / "empty.csv"
        path.write_text("Foo,Bar,Baz\n")
        info = {
            "path": str(path), "ext": ".csv",
            "filename": "empty.csv", "size_kb": 0,
        }
        result = parse_alarm_file(info)
        assert result is None

    def test_result_columns_match_all_internal(self, tmp_path):
        """Every returned DataFrame must have exactly ALL_INTERNAL_COLS."""
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "S1", "2024-01-01", "2024-01-02",
                 "24:00:00", "1", "A", "C", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "power.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert list(result.columns) == ALL_INTERNAL_COLS

    def test_file_source_column_set(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "S1", "2024-01-01", "2024-01-02",
                 "01:00:00", "1", "A", "C", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "my_power_data.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert (result["file_source"] == "my_power_data.csv").all()


# ═══════════════════════════════════════════════════════════════════
# 5. classify_by_alarm_id
# ═══════════════════════════════════════════════════════════════════
class TestClassifyByAlarmId:
    """Classify rows by alarm_id membership and door-name/source heuristics."""

    @staticmethod
    def _make_df(alarm_ids, categories=None):
        n = len(alarm_ids)
        cats = categories if categories is not None else [""] * n
        return pd.DataFrame({
            "alarm_id": alarm_ids,
            "alarm_category": cats,
        })

    def test_power_ids_classified(self):
        df = self._make_df(["100", "200", "999"])
        alarm_ids = {"power": ["100", "200"], "down": []}
        result = classify_by_alarm_id(df, alarm_ids)
        assert result.loc[0, "alarm_category"] == "Power"
        assert result.loc[1, "alarm_category"] == "Power"
        assert result.loc[2, "alarm_category"] == ""

    def test_down_ids_classified(self):
        df = self._make_df(["500", "600"])
        alarm_ids = {"power": [], "down": ["500", "600"]}
        result = classify_by_alarm_id(df, alarm_ids)
        assert result.loc[0, "alarm_category"] == "Down"
        assert result.loc[1, "alarm_category"] == "Down"

    def test_door_ids_classified(self):
        df = self._make_df(["700", "800"])
        alarm_ids = {"power": [], "down": [], "door": ["700", "800"]}
        result = classify_by_alarm_id(df, alarm_ids)
        assert result.loc[0, "alarm_category"] == "Door"
        assert result.loc[1, "alarm_category"] == "Door"

    def test_door_heuristic_from_name_or_source(self):
        df = pd.DataFrame({
            "alarm_id": ["1", "2", "3"],
            "alarm_category": ["", "", ""],
            "alarm_name": ["Main Door Open", "Power Fail", "Outdoor Temp High"],
            "file_source": ["misc.csv", "door_events.csv", "power.csv"],
        })
        result = classify_by_alarm_id(df, {"power": [], "down": [], "door": []})
        assert result.loc[0, "alarm_category"] == "Door"   # alarm_name contains door
        assert result.loc[1, "alarm_category"] == "Door"   # file_source contains door
        assert result.loc[2, "alarm_category"] == ""       # 'Outdoor' must not match

    def test_float_ids_normalized(self):
        """IDs like 300.0 (from Excel numeric parsing) become '300'."""
        df = self._make_df(["300.0", "400.0"])
        alarm_ids = {"power": ["300"], "down": ["400"]}
        result = classify_by_alarm_id(df, alarm_ids)
        assert result.loc[0, "alarm_category"] == "Power"
        assert result.loc[1, "alarm_category"] == "Down"

    def test_empty_dataframe_returned_unchanged(self):
        df = pd.DataFrame(columns=["alarm_id", "alarm_category"])
        alarm_ids = {"power": ["100"], "down": ["200"]}
        result = classify_by_alarm_id(df, alarm_ids)
        assert result.empty

    def test_no_matching_ids(self):
        df = self._make_df(["999", "888"])
        alarm_ids = {"power": ["100"], "down": ["200"]}
        result = classify_by_alarm_id(df, alarm_ids)
        assert (result["alarm_category"] == "").all()

    def test_missing_alarm_id_column(self):
        """DataFrame without alarm_id column should be returned as-is."""
        df = pd.DataFrame({"alarm_category": ["Power"]})
        alarm_ids = {"power": ["100"], "down": []}
        result = classify_by_alarm_id(df, alarm_ids)
        assert list(result.columns) == ["alarm_category"]

    def test_nan_alarm_ids_ignored(self):
        df = self._make_df([np.nan, "100"])
        alarm_ids = {"power": ["100"], "down": []}
        result = classify_by_alarm_id(df, alarm_ids)
        assert result.loc[0, "alarm_category"] == ""
        assert result.loc[1, "alarm_category"] == "Power"

    def test_does_not_mutate_original(self):
        df = self._make_df(["100"])
        original_cat = df.loc[0, "alarm_category"]
        alarm_ids = {"power": ["100"], "down": []}
        classify_by_alarm_id(df, alarm_ids)
        # Original DataFrame should be untouched
        assert df.loc[0, "alarm_category"] == original_cat


# ═══════════════════════════════════════════════════════════════════
# 6. compute_site_down_flag
# ═══════════════════════════════════════════════════════════════════
class TestComputeSiteDownFlag:
    """Determine whether each alarm row indicates the site went down."""

    @staticmethod
    def _make_df(records):
        """Build a DataFrame with standard columns from a list of dicts."""
        df = pd.DataFrame(records)
        for col in ("occurred_on", "cleared_on"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        return df

    def test_down_alarm_always_yes(self):
        df = self._make_df([{
            "alarm_category": "Down",
            "site_id": "S1",
            "occurred_on": "2024-01-01 10:00",
            "cleared_on": "2024-01-01 11:00",
        }])
        result = compute_site_down_flag(df)
        assert result.iloc[0]["site_down_flag"] == "Yes"

    def test_power_with_down_inside_window(self):
        """Power alarm window contains a Down alarm on the same site -> Yes."""
        df = self._make_df([
            {
                "alarm_category": "Power",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": "2024-01-01 14:00",
            },
            {
                "alarm_category": "Down",
                "site_id": "S1",
                "occurred_on": "2024-01-01 12:00",
                "cleared_on": "2024-01-01 13:00",
            },
        ])
        result = compute_site_down_flag(df)
        # Power row should be flagged "Yes" because Down is inside its window
        power_row = result[result["alarm_category"] == "Power"].iloc[0]
        assert power_row["site_down_flag"] == "Yes"
        # Down row is always "Yes"
        down_row = result[result["alarm_category"] == "Down"].iloc[0]
        assert down_row["site_down_flag"] == "Yes"

    def test_power_with_no_down_inside_window(self):
        """Power alarm with no Down alarm inside its window -> No."""
        df = self._make_df([
            {
                "alarm_category": "Power",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": "2024-01-01 11:00",
            },
            {
                "alarm_category": "Down",
                "site_id": "S1",
                "occurred_on": "2024-01-01 15:00",  # outside Power window
                "cleared_on": "2024-01-01 16:00",
            },
        ])
        result = compute_site_down_flag(df)
        power_row = result[result["alarm_category"] == "Power"].iloc[0]
        assert power_row["site_down_flag"] == "No"

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["alarm_category", "site_id",
                                    "occurred_on", "cleared_on"])
        result = compute_site_down_flag(df)
        assert result.empty

    def test_different_sites_not_matched(self):
        """Down alarm on a different site should not flag Power alarm."""
        df = self._make_df([
            {
                "alarm_category": "Power",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": "2024-01-01 14:00",
            },
            {
                "alarm_category": "Down",
                "site_id": "S2",  # different site
                "occurred_on": "2024-01-01 12:00",
                "cleared_on": "2024-01-01 13:00",
            },
        ])
        result = compute_site_down_flag(df)
        power_row = result[result["alarm_category"] == "Power"].iloc[0]
        assert power_row["site_down_flag"] == "No"

    def test_power_with_no_cleared_on(self):
        """Power alarm with NaT cleared_on and Down inside window -> Yes.

        When cleared_on is NaT the code fills it with Timestamp.max,
        so any Down alarm after occurred_on should match.
        """
        df = self._make_df([
            {
                "alarm_category": "Power",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": pd.NaT,
            },
            {
                "alarm_category": "Down",
                "site_id": "S1",
                "occurred_on": "2024-01-01 12:00",
                "cleared_on": "2024-01-01 13:00",
            },
        ])
        result = compute_site_down_flag(df)
        power_row = result[result["alarm_category"] == "Power"].iloc[0]
        assert power_row["site_down_flag"] == "Yes"

    def test_only_power_alarms(self):
        """No Down alarms at all -> Power alarms stay 'No'."""
        df = self._make_df([
            {
                "alarm_category": "Power",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": "2024-01-01 14:00",
            },
        ])
        result = compute_site_down_flag(df)
        assert result.iloc[0]["site_down_flag"] == "No"

    def test_only_down_alarms(self):
        """Only Down alarms -> all flagged 'Yes'."""
        df = self._make_df([
            {
                "alarm_category": "Down",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": "2024-01-01 11:00",
            },
            {
                "alarm_category": "Down",
                "site_id": "S2",
                "occurred_on": "2024-01-01 12:00",
                "cleared_on": "2024-01-01 13:00",
            },
        ])
        result = compute_site_down_flag(df)
        assert (result["site_down_flag"] == "Yes").all()

    def test_does_not_mutate_original(self):
        df = self._make_df([{
            "alarm_category": "Down",
            "site_id": "S1",
            "occurred_on": "2024-01-01 10:00",
            "cleared_on": "2024-01-01 11:00",
        }])
        assert "site_down_flag" not in df.columns
        compute_site_down_flag(df)
        assert "site_down_flag" not in df.columns

    def test_missing_alarm_category_column(self):
        """DataFrame without alarm_category should be returned as-is."""
        df = pd.DataFrame({"site_id": ["S1"]})
        result = compute_site_down_flag(df)
        assert "site_down_flag" not in result.columns

    def test_down_at_exact_power_start(self):
        """Down alarm at exactly occurred_on boundary -> Yes (>= comparison)."""
        df = self._make_df([
            {
                "alarm_category": "Power",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",
                "cleared_on": "2024-01-01 14:00",
            },
            {
                "alarm_category": "Down",
                "site_id": "S1",
                "occurred_on": "2024-01-01 10:00",  # exactly at boundary
                "cleared_on": "2024-01-01 11:00",
            },
        ])
        result = compute_site_down_flag(df)
        power_row = result[result["alarm_category"] == "Power"].iloc[0]
        assert power_row["site_down_flag"] == "Yes"


# ═══════════════════════════════════════════════════════════════════
# 7. Schema detection in parse_alarm_file
# ═══════════════════════════════════════════════════════════════════
class TestSchemaDetection:
    """Verify the Nokia-vs-Huawei auto-detection inside parse_alarm_file."""

    @staticmethod
    def _write_csv(tmp_path, filename, columns, rows):
        path = tmp_path / filename
        df = pd.DataFrame(rows, columns=columns)
        df.to_csv(path, index=False)
        return {
            "path": str(path),
            "ext": ".csv",
            "filename": filename,
            "size_kb": path.stat().st_size / 1024,
        }

    def test_fm_office_triggers_nokia_schema(self, tmp_path):
        """'FM Office' column is a Nokia-only column -> Nokia schema used."""
        # Include FM Office plus enough Nokia schema keys to pass header check
        cols = list(SCHEMA_2_MAP.keys()) + ["FM Office"]
        row = ["Active", "SiteN", "200", "Nokia", "nsrc",
               "Link Down", "3G", "2024-02-01", "2024-02-02", "Regional"]
        info = self._write_csv(tmp_path, "alarm.csv", cols, [row])
        result = parse_alarm_file(info)
        assert result is not None
        # Nokia schema maps "Site ID" -> "site_id"
        assert result.iloc[0]["site_id"] == "SiteN"

    def test_site_id_without_site_name_triggers_nokia(self, tmp_path):
        """'Site ID' present and 'Site Name' absent -> Nokia schema."""
        cols = list(SCHEMA_2_MAP.keys())
        assert "Site ID" in cols
        assert "Site Name" not in cols
        row = ["Active", "SiteN2", "300", "Nokia", "nsrc",
               "Link Down", "3G", "2024-03-01", "2024-03-02"]
        info = self._write_csv(tmp_path, "alarm.csv", cols, [row])
        result = parse_alarm_file(info)
        assert result is not None
        assert result.iloc[0]["site_id"] == "SiteN2"

    def test_site_name_triggers_huawei(self, tmp_path):
        """'Site Name' present -> Huawei schema (even if 'Site ID' also present)."""
        cols = list(SCHEMA_1_MAP.keys())
        assert "Site Name" in cols
        row = ["src1", "SiteH1", "2024-01-01 10:00", "2024-01-01 11:00",
               "01:00:00", "100", "Power Fail", "Cleared", "LTE", "Huawei"]
        info = self._write_csv(tmp_path, "alarm.csv", cols, [row])
        result = parse_alarm_file(info)
        assert result is not None
        # Huawei schema maps "Site Name" -> "site_id"
        assert result.iloc[0]["site_id"] == "SiteH1"

    def test_huawei_columns_do_not_use_nokia_mapping(self, tmp_path):
        """When Huawei schema is chosen, Nokia-only mappings are not applied."""
        cols = list(SCHEMA_1_MAP.keys())
        row = ["src1", "SiteH2", "2024-01-01", "2024-01-02",
               "24:00:00", "50", "Alarm", "Cleared", "LTE", "Huawei"]
        info = self._write_csv(tmp_path, "alarm.csv", cols, [row])
        result = parse_alarm_file(info)
        assert result is not None
        # vendor column should come from Huawei mapping
        assert result.iloc[0]["vendor"] == "Huawei"
