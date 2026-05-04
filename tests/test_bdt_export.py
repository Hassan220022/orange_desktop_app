"""Tests for alarm_app.bdt_export."""

from datetime import datetime

from alarm_app.bdt.export import build_bdt_export_sheets
from alarm_app.bdt.parser import BDTData
from alarm_app.bdt.validator import RuleResult, ValidationResult
from alarm_app.constants import (
    BDT_SUMMARY_EXPORT_HEADERS,
    BDT_SUMMARY_SHEET_NAME,
    format_bdt_rule_label,
)


def _make_result(
    *,
    summary_data: dict[str, str] | None = None,
    rules: list[RuleResult] | None = None,
    overall: str = "Accepted",
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
        overall=overall,
        rules=rules or [],
        parse_errors=[],
        bdt_data=bdt,
    )


class TestBDTExport:
    def test_builds_validation_rule_and_summary_sheets(self):
        res = _make_result(summary_data={"Week": "W1", "Short Code": "0167DE"})
        sheets = build_bdt_export_sheets([res], health_pct=0.8)

        assert list(sheets.keys()) == [
            "Validation Results",
            "Rule Evidence",
            BDT_SUMMARY_SHEET_NAME,
        ]
        validation_headers = list(sheets["Validation Results"].columns)
        assert validation_headers[:5] == [
            "File",
            "Site Code",
            "Test Date",
            "Verdict",
            "Verdict Reason",
        ]
        assert format_bdt_rule_label("R1", "Photos") in validation_headers
        assert f"{format_bdt_rule_label('R1', 'Photos')} - Detail" in validation_headers
        assert list(sheets[BDT_SUMMARY_SHEET_NAME].columns) == BDT_SUMMARY_EXPORT_HEADERS
        assert len(sheets["Rule Evidence"].columns) == 8

    def test_validation_sheet_exports_rule_verdicts_and_details(self):
        res = _make_result(
            overall="Rejected",
            rules=[
                RuleResult("R1", "Photos", False, "Rejected", "AI-generated photo signal detected"),
                RuleResult("R2", "Power Alarm + Duration", True, "Accepted", "Matched window"),
                RuleResult("R10", "Door Alarm Condition", None, "N/A", "No alarm data loaded"),
            ],
            end_voltage=46.25,
            battery_brand="Narada",
        )

        row = build_bdt_export_sheets([res], health_pct=0.8)["Validation Results"].iloc[0]

        assert row["Verdict"] == "Rejected"
        assert row["Verdict Reason"] == (
            "R1 - Photos: AI-generated photo signal detected | "
            "R10 - Door Alarm Condition: No alarm data loaded"
        )
        assert row["R1 - Photos"] == "Rejected"
        assert row["R2 - Power Alarm + Duration"] == "Accepted"
        assert row["R10 - Door Alarm Condition"] == "No data"
        assert row["R1 - Photos - Detail"] == "AI-generated photo signal detected"
        assert row["R2 - Power Alarm + Duration - Detail"] == ""
        assert row["R10 - Door Alarm Condition - Detail"] == "No alarm data loaded"
        assert row["End Rectifier Voltage (V)"] == "46.25"
        assert row["Lead-acid SOH (%)"] == "80"

    def test_validation_sheet_includes_revise_reasons_in_verdict_reason(self):
        res = _make_result(
            overall="Revise",
            rules=[
                RuleResult("R1", "Photos", False, "Revise", "Missing 2 photos"),
                RuleResult("R8", "Sizing vs Actual", False, "Revise", "Actual runtime below sizing expectation"),
            ],
        )

        row = build_bdt_export_sheets([res], health_pct=0.8)["Validation Results"].iloc[0]

        assert row["Verdict Reason"] == (
            "R1 - Photos: Missing 2 photos | "
            "R8 - Sizing vs Actual: Actual runtime below sizing expectation"
        )

    def test_rule_evidence_sheet_expands_one_row_per_rule(self):
        res = _make_result(
            overall="Revise",
            rules=[
                RuleResult("R1", "Photos", False, "Revise", "Missing 2 photos"),
                RuleResult("R8", "Sizing vs Actual", True, "Accepted", "Within sizing window"),
            ],
        )

        sheet = build_bdt_export_sheets([res], health_pct=0.8)["Rule Evidence"]

        assert len(sheet) == 1
        assert list(sheet["Rule ID"]) == ["R1"]
        assert list(sheet["Rule Verdict"]) == ["Revise"]
        assert list(sheet["Overall Verdict"]) == ["Revise"]

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
        assert row["Charging current"] == "30"
        assert row["PLD Value"] == "44"
        assert row["Site Category"] == "URBAN"
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

    def test_pm_summary_normalizes_week_ser_dates_and_numeric_cells(self):
        res = _make_result(
            summary_data={
                "Week": "W00",
                "Ser": "",
                "Site Category": "out door",
                "Type": "Bronze",
                "Power Source": "et dg",
                "Reason for Repeated BDT": "cycle",
                "# of BTS": "Huawei",
                "BSC Type": "0.0",
                "Battery Volt": "48V",
                "Battery Ampere Hour": "100AH",
                "Discharge time( Mins)": "65 min",
                "Test Date": "13-1-2026",
            }
        )
        row = build_bdt_export_sheets([res], health_pct=0.8)[BDT_SUMMARY_SHEET_NAME].iloc[0]

        assert row["Week"] == "W03"
        assert row["Ser"] == "1"
        assert row["Test Date"] == "2026-01-13"
        assert row["Site Category"] == "OUTDOOR"
        assert row["Type"] == "BRONZE"
        assert row["Power Source"] == "ET+DG"
        assert row["Reason for Repeated BDT"] == "Cycle"
        assert row["# of BTS"] == ""
        assert row["BSC Type"] == ""
        assert row["Battery Volt"] == "48"
        assert row["Battery Ampere Hour"] == "100"
        assert row["Discharge time( Mins)"] == "65"
