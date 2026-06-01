"""
Tests for alarm_app.bdt_parser — BDT file parsing and helper functions.

Uses unittest.mock to avoid any real file I/O or calamine/openpyxl dependency.
Does NOT import PyQt5.
"""

import datetime
import sys
from unittest.mock import MagicMock, patch

from alarm_app.bdt.models import Section, SectionImage, WorkbookParseManifest
from alarm_app.bdt.parser import (
    BDTData,
    PhotoSlot,
    _extract_photo_slots,
    _extract_photo_slots_structural,
    _parse_battery_info,
    _parse_summary_sheet,
    _parse_test_date,
    _resolve_bdt_sheet_name,
    _safe_float,
    _safe_str,
    load_bdt_photos,
    parse_bdt_file,
)


def test_photo_extraction_uses_structural_only():
    # The legacy ``_extract_photo_slots_layout`` was removed; only the
    # structural OOXML path remains.  Verify the active wrapper still
    # routes through it.
    with patch("alarm_app.bdt.parser._extract_photo_slots_structural") as structural:
        structural.return_value = ([], 0, "LAYOUT_PHOTO_6", 6, "low", "structural", [])
        result = _extract_photo_slots("/fake/file.xlsx", family_guess="A", family_confidence="high")
        structural.assert_called_once()
        assert result[5] == "structural"


class _FakeAnchor:
    def __init__(self, from_row: int, from_col: int, to_row: int, to_col: int, r_id: str, media_path: str):
        self.from_row = from_row
        self.from_col = from_col
        self.to_row = to_row
        self.to_col = to_col
        self.r_id = r_id
        self.media_path = media_path


