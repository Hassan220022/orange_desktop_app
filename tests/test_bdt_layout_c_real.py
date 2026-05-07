"""
Tests for Layout C (BDT sheet) parsing against the real 0167DE production file.

Skipped automatically when the file is not present on disk.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REAL_FILE = (
    "/Users/mikawi/Developer/orange/data/test_pms/"
    "BDT_ Lithium (DK-MANS-SADATBSC _0167DE BDT Test Date (11-1-2026).xlsx"
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(REAL_FILE),
    reason="Production file not present on this machine",
)


def _parse():
    from bdt.parser import parse_bdt_file
    return parse_bdt_file(REAL_FILE)


def test_site_code():
    result = _parse()
    assert result.site_code == "0167DE"


def test_rectifier_brand():
    result = _parse()
    assert result.rectifier_brand == "Delta 2", (
        f"Expected 'Delta 2', got {result.rectifier_brand!r}"
    )


def test_num_modules():
    result = _parse()
    assert result.num_modules == 3


def test_battery_brand():
    result = _parse()
    assert result.battery_brand is not None
    assert result.battery_brand.lower() == "lithium"


def test_battery_ah():
    result = _parse()
    assert result.battery_ah == 100.0


def test_battery_voltage():
    result = _parse()
    assert result.battery_voltage == 48.0


def test_core_layout_family():
    result = _parse()
    assert result.core_layout_family == "C"
