"""
Golden tests for BDT parser core field extraction.

Fixtures are synthetic xlsx files with data placed at the correct Layout A/B
cell positions. Tests assert specific expected values — a change to layout
detection or field positions will surface as a test failure here.
"""

import datetime
from pathlib import Path

import pytest

from alarm_app.bdt.parser import _LAYOUT_A, _LAYOUT_B, _detect_layout, parse_bdt_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Layout A 16-photo fixture (canonical production template) ─────────────────

class TestLayoutA16PhotoCoreFields:
    """Regression tests for core field parsing on the Layout A fixture."""

    @pytest.fixture(scope="class")
    def bdt(self):
        return parse_bdt_file(str(FIXTURES_DIR / "bdt_layout_a_16photo.xlsx"),
                              skip_photos=True)

    def test_site_code(self, bdt):
        assert bdt.site_code == "3938CA"

    def test_test_date(self, bdt):
        assert bdt.test_date == datetime.datetime(2025, 3, 15)

    def test_rectifier_brand(self, bdt):
        assert bdt.rectifier_brand == "Huawei"

    def test_battery_ah(self, bdt):
        assert bdt.battery_ah == 200.0

    def test_battery_voltage(self, bdt):
        assert bdt.battery_voltage == 12.0

    def test_num_batteries(self, bdt):
        assert bdt.num_batteries == 4

    def test_num_strings(self, bdt):
        assert bdt.num_strings == 2

    def test_no_parse_errors(self, bdt):
        assert bdt.errors == []


# ── Layout A 6-photo fixture (same positions, different photo variant) ─────────

class TestLayoutA6PhotoCoreFields:
    """Same assertions on the 6-photo variant — same core positions as 16-photo."""

    @pytest.fixture(scope="class")
    def bdt(self):
        return parse_bdt_file(str(FIXTURES_DIR / "bdt_layout_a_6photo.xlsx"),
                              skip_photos=True)

    def test_site_code(self, bdt):
        assert bdt.site_code == "3938CA"

    def test_test_date(self, bdt):
        assert bdt.test_date == datetime.datetime(2025, 3, 15)

    def test_rectifier_brand(self, bdt):
        assert bdt.rectifier_brand == "Huawei"

    def test_battery_ah(self, bdt):
        assert bdt.battery_ah == 200.0

    def test_num_batteries(self, bdt):
        assert bdt.num_batteries == 4

    def test_no_parse_errors(self, bdt):
        assert bdt.errors == []


# ── Layout B fixture ───────────────────────────────────────────────────────────
#
# NOTE: Layout B cell positions were inferred from old code and have NOT been
# confirmed against real production files. These tests validate the Layout B
# parsing logic against the synthetic fixture. Mark xfail if Layout B is
# found not to exist in production.

class TestLayoutBCoreFields:
    """Core field parsing on the Layout B fixture (unconfirmed in production)."""

    @pytest.fixture(scope="class")
    def bdt(self):
        return parse_bdt_file(str(FIXTURES_DIR / "bdt_layout_b.xlsx"),
                              skip_photos=True)

    def test_site_code(self, bdt):
        assert bdt.site_code == "BST002"

    def test_test_date(self, bdt):
        assert bdt.test_date == datetime.datetime(2024, 11, 20)

    def test_rectifier_brand(self, bdt):
        assert bdt.rectifier_brand == "ZTE"

    def test_battery_ah(self, bdt):
        assert bdt.battery_ah == 100.0

    def test_battery_voltage(self, bdt):
        assert bdt.battery_voltage == 48.0

    def test_no_parse_errors(self, bdt):
        assert bdt.errors == []


# ── _detect_layout unit tests ──────────────────────────────────────────────────

class TestDetectLayout:
    """Unit tests for the layout detection logic."""

    def _make_cell_fn(self, data: dict):
        """Make a cell(row, col) function from a {(row,col): value} dict."""
        def cell(r, c):
            return data.get((r, c))
        return cell

    def test_layout_a_detected_by_site_code_at_l4(self):
        # Site code must match the 4-5 digit + 2 uppercase letter pattern (e.g. 3938CA)
        cell = self._make_cell_fn({(4, 12): "3938CA"})
        result = _detect_layout(cell, max_row=50, max_col=25)
        assert result is _LAYOUT_A

    def test_layout_a_detected_by_date_at_t3(self):
        import datetime
        cell = self._make_cell_fn({(3, 20): datetime.datetime(2025, 1, 1)})
        result = _detect_layout(cell, max_row=50, max_col=25)
        assert result is _LAYOUT_A

    def test_layout_a_detected_by_rectifier_at_l13(self):
        # L4 and T3 are blank, but L13 has a brand name
        cell = self._make_cell_fn({(13, 12): "Huawei"})
        result = _detect_layout(cell, max_row=50, max_col=25)
        assert result is _LAYOUT_A

    def test_layout_b_when_no_signals(self):
        cell = self._make_cell_fn({})
        result = _detect_layout(cell, max_row=50, max_col=25)
        assert result is _LAYOUT_B

    def test_layout_b_when_max_col_less_than_12(self):
        cell = self._make_cell_fn({(4, 9): "BST002"})
        result = _detect_layout(cell, max_row=50, max_col=10)
        assert result is _LAYOUT_B