class _FakeOOXMLPackage:
    def __init__(self, _file_path: str):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read_workbook_xml(self):
        import xml.etree.ElementTree as ET
        return ET.fromstring(
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                 <sheets><sheet name="BDT sheet"/></sheets>
               </workbook>"""
        )

    def resolve_worksheet_xml_path(self, _sheet_name: str):
        return "xl/worksheets/sheet1.xml"

    def parse_shared_strings(self):
        return []

    def parse_worksheet_cells(self, _worksheet_xml_path: str, shared_strings=None):
        return {}, [], {}

    def get_worksheet_drawing_paths(self, _worksheet_xml_path: str):
        return ["xl/drawings/drawing1.xml"]

    def extract_two_cell_anchors(self, _drawing_path: str):
        return [_FakeAnchor(10, 12, 20, 16, "rId1", "xl/media/image1.jpeg")]

    def read_media(self, _media_path: str):
        return b"img-bytes"

    def list_media_files(self):
        return ["xl/media/image1.jpeg"]


class _FakeOOXMLPackageVariableBytes(_FakeOOXMLPackage):
    def __init__(self, _file_path: str):
        super().__init__(_file_path)
        self._read_count = 0

    def read_media(self, _media_path: str):
        self._read_count += 1
        return f"img-bytes-{self._read_count}".encode()


def test_structural_dedupe_keeps_same_media_across_different_sections():
    manifest = WorkbookParseManifest(
        sheet_name="BDT sheet",
        sections=[
            Section(
                section_id="sec_1",
                sheet_name="BDT sheet",
                header_text="Rectifier",
                category="rectifier",
                images=[SectionImage(media_path="xl/media/image1.jpeg")],
            ),
            Section(
                section_id="sec_2",
                sheet_name="BDT sheet",
                header_text="Batteries",
                category="batteries",
                images=[SectionImage(media_path="xl/media/image1.jpeg")],
            ),
        ],
    )
    with patch("alarm_app.bdt.ooxml_reader.OOXMLPackage", _FakeOOXMLPackage), \
         patch("alarm_app.bdt.section_parser.build_workbook_manifest", return_value=manifest):
        slots, *_ = _extract_photo_slots_structural(
            "/fake/file.xlsx",
            family_guess="A",
            family_confidence="high",
            bdt_sheet_name="BDT sheet",
        )
    filled = [s for s in slots if s.image_data]
    assert len(filled) == 2
    assert {s.category for s in filled} == {"rectifier", "batteries"}


def test_structural_dedupe_removes_same_media_within_same_section():
    manifest = WorkbookParseManifest(
        sheet_name="BDT sheet",
        sections=[
            Section(
                section_id="sec_1",
                sheet_name="BDT sheet",
                header_text="Rectifier",
                category="rectifier",
                images=[
                    SectionImage(media_path="xl/media/image1.jpeg"),
                    SectionImage(media_path="xl/media/image1.jpeg"),
                ],
            ),
        ],
    )
    with patch("alarm_app.bdt.ooxml_reader.OOXMLPackage", _FakeOOXMLPackage), \
         patch("alarm_app.bdt.section_parser.build_workbook_manifest", return_value=manifest):
        slots, *_ = _extract_photo_slots_structural(
            "/fake/file.xlsx",
            family_guess="A",
            family_confidence="high",
            bdt_sheet_name="BDT sheet",
        )
    filled = [s for s in slots if s.image_data]
    assert len(filled) == 1


def test_structural_dedupe_keeps_same_path_when_bytes_differ():
    manifest = WorkbookParseManifest(
        sheet_name="BDT sheet",
        sections=[
            Section(
                section_id="sec_1",
                sheet_name="BDT sheet",
                header_text="Rectifier",
                category="rectifier",
                images=[
                    SectionImage(media_path="xl/media/image1.jpeg"),
                    SectionImage(media_path="xl/media/image1.jpeg"),
                ],
            ),
        ],
    )
    with patch("alarm_app.bdt.ooxml_reader.OOXMLPackage", _FakeOOXMLPackageVariableBytes), \
         patch("alarm_app.bdt.section_parser.build_workbook_manifest", return_value=manifest):
        slots, *_ = _extract_photo_slots_structural(
            "/fake/file.xlsx",
            family_guess="A",
            family_confidence="high",
            bdt_sheet_name="BDT sheet",
        )
    filled = [s for s in slots if s.image_data]
    assert len(filled) == 2


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
        """Fixed-position cells use Layout A defaults: brand(28,12), voltage(32,12), ah(34,12), strings(36,12)."""
        cell_map = {
            (28, 12): "Lithium",
            (32, 12): 48.0,
            (34, 12): "100 AH",
            (36, 12): 2.0,
        }
        data = BDTData()
        _parse_battery_info(20, self._make_cell_fn(cell_map), data)

        assert data.battery_brand == "Lithium"
        assert data.battery_voltage == 48.0
        assert data.battery_ah == 100.0
        assert data.num_strings == 2

    def test_keyword_fallback_when_fixed_positions_empty(self):
        """If fixed positions are empty, keyword scanning finds values 1 col right of the label."""
        cell_map = {
            # Fixed positions all None (not in map)
            # Labels at col 11, values at col 12 (Layout A style: 1 col to the right)
            (50, 11): "Battery brand",
            (50, 12): "Narada",
            (52, 11): "Battery nominal voltage",
            (52, 12): 48.0,
            (54, 11): "Battery ampere hour",
            (54, 12): "200AH",
            (56, 11): "Number of strings",
            (56, 12): 4.0,
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
        """Keyword label found in col 2 when col 1 is empty; value is 1 col to the right."""
        cell_map = {
            (60, 2): "Battery ampere hour",
            (60, 3): "150AH",
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

    def test_case_insensitive_bdt_sheet_name_is_accepted(self):
        rows = [[None] * 20 for _ in range(10)]
        rows[3][8] = "4415DE"
        result = self._run_with_calamine(
            "/fake/path/test.xlsx",
            sheet_names=["bdt sheet"],
            rows=rows,
        )
        assert result.errors == []
        assert result.site_code == "4415DE"

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

    def test_site_code_falls_back_to_filename_token_when_sheet_unknown(self):
        rows = [[None] * 20 for _ in range(70)]
        rows[3][8] = "Unknown"  # (4,9) placeholder
        result = self._run_with_calamine(
            "/fake/path/U_S_3938CA_BOLAKDAKROR27_3938CA_BDT.XLSX",
            sheet_names=["BDT sheet"],
            rows=rows,
        )
        assert result.site_code == "3938CA"

    def test_site_code_extracts_token_from_sheet_text(self):
        rows = [[None] * 20 for _ in range(70)]
        rows[3][8] = "Site code: 0482SI"
        result = self._run_with_calamine(
            "/fake/path/random.xlsx",
            sheet_names=["BDT sheet"],
            rows=rows,
        )
        assert result.site_code == "0482SI"

    def test_filename_token_overrides_non_token_sheet_site_code(self):
        rows = [[None] * 20 for _ in range(70)]
        rows[3][8] = "RMS-OLD-FREE-TEXT"
        result = self._run_with_calamine(
            "/fake/path/02186_N_0296CA_KABLATE_0296CA_BDT.XLSX",
            sheet_names=["BDT sheet"],
            rows=rows,
        )
        assert result.site_code == "0296CA"

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
                with patch("alarm_app.bdt.parser.load_workbook",
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
                with patch("alarm_app.bdt.parser.load_workbook",
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
                with patch("alarm_app.bdt.parser.load_workbook",
                           side_effect=Exception("corrupt file")):
                    result = parse_bdt_file("/fake/corrupt.xlsx",
                                            skip_photos=True)

            assert any("Cannot open file" in e for e in result.errors)
        finally:
            if saved is not None:
                sys.modules["python_calamine"] = saved

    def test_missing_file_path_fails_closed(self):
        result = parse_bdt_file("", skip_photos=True)

        assert any("missing file path" in e.lower() for e in result.errors)

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

            with patch("alarm_app.bdt.parser.load_workbook", return_value=mock_owb):
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
        assert data.rectifier_brand == ""
        assert data.pld_value == ""

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
        assert data.num_batteries is None
        assert data.num_modules is None
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
        assert data.string_discharge_readings == []
        assert data.summary_data == {}

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


class TestSummarySheetParsing:
    def test_matches_multisheet_summary_row_by_site_and_date(self):
        class _FakeEngine:
            def sheet_rows(self, sheet_name):
                return {
                    "BDT": [["not", "summary"], ["3868DE", "wrong"]],
                    "Power Alarm": [
                        ["Site", "Date", "Alarm Name"],
                        ["3868DE", "2026-01-05", "Power"],
                    ],
                    "BDT 2025-2026": [
                        ["Short Code", "Test Date", "PLD Value", "Rectifier Brand"],
                        ["1111AA", "2026-01-04", "40", "Wrong"],
                        ["3868DE", "5-Jan-26", "44", "Delta 3"],
                    ],
                }[sheet_name]

        result = _parse_summary_sheet(
            "/fake/file.xlsx",
            ["BDT", "Power Alarm", "BDT 2025-2026"],
            engine=_FakeEngine(),
            match_site="3868DE",
            match_date=datetime.datetime(2026, 1, 5),
            exclude_sheet="BDT",
        )

        assert result["Short Code"] == "3868DE"
        assert result["PLD Value"] == "44"
        assert result["Rectifier Brand"] == "Delta 3"

        iso_result = _parse_summary_sheet(
            "/fake/file.xlsx",
            ["BDT", "Power Alarm", "BDT 2025-2026"],
            engine=_FakeEngine(),
            match_site="1111AA",
            match_date=datetime.datetime(2026, 1, 4),
            exclude_sheet="BDT",
        )
        assert iso_result["Short Code"] == "1111AA"


class TestResolveBdtSheetName:
    def test_exact_match(self):
        assert _resolve_bdt_sheet_name(["BDT sheet", "Other"]) == "BDT sheet"

    def test_case_insensitive_match(self):
        assert _resolve_bdt_sheet_name(["bdt sheet"]) == "bdt sheet"

    def test_flexible_variant_match(self):
        assert _resolve_bdt_sheet_name(["BDT_Sheet(1)"]) == "BDT_Sheet(1)"

    def test_bdt_prefix_match(self):
        assert _resolve_bdt_sheet_name(["BDT-Template"]) == "BDT-Template"

    def test_bdt_filename_fallback_to_first_sheet(self):
        assert _resolve_bdt_sheet_name(
            ["Sheet1", "Data"], "QN-IND-NTH_0630UP_0630UP_BDT.XLSX"
        ) == "Sheet1"

    def test_missing_match(self):
        assert _resolve_bdt_sheet_name(["Sheet1", "Data"], "random.xlsx") is None

    def test_summary_and_bdt_summary_resolves_to_none(self):
        assert _resolve_bdt_sheet_name(["Summary", "BDT Summary"]) is None

    def test_bdt_summary_only_resolves_to_none(self):
        assert _resolve_bdt_sheet_name(["BDT Summary"]) is None

    def test_summary_only_resolves_to_none(self):
        assert _resolve_bdt_sheet_name(["Summary"]) is None

    def test_bdt_and_summary_resolves_bdt(self):
        assert _resolve_bdt_sheet_name(["BDT", "Summary"]) == "BDT"

    def test_filename_fallback_with_summary_first_sheet(self):
        assert _resolve_bdt_sheet_name(
            ["Summary", "Other"], filename="test_bdt_2026.xlsx"
        ) is None

    def test_filename_fallback_with_non_summary_first_sheet(self):
        assert _resolve_bdt_sheet_name(
            ["Other", "Summary"], filename="test_bdt_2026.xlsx"
        ) is None


def test_load_bdt_photos_handles_missing_file_path():
    bdt = BDTData(file_path="", filename="")
    bdt.photos_deferred = True

    load_bdt_photos(bdt)

    assert bdt.photo_slots == []
    assert bdt.photo_count == 0
    assert bdt.photo_detection_mode == "unavailable"
    assert bdt.photos_deferred is False


# ═══════════════════════════════════════════════════════════════════════
# 8. String discharge readings
# ═══════════════════════════════════════════════════════════════════════

class TestStringDischargeReadings:
    """Tests for per-string (V, A) discharge readings stored alongside bus-bar."""

    def _run_with_calamine(self, file_path, sheet_names, rows=None,
                           skip_photos=True):
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

    def test_two_strings_stored_aligned_with_bus_bar(self):
        """With 2 string columns, string_discharge_readings aligns with discharge_readings."""
        # 70 rows x 22 cols
        rows = [[None] * 22 for _ in range(70)]

        # Discharge header at row 10 (index 9)
        rows[9][1] = "Batteries discharge test"
        # Header row with Rec Bus Bar at col 4 (index 3) and String columns
        rows[10][3] = "Rec Bus Bar"
        # String #1 header at col 6 (index 5), ampere col at 7 (index 6)
        rows[10][5] = "String #1"
        # String #2 header at col 8 (index 7), ampere col at 9 (index 8)
        rows[10][7] = "String #2"

        # "Before disconnecting Rectifier" at row 13 (index 12)
        rows[12][0] = "Before disconnecting Rectifier"
        rows[12][3] = 52.0   # bus bar voltage
        rows[12][4] = 15.0   # bus bar ampere
        rows[12][5] = 51.5   # string 1 voltage
        rows[12][6] = 7.5    # string 1 ampere
        rows[12][7] = 51.8   # string 2 voltage
        rows[12][8] = 7.4    # string 2 ampere

        # Discharge reading at row 14 (index 13): "5 min"
        rows[13][0] = "5 min"
        rows[13][3] = 50.5
        rows[13][4] = 14.0
        rows[13][5] = 50.0   # string 1 voltage
        rows[13][6] = 7.0    # string 1 ampere
        rows[13][7] = 50.2   # string 2 voltage
        rows[13][8] = 6.9    # string 2 ampere

        # "After connecting" at row 15 (index 14)
        rows[14][0] = "After connecting rectifier"
        rows[14][3] = 53.0
        rows[14][4] = 0.5

        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )

        assert len(result.discharge_readings) == 1
        # string_discharge_readings: index 0 = "Before disconnecting" row,
        # index 1 = "5 min" row
        assert len(result.string_discharge_readings) == 2
        # Each entry has 2 (V, A) tuples (one per string)
        for entry in result.string_discharge_readings:
            assert len(entry) == 2
            for pair in entry:
                assert isinstance(pair, tuple)
                assert len(pair) == 2

        # Verify actual values for the "Before disconnecting" row (index 0)
        assert result.string_discharge_readings[0][0] == (51.5, 7.5)
        assert result.string_discharge_readings[0][1] == (51.8, 7.4)
        # Verify "5 min" row (index 1)
        assert result.string_discharge_readings[1][0] == (50.0, 7.0)
        assert result.string_discharge_readings[1][1] == (50.2, 6.9)

    def test_no_string_columns_empty_list(self):
        """When no 'String #' columns detected, string_discharge_readings stays empty."""
        rows = [[None] * 10 for _ in range(70)]

        # Discharge header but no string columns in header row
        rows[9][1] = "Batteries discharge test"
        rows[10][3] = "Rec Bus Bar"
        # No "String" headers

        rows[12][0] = "Before disconnecting Rectifier"
        rows[12][3] = 52.0
        rows[12][4] = 15.0

        rows[13][0] = "5 min"
        rows[13][3] = 50.5
        rows[13][4] = 14.0

        rows[14][0] = "After connecting rectifier"
        rows[14][3] = 53.0
        rows[14][4] = 0.5

        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )

        assert result.string_discharge_readings == []

    def test_none_values_preserved_for_empty_cells(self):
        """Empty string cells produce (None, None) tuples."""
        rows = [[None] * 22 for _ in range(70)]

        rows[9][1] = "Batteries discharge test"
        rows[10][3] = "Rec Bus Bar"
        rows[10][5] = "String #1"

        rows[12][0] = "Before disconnecting Rectifier"
        rows[12][3] = 52.0
        rows[12][4] = 15.0
        # String cols left as None

        rows[13][0] = "5 min"
        rows[13][3] = 50.5
        rows[13][4] = 14.0
        # String cols left as None

        rows[14][0] = "After connecting rectifier"
        rows[14][3] = 53.0
        rows[14][4] = 0.5

        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )

        # Should have entries (before-disconnect + 5 min row)
        assert len(result.string_discharge_readings) == 2
        # Each entry has 1 tuple (one string column) with (None, None)
        assert result.string_discharge_readings[0][0] == (None, None)
        assert result.string_discharge_readings[1][0] == (None, None)


# ═══════════════════════════════════════════════════════════════════════
# 9. New BDT fields (rectifier, modules, batteries, PLVD)
# ═══════════════════════════════════════════════════════════════════════

class TestNewBDTFields:
    """Tests for newly added BDT extraction fields."""

    def _run_with_calamine(self, file_path, sheet_names, rows=None,
                           skip_photos=True):
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

    def _make_rows(self):
        """Build a 70x20 grid of None values."""
        return [[None] * 20 for _ in range(70)]

    def test_rectifier_brand_extracted(self):
        rows = self._make_rows()
        # _LAYOUT_C rectifier_brand = (12, 9) → rows[11][8]
        # (BDT sheet files have empty Excel row 1; calamine row 12 = Excel row 13)
        rows[11][8] = "Delta 2"
        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )
        assert result.rectifier_brand == "Delta 2"

    def test_num_modules_extracted(self):
        rows = self._make_rows()
        # _LAYOUT_C num_modules = (16, 9) → rows[15][8]
        rows[15][8] = 3
        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )
        assert result.num_modules == 3

    def test_num_batteries_extracted(self):
        rows = self._make_rows()
        rows[42][8] = 2  # cell(43, 9) — unchanged in _LAYOUT_C
        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )
        assert result.num_batteries == 2

    def test_pld_value_extracted(self):
        rows = self._make_rows()
        # _LAYOUT_C pld_value = (28, 9) → rows[27][8]
        rows[27][8] = 44
        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )
        assert result.pld_value == "44"

    def test_pld_photo_label_is_not_extracted_as_value(self):
        rows = self._make_rows()
        rows[27][8] = "PLVD set point"
        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )
        assert result.pld_value == ""

    def test_missing_fields_default_to_none(self):
        """When cells are empty, fields stay at their defaults."""
        rows = self._make_rows()
        result = self._run_with_calamine(
            "/fake/test.xlsx", sheet_names=["BDT sheet"], rows=rows,
        )
        assert result.rectifier_brand == ""
        assert result.num_modules is None
        assert result.num_batteries is None
        assert result.pld_value == ""
