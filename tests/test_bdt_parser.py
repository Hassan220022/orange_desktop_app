"""
Tests for alarm_app.bdt_parser — BDT file parsing and helper functions.

Uses unittest.mock to avoid any real file I/O or calamine/openpyxl dependency.
Does NOT import PyQt5.
"""

import datetime
import math
import sys
from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

from alarm_app.bdt_parser import (
    BDTData,
    PhotoSlot,
    _parse_battery_info,
    _parse_test_date,
    _safe_float,
    _safe_str,
    parse_bdt_file,
)


# ═══════════════════════════════════════════════════════════════════════
# 1. _safe_float()
# ═══════════════════════════════════════════════════════════════════════

class TestSafeFloat:
    def test_normal_float(self):
        assert _safe_float(12.5) == 12.5

    def test_integer(self):
        assert _safe_float(7) == 7.0

    def test_string_with_ah_suffix(self):
        assert _safe_float("170AH") == 170.0

    def test_string_with_v_suffix(self):
        assert _safe_float("48V") == 48.0

    def test_string_with_space_and_ah(self):
        assert _safe_float("100 AH") == 100.0

    def test_string_with_vdc_suffix(self):
        assert _safe_float("52.3VDC") == 52.3

    def test_string_with_am_suffix(self):
        assert _safe_float("25AM") == 25.0

    def test_string_with_a_suffix(self):
        assert _safe_float("10.5A") == 10.5

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_garbage_string_returns_none(self):
        assert _safe_float("abc") is None

    def test_nan_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test_string_with_comma(self):
        assert _safe_float("1,5") == 1.5

    def test_string_with_comma_and_suffix(self):
        assert _safe_float("1,5V") == 1.5

    def test_zero(self):
        assert _safe_float(0) == 0.0

    def test_negative_float(self):
        assert _safe_float(-3.2) == -3.2

    def test_empty_string_returns_none(self):
        assert _safe_float("") is None

    def test_whitespace_only_returns_none(self):
        assert _safe_float("   ") is None

    def test_case_insensitive_suffix(self):
        assert _safe_float("48v") == 48.0
        assert _safe_float("170ah") == 170.0
        assert _safe_float("170Ah") == 170.0


# ═══════════════════════════════════════════════════════════════════════
# 2. _safe_str()
# ═══════════════════════════════════════════════════════════════════════

class TestSafeStr:
    def test_normal_string(self):
        assert _safe_str("hello") == "hello"

    def test_string_is_stripped(self):
        assert _safe_str("  hello  ") == "hello"

    def test_none_returns_empty(self):
        assert _safe_str(None) == ""

    def test_nan_string_returns_empty(self):
        assert _safe_str("nan") == ""

    def test_nan_uppercase_returns_empty(self):
        assert _safe_str("NaN") == ""

    def test_nan_allcaps_returns_empty(self):
        assert _safe_str("NAN") == ""

    def test_numeric_value_converted_to_string(self):
        assert _safe_str(42) == "42"

    def test_float_value_converted_to_string(self):
        assert _safe_str(3.14) == "3.14"

    def test_empty_string_stays_empty(self):
        assert _safe_str("") == ""

    def test_whitespace_only_returns_empty(self):
        assert _safe_str("   ") == ""


# ═══════════════════════════════════════════════════════════════════════
# 3. _parse_test_date()
# ═══════════════════════════════════════════════════════════════════════

