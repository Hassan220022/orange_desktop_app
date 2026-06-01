from types import SimpleNamespace

from alarm_app.bdt.validator import RuleResult, ValidationResult
from alarm_app.core.battery_backup_insights import (
    attach_battery_backup_insight,
    build_battery_backup_insight,
)


def test_build_battery_backup_insight_flags_network_bdt_mismatch():
    insight = build_battery_backup_insight(
        site_row={"site_id": "0167DE", "site_name": "Test Site"},
        network_rows=[{
            "site_id": "0167DE",
            "battery_type": "Narada",
            "backup_status": "Good",
            "backup_minutes": 180,
            "no_of_strings": 2,
            "recent_test_date_or_reporting_date": "2026-02-01",
        }],
        bdt_payload={
            "bdt_summary": {"rows": [{}], "returned": 1, "total": 1},
            "bdt_tests": {
                "rows": [{
                    "battery_brand": "Lithium Power",
                    "test_date": "2026-03-01",
                    "discharge_minutes": 70,
                    "num_strings": 1,
                }],
                "returned": 1,
                "total": 1,
            },
            "validation_runs": {"rows": [{"overall_verdict": "Accepted"}], "returned": 1, "total": 1},
            "rule_results": {"rows": [], "returned": 0, "total": 0},
            "photos": {"rows": [{}], "returned": 1, "total": 1},
        },
        min_backup_minutes=90,
        backup_minutes_tolerance=30,
    )

    assert insight["insight_status"] == "Network Summary / BDT Mismatch"
    assert insight["severity"] == "high"
    assert "network_bdt_mismatch" in insight["insight_flags"]
    assert "weak_measured_backup" in insight["insight_flags"]
    assert {diff["field"] for diff in insight["differences"]} >= {
        "battery_type",
        "no_of_strings",
        "backup_minutes",
        "backup_status",
    }
    assert insight["snapshot_freshness"]["status"] == "network_summary_older_than_bdt"
    assert insight["snapshot_freshness"]["network_summary_date"] == "2026-02-01"
    assert insight["snapshot_freshness"]["bdt_test_date"] == "2026-03-01"
    assert "older than the BDT test date" in insight["snapshot_freshness"]["warnings"][0]


def test_attach_battery_backup_insight_adds_runtime_bdt_validation_context():
    bdt_data = SimpleNamespace(
        site_code="0167DE",
        site_name="Test Site",
        test_date="2026-03-01",
        battery_brand="Narada",
        discharge_minutes=60,
        num_strings=2,
        num_batteries=8,
        end_voltage=46.1,
        photo_count=3,
    )
    result = ValidationResult(
        filename="0167DE_BDT.xlsx",
        site_code="0167DE",
        test_date="2026-03-01",
        overall="Rejected",
        rules=[RuleResult("R8", "Sizing vs Actual", False, "Rejected", "Weak backup")],
        bdt_data=bdt_data,
    )

    insight = attach_battery_backup_insight(
        result,
        bdt_data,
        network_rows=[{
            "site_id": "0167DE",
            "battery_type": "Narada",
            "backup_status": "Good",
            "backup_minutes": 120,
            "no_of_strings": 2,
        }],
    )

    assert result.battery_backup_insight is insight
    assert insight["insight_status"] == "Network Summary / BDT Mismatch"
    assert insight["bdt"]["latest_validation_verdict"] == "Rejected"
    assert insight["bdt"]["failed_rule_count"] == 1


def test_build_battery_backup_insight_classifies_lead_acid_to_lithium_upgrade():
    insight = build_battery_backup_insight(
        site_row={"site_id": "0704UP", "site_name": "Upgrade Site"},
        network_rows=[{
            "site_id": "0704UP",
            "battery_type": "SBS",
            "backup_status": "Good",
            "backup_minutes": 180,
            "no_of_strings": 4,
            "recent_test_date_or_reporting_date": "2024-05-26",
        }],
        bdt_payload={
            "bdt_summary": {"rows": [{}], "returned": 1, "total": 1},
            "bdt_tests": {
                "rows": [{
                    "site_code": "0704UP",
                    "test_date": "2026-04-01",
                    "battery_brand": "Lithium-Huawei",
                    "battery_ah": 100,
                    "battery_voltage": 48,
                    "num_strings": 3,
                    "num_batteries": 3,
                    "discharge_minutes": 115,
                    "end_voltage": 43.7,
                }],
                "returned": 1,
                "total": 1,
            },
            "validation_runs": {"rows": [{"overall_verdict": "Rejected", "test_date": "2026-04-01"}], "returned": 1, "total": 1},
            "rule_results": {"rows": [], "returned": 0, "total": 0},
            "photos": {"rows": [{}], "returned": 1, "total": 1},
        },
        min_backup_minutes=90,
        backup_minutes_tolerance=30,
    )

    assert insight["insight_status"] == "Battery Technology Upgrade Detected"
    assert "battery_technology_upgrade" in insight["insight_flags"]
    assert "network_bdt_mismatch" not in insight["insight_flags"]
    assert {diff["field"] for diff in insight["differences"]} == {"battery_technology_upgrade", "backup_minutes"}
    assert insight["battery_topology"]["upgrade_detected"] is True
    assert insight["snapshot_freshness"]["status"] == "network_summary_older_than_bdt"
