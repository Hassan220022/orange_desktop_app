"""Tests for alarm_app.bdt_export."""

from datetime import datetime

from alarm_app.bdt_export import build_bdt_export_sheets
from alarm_app.bdt_parser import BDTData
from alarm_app.bdt_validator import ValidationResult
from alarm_app.constants import BDT_SUMMARY_EXPORT_HEADERS, BDT_SUMMARY_SHEET_NAME


def _make_result(
    *,
    summary_data: dict[str, str] | None = None,
    **bdt_overrides,
) -> ValidationResult:
    bdt_defaults = {
        "file_path": "/data/bdt/0167DE_BDT.xlsx",
        "filename": "0167DE_BDT.xlsx",
        "site_code": "0167DE",
        "site_name": "Test Site",
        "test_date": datetime(2026, 1, 11),
        "summary_data": summary_data or {},
    }
    bdt_defaults.update(bdt_overrides)
    bdt = BDTData(**bdt_defaults)
    return ValidationResult(
        filename=bdt.filename,
        site_code=bdt.site_code,
        test_date="2026-01-11",
        overall="Accepted",
        rules=[],
        parse_errors=[],
        bdt_data=bdt,
    )


class TestBDTExport:
    def test_builds_single_weekly_sheet_with_expected_headers(self):
        res = _make_result(summary_data={"Week": "W1", "Short Code": "0167DE"})
        sheets = build_bdt_export_sheets([res], health_pct=0.8)

        assert list(sheets.keys()) == [BDT_SUMMARY_SHEET_NAME]
        assert list(sheets[BDT_SUMMARY_SHEET_NAME].columns) == BDT_SUMMARY_EXPORT_HEADERS
        assert len(sheets[BDT_SUMMARY_SHEET_NAME].columns) == 53

    def test_pm_summary_reads_normal_summary_keys(self):
        res = _make_result(
            summary_data={
                "Week": "W10",
                "Site Name": "Summary Site Name",
                "Short Code": "9999ZZ",
                "Battery Brand": "SummaryBrand",
                "Test Date": "2026-02-01",
            }
        )
        row = build_bdt_export_sheets([res], health_pct=0.8)[BDT_SUMMARY_SHEET_NAME].iloc[0]

        assert row["Week"] == "W10"
        assert row["Site Name"] == "Summary Site Name"
        assert row["Short Code"] == "9999ZZ"
        assert row["Battery Brand"] == "SummaryBrand"
        assert row["Test Date"] == "2026-02-01"

    def test_pm_summary_handles_variants_typos_and_spaces(self):
        res = _make_result(
            summary_data={
                " Type2 ": "Macro BTS",
                "Cap request #": "CR-22",
                "Reason for Test stop ": "Load issue",
                "Batteries Charnging current limit": "30A",
                "PLVD Value (LVD disconnect value)": "44.0",
                "Site Category and Type": "Urban",
                "AC HP": "15",
                "AC HP3": "18",
            }
        )
        row = build_bdt_export_sheets([res], health_pct=0.8)[BDT_SUMMARY_SHEET_NAME].iloc[0]

        assert row["BTS Type"] == "Macro BTS"
        assert row["CAP request "] == "CR-22"
        assert row["Reason for Stop BDT"] == "Load issue"
        assert row["Charging current"] == "30A"
        assert row["PLD Value"] == "44.0"
        assert row["Site Category"] == "Urban"
        assert row["AC1 HP"] == "15"
        assert row["AC2 HP"] == "18"

    def test_pm_summary_uses_bdt_fallbacks_when_summary_missing(self):
        res = _make_result(
            summary_data={"Battery Brand": "SummaryBrand"},
            site_code="4415DE",
            site_name="Fallback Site",
            test_date=datetime(2026, 3, 1),
            rectifier_brand="Delta",
            num_modules=4,
            battery_brand="FallbackBrand",
            battery_voltage=48.0,
            battery_ah=200.0,
            num_strings=2,
            num_batteries=24,
            start_voltage=54.2,
            start_ampere=22.4,
            end_voltage=47.1,
            end_ampere=21.7,
            discharge_minutes=180.0,
            pld_value="44",
        )
        row = build_bdt_export_sheets([res], health_pct=0.8)[BDT_SUMMARY_SHEET_NAME].iloc[0]

        assert row["Short Code"] == "4415DE"
        assert row["Site Name"] == "Fallback Site"
        assert row["Test Date"] == "2026-03-01"
        assert row["Rectifier Brand"] == "Delta"
        assert row["# of Modules"] == "4"
        assert row["Battery Brand"] == "SummaryBrand"
        assert row["Battery Volt"] == "48"
        assert row["Battery Ampere Hour"] == "200"
        assert row["No of String"] == "2"
        assert row["No of Batteries "] == "24"
        assert row["Start Volt"] == "54.2"
        assert row["Start Amp"] == "22.4"
        assert row["End Volt"] == "47.1"
        assert row["End Amp"] == "21.7"
        assert row["Discharge time( Mins)"] == "180"
        assert row["PLD Value"] == "44"