class TestParseTestDate:
    def test_date_object_from_calamine(self):
        """Calamine returns datetime.date objects for date-only cells."""
        d = datetime.date(2026, 1, 12)
        result = _parse_test_date(d, "file.xlsx")
        assert result == datetime.datetime(2026, 1, 12)
        assert isinstance(result, datetime.datetime)

    def test_datetime_returned_as_is(self):
        dt = datetime.datetime(2026, 1, 12, 10, 0)
        result = _parse_test_date(dt, "file.xlsx")
        assert result is dt

    def test_string_iso_format(self):
        result = _parse_test_date("2026-01-12", "file.xlsx")
        assert result == datetime.datetime(2026, 1, 12)

    def test_string_dmy_format(self):
        result = _parse_test_date("12-01-2026", "file.xlsx")
        assert result == datetime.datetime(2026, 1, 12)

    def test_string_dmy_slash_format(self):
        result = _parse_test_date("12/01/2026", "file.xlsx")
        assert result == datetime.datetime(2026, 1, 12)

    def test_time_object_falls_through_to_filename(self):
        """datetime.time has no date info — should fall through to filename."""
        t = datetime.time(11, 0)
        result = _parse_test_date(t, "BDT 14-1-2026.xlsx")
        assert result == datetime.datetime(2026, 1, 14)

    def test_datetime_1900_falls_through_to_filename(self):
        """Year <= 1900 is treated as garbage (Excel epoch artifact)."""
        dt = datetime.datetime(1900, 1, 1, 10, 59, 51)
        result = _parse_test_date(dt, "BDT 14-1-2026.xlsx")
        assert result == datetime.datetime(2026, 1, 14)

    def test_filename_fallback_parses_date(self):
        result = _parse_test_date(None, "BDT 14-1-2026.xlsx")
        assert result == datetime.datetime(2026, 1, 14)

    def test_filename_no_date_bad_cell_returns_none(self):
        result = _parse_test_date("not a date", "BDT_no_date.xlsx")
        assert result is None

    def test_none_cell_no_date_in_filename_returns_none(self):
        result = _parse_test_date(None, "random_file.xlsx")
        assert result is None

    def test_date_year_1900_no_filename_fallback_returns_none(self):
        """Year <= 1900 with no filename date gives None."""
        d = datetime.date(1900, 1, 1)
        result = _parse_test_date(d, "no_date.xlsx")
        assert result is None

    def test_string_with_datetime_format(self):
        result = _parse_test_date("2026-01-12 14:30:00", "file.xlsx")
        assert result == datetime.datetime(2026, 1, 12, 14, 30, 0)


# ═══════════════════════════════════════════════════════════════════════
# 4. _parse_battery_info()
# ═══════════════════════════════════════════════════════════════════════

class TestParseBatteryInfo:
    @staticmethod
    def _make_cell_fn(cell_map):
        """Build a cell_fn from a dict of (row, col) -> value."""
        def cell_fn(row, col):
            return cell_map.get((row, col))
        return cell_fn

    def test_fixed_positions_return_correct_values(self):
        """Fixed-position cells at rows 40/44/46/48, col 9."""
        cell_map = {
            (40, 9): "Lithium",
            (44, 9): 48.0,
            (46, 9): "100 AH",
            (48, 9): 2.0,
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_brand == "Lithium"
        assert data.battery_voltage == 48.0
        assert data.battery_ah == 100.0
        assert data.num_strings == 2

    def test_keyword_fallback_when_fixed_positions_empty(self):
        """If fixed positions are empty, keyword scanning finds values."""
        cell_map = {
            # Fixed positions all None (not in map)
            # Keyword rows in range 35-65
            (50, 1): "Battery brand",
            (50, 9): "Narada",
            (52, 1): "Battery nominal voltage",
            (52, 9): 48.0,
            (54, 2): "Battery ampere hour",
            (54, 9): "200AH",
            (56, 1): "Number of strings",
            (56, 9): 4.0,
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_brand == "Narada"
        assert data.battery_voltage == 48.0
        assert data.battery_ah == 200.0
        assert data.num_strings == 4

    def test_brand_keyword_detection_when_explicit_brand_empty(self):
        """When no explicit brand is found, scan for manufacturer keywords."""
        cell_map = {
            # No brand at row 40, no "Battery brand" keyword
            # But "huawei" appears somewhere in rows 35-65
            (38, 1): "huawei LFP battery",
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_brand == "huawei LFP battery"

    def test_all_empty_gives_defaults(self):
        """No data at all → brand empty, others None."""
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn({}), data)

        assert data.battery_brand == ""
        assert data.battery_ah is None
        assert data.battery_voltage is None
        assert data.num_strings is None

    def test_brand_keyword_in_col_9(self):
        """Brand keyword found in column 9."""
        cell_map = {
            (42, 9): "Shoto lithium pack",
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        # "shoto" is a known brand keyword, found in col 9
        assert "Shoto" in data.battery_brand

    def test_negative_voltage_ignored(self):
        """Negative values should not be accepted (parsed > 0 check)."""
        cell_map = {
            (44, 9): -48.0,
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_voltage is None

    def test_zero_ah_ignored(self):
        """Zero values should not be accepted (parsed > 0 check)."""
        cell_map = {
            (46, 9): 0.0,
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_ah is None

    def test_keyword_in_col2_fallback(self):
        """Keyword label found in col 2 when col 1 is empty."""
        cell_map = {
            (60, 2): "Battery ampere hour",
            (60, 9): "150AH",
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_ah == 150.0


# ═══════════════════════════════════════════════════════════════════════
# 5. parse_bdt_file()
# ═══════════════════════════════════════════════════════════════════════

def _make_calamine_mock(sheet_names, rows=None):
    """Build a mock python_calamine module that returns the given data.

    Args:
        sheet_names: list of sheet name strings the workbook should report.
        rows: 2D list for ``get_sheet_by_name("BDT sheet").to_python()``.
              Pass None when the sheet should not exist.

    Returns:
        A mock module suitable for injection into ``sys.modules``.
    """
    mock_sheet = MagicMock()
    if rows is not None:
        mock_sheet.to_python.return_value = rows

    mock_wb = MagicMock()
    mock_wb.sheet_names = sheet_names
    mock_wb.get_sheet_by_name.return_value = mock_sheet

    mock_module = MagicMock()
    mock_module.CalamineWorkbook.from_path.return_value = mock_wb
    return mock_module


class TestParseBdtFile:
    """Tests for parse_bdt_file().

    python_calamine is imported *inside* the function (``import python_calamine``),
    so we inject a mock module into ``sys.modules["python_calamine"]`` for tests
    that exercise the calamine path.
    """

    def _run_with_calamine(self, file_path, sheet_names, rows=None,
                           skip_photos=True):
        """Helper: inject calamine mock, call parse_bdt_file, clean up."""
        mock_mod = _make_calamine_mock(sheet_names, rows)
        saved = sys.modules.get("python_calamine")
        sys.modules["python_calamine"] = mock_mod
        try:
            return parse_bdt_file(file_path, skip_photos=skip_photos)
        finally:
            if saved is None:
                sys.modules.pop("python_calamine", None)
            else:
                sys.modules["python_calamine"] = saved

    def test_missing_bdt_sheet_returns_error(self):
        """File with no 'BDT sheet' -> BDTData with error."""
        result = self._run_with_calamine(
            "/fake/path/test.xlsx",
            sheet_names=["Sheet1", "Other"],
        )

        assert len(result.errors) == 1
        assert "Missing 'BDT sheet'" in result.errors[0]
        assert result.filename == "test.xlsx"

    def test_calamine_returns_known_rows(self):
        """Mock calamine to return known rows and verify extraction."""
        # Build a grid large enough: 70 rows x 20 cols, all None
        rows = [[None] * 20 for _ in range(70)]

        # Site info: site_name at (4,3) -> row index 3, col index 2
        rows[3][2] = "Test Site Alpha"
        # site_code at (4,9) -> row index 3, col index 8
        rows[3][8] = "TSA001"
        # test_date at (3,15) -> row index 2, col index 14
        rows[2][14] = datetime.date(2026, 3, 10)
        # time_in at (4,15) -> row index 3, col index 14
        rows[3][14] = "08:00"
        # time_out at (5,15) -> row index 4, col index 14
        rows[4][14] = "17:00"

        # Discharge test header at row 10 (1-indexed) -> index 9, col 2 -> index 1
        rows[9][1] = "Batteries discharge test"
        # "Before disconnecting Rectifier" at row 13 col 1 -> index 12, col 0
        rows[12][0] = "Before disconnecting Rectifier"
        # Start voltage at (13, 4) -> index 12, col 3
        rows[12][3] = 52.4
        # Start ampere at (13, 5) -> index 12, col 4
        rows[12][4] = 15.2
        # String currents at cols 7,9,...,21 (1-indexed) -> indices 6,8,...
        rows[12][6] = 0.2
        rows[12][8] = 0.35
        rows[12][10] = 0.4

        # Discharge reading at row 14 (1-indexed) -> index 13
        rows[13][0] = "5 min"
        rows[13][3] = 51.8
        rows[13][4] = 14.9

        # After connecting at row 15 -> index 14
        rows[14][0] = "After connecting rectifier"
        rows[14][3] = 53.0
        rows[14][4] = 0.5

        # Battery info at fixed positions
        rows[39][8] = "Narada"   # row 40, col 9
        rows[43][8] = 48.0      # row 44, col 9
        rows[45][8] = "100AH"   # row 46, col 9
        rows[47][8] = 2.0       # row 48, col 9

        result = self._run_with_calamine(
            "/fake/path/BDT 10-3-2026.xlsx",
            sheet_names=["BDT sheet"],
            rows=rows,
        )

        assert result.errors == []
        assert result.site_name == "Test Site Alpha"
        assert result.site_code == "TSA001"
        assert result.test_date == datetime.datetime(2026, 3, 10)
        assert result.time_in == "08:00"
        assert result.time_out == "17:00"
        assert result.start_voltage == 52.4
        assert result.start_ampere == 15.2
        assert result.after_reconnect_voltage == 53.0
        assert result.after_reconnect_ampere == 0.5
        assert result.ibat_before_test == 0.4
        assert result.starting_ibattery_ampere == 0.4
        assert result.battery_brand == "Narada"
        assert result.battery_voltage == 48.0
        assert result.battery_ah == 100.0
        assert result.num_strings == 2
        assert len(result.discharge_readings) == 1
        assert result.discharge_readings[0] == ("5 min", 51.8, 14.9)
        assert result.discharge_minutes == 5.0
        assert result.end_voltage == 51.8
        assert result.end_ampere == 14.9
        assert result.photos_deferred is True

    def test_discharge_table_finds_before_disconnecting(self):
        """Verify scanning finds 'Before disconnecting Rectifier' row."""
        rows = [[None] * 10 for _ in range(70)]

        # Discharge header at row 20
        rows[19][1] = "Batteries discharge test"
        # "Before disconnecting Rectifier" at row 22 (within +10 range)
        rows[21][0] = "Before disconnecting Rectifier"
        rows[21][3] = 50.0  # voltage
        rows[21][4] = 10.0  # ampere

        # Next row: "After connecting" immediately
        rows[22][0] = "After connecting rectifier"
        rows[22][3] = 51.0
        rows[22][4] = 1.0

        result = self._run_with_calamine(
            "/fake/test.xlsx",
            sheet_names=["BDT sheet"],
            rows=rows,
        )

        assert result.start_voltage == 50.0
        assert result.start_ampere == 10.0
        assert result.after_reconnect_voltage == 51.0

    def test_calamine_import_fails_falls_back_to_openpyxl(self):
        """When calamine is not installed, openpyxl fallback kicks in."""
        # Ensure python_calamine is NOT in sys.modules so the local import fails
        saved = sys.modules.pop("python_calamine", None)
        try:
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "python_calamine":
                    raise ImportError("No module named 'python_calamine'")
                return original_import(name, *args, **kwargs)

            mock_ws = MagicMock()
            mock_ws.max_row = 5
            mock_ws.max_column = 5
            mock_ws.iter_rows.return_value = [
                [MagicMock(value=None) for _ in range(5)]
                for _ in range(5)
            ]

            mock_owb = MagicMock()
            mock_owb.sheetnames = ["BDT sheet"]
            mock_owb.__getitem__ = MagicMock(return_value=mock_ws)

            with patch("builtins.__import__", side_effect=mock_import):
                with patch("alarm_app.bdt_parser.load_workbook",
                           return_value=mock_owb):
                    result = parse_bdt_file("/fake/file.xlsx",
                                            skip_photos=True)

            assert result.errors == []
            assert result.photos_deferred is True
            mock_owb.close.assert_called_once()
        finally:
            if saved is not None:
                sys.modules["python_calamine"] = saved

    def test_openpyxl_missing_bdt_sheet(self):
        """openpyxl fallback also detects missing 'BDT sheet'."""
        saved = sys.modules.pop("python_calamine", None)
        try:
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "python_calamine":
                    raise ImportError
                return original_import(name, *args, **kwargs)

            mock_owb = MagicMock()
            mock_owb.sheetnames = ["Sheet1"]

            with patch("builtins.__import__", side_effect=mock_import):
                with patch("alarm_app.bdt_parser.load_workbook",
                           return_value=mock_owb):
                    result = parse_bdt_file("/fake/file.xlsx",
                                            skip_photos=True)

            assert "Missing 'BDT sheet'" in result.errors[0]
            mock_owb.close.assert_called_once()
        finally:
            if saved is not None:
                sys.modules["python_calamine"] = saved

    def test_file_cannot_be_opened(self):
        """When both calamine and openpyxl fail to open the file."""
        saved = sys.modules.pop("python_calamine", None)
        try:
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "python_calamine":
                    raise ImportError
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with patch("alarm_app.bdt_parser.load_workbook",
                           side_effect=Exception("corrupt file")):
                    result = parse_bdt_file("/fake/corrupt.xlsx",
                                            skip_photos=True)

            assert any("Cannot open file" in e for e in result.errors)
        finally:
            if saved is not None:
                sys.modules["python_calamine"] = saved

    def test_calamine_open_succeeds_but_sheet_read_fails_then_openpyxl_fallback(self):
        """If calamine opens but fails reading rows, fallback to openpyxl."""
        mock_wb = MagicMock()
        mock_wb.sheet_names = ["BDT sheet"]
        mock_wb.get_sheet_by_name.side_effect = RuntimeError("sheet read failed")

        mock_mod = MagicMock()
        mock_mod.CalamineWorkbook.from_path.return_value = mock_wb

        saved = sys.modules.get("python_calamine")
        sys.modules["python_calamine"] = mock_mod
        try:
            mock_ws = MagicMock()
            mock_ws.max_row = 2
            mock_ws.max_column = 2
            mock_ws.iter_rows.return_value = [
                [MagicMock(value=None), MagicMock(value=None)],
                [MagicMock(value=None), MagicMock(value=None)],
            ]
            mock_owb = MagicMock()
            mock_owb.sheetnames = ["BDT sheet"]
            mock_owb.__getitem__ = MagicMock(return_value=mock_ws)

            with patch("alarm_app.bdt_parser.load_workbook", return_value=mock_owb):
                result = parse_bdt_file("/fake/fallback.xlsx", skip_photos=True)

            assert result.errors == []
            assert result.photos_deferred is True
            mock_owb.close.assert_called_once()
        finally:
            if saved is None:
                sys.modules.pop("python_calamine", None)
            else:
                sys.modules["python_calamine"] = saved

    def test_filename_preserved(self):
        """BDTData.filename is set from os.path.basename."""
        result = self._run_with_calamine(
            "/long/path/to/BDT 5-2-2026.xlsx",
            sheet_names=["SomeOther"],
        )

        assert result.filename == "BDT 5-2-2026.xlsx"
        assert result.file_path == "/long/path/to/BDT 5-2-2026.xlsx"

    def test_no_discharge_table(self):
        """File with no 'Batteries discharge test' header."""
        rows = [[None] * 10 for _ in range(70)]
        rows[3][2] = "Site X"
        rows[3][8] = "SX01"

        result = self._run_with_calamine(
            "/fake/test.xlsx",
            sheet_names=["BDT sheet"],
            rows=rows,
        )

        assert result.site_name == "Site X"
        assert result.start_voltage is None
        assert result.discharge_readings == []
        assert result.discharge_minutes == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 6. BDTData dataclass
# ═══════════════════════════════════════════════════════════════════════

class TestBDTDataDefaults:
    def test_default_string_fields_are_empty(self):
        data = BDTData()
        assert data.file_path == ""
        assert data.filename == ""
        assert data.site_code == ""
        assert data.site_name == ""
        assert data.time_in == ""
        assert data.time_out == ""
        assert data.battery_brand == ""

    def test_default_none_fields(self):
        data = BDTData()
        assert data.test_date is None
        assert data.start_voltage is None
        assert data.start_ampere is None
        assert data.end_voltage is None
        assert data.end_ampere is None
        assert data.after_reconnect_voltage is None
        assert data.after_reconnect_ampere is None
        assert data.ibat_before_test is None
        assert data.starting_ibattery_ampere is None
        assert data.battery_ah is None
        assert data.battery_voltage is None
        assert data.num_strings is None
        assert data.door_alarm_condition is None

    def test_default_numeric_fields(self):
        data = BDTData()
        assert data.discharge_minutes == 0.0
        assert data.photo_count == 0
        assert data.photos_deferred is False

    def test_default_list_fields(self):
        data = BDTData()
        assert data.discharge_readings == []
        assert data.photo_slots == []
        assert data.errors == []

    def test_list_fields_are_independent_instances(self):
        """Each BDTData instance gets its own list (not shared)."""
        a = BDTData()
        b = BDTData()
        a.discharge_readings.append(("5 min", 50.0, 10.0))
        assert b.discharge_readings == []

    def test_fields_are_mutable(self):
        data = BDTData()
        data.site_code = "ABC123"
        data.battery_voltage = 48.0
        data.discharge_minutes = 120.5
        data.test_date = datetime.datetime(2026, 6, 15)
        data.errors.append("test error")

        assert data.site_code == "ABC123"
        assert data.battery_voltage == 48.0
        assert data.discharge_minutes == 120.5
        assert data.test_date == datetime.datetime(2026, 6, 15)
        assert data.errors == ["test error"]

    def test_construction_with_kwargs(self):
        data = BDTData(
            file_path="/some/path.xlsx",
            filename="path.xlsx",
            site_code="S001",
            site_name="My Site",
        )
        assert data.file_path == "/some/path.xlsx"
        assert data.filename == "path.xlsx"
        assert data.site_code == "S001"
        assert data.site_name == "My Site"
        # Others still default
        assert data.test_date is None
        assert data.discharge_readings == []

    def test_photo_slot_defaults(self):
        slot = PhotoSlot(label="Test Label")
        assert slot.label == "Test Label"
        assert slot.image_data is None
        assert slot.image_ext == ""
        assert slot.category == "other"
