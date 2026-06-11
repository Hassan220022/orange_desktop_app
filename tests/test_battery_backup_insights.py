from types import SimpleNamespace

from alarm_app.bdt.validator import RuleResult, ValidationResult
from alarm_app.core.battery_backup_insights import (
    COMPONENT_CHECK_INSIGHT_STATUS,
    attach_battery_backup_insight,
    build_battery_backup_insight,
    insight_blocking_rule_failures,
    resolve_network_battery_context,
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


def test_resolve_network_battery_context_detects_strong_no_backup_triggers():
    cases = [
        ({"backup_status": "ZERO BACKUP"}, "ZERO BACKUP"),
        ({"batt_reason": "Battery stolen"}, "STOLEN"),
        ({"backup_status": "removed battery"}, "REMOVED"),
        ({"no_of_strings": 0}, "No of Strings"),
        ({"backup_minutes": 9.9}, "below"),
    ]

    for row, expected_reason in cases:
        context = resolve_network_battery_context([row], min_backup_minutes=10.0)

        assert context.has_network_summary is True
        assert context.no_usable_backup is True
        assert any(expected_reason.lower() in reason.lower() for reason in context.reasons)


def test_resolve_network_battery_context_treats_missing_battery_type_as_unknown():
    context = resolve_network_battery_context(
        [{"battery_type": "", "installed_battery_type": "", "backup_minutes": 10.0, "no_of_strings": 1}],
        min_backup_minutes=10.0,
    )

    assert context.has_network_summary is True
    assert context.no_usable_backup is False
    assert context.reasons == []


def test_resolve_network_battery_context_backup_threshold_boundary():
    below = resolve_network_battery_context([{"backup_minutes": 9.99}], min_backup_minutes=10.0)
    at_threshold = resolve_network_battery_context([{"backup_minutes": 10.0}], min_backup_minutes=10.0)
    above = resolve_network_battery_context([{"backup_minutes": 10.01}], min_backup_minutes=10.0)

    assert below.no_usable_backup is True
    assert at_threshold.no_usable_backup is False
    assert above.no_usable_backup is False


def test_build_battery_backup_insight_keeps_weak_positive_backup_declared():
    insight = build_battery_backup_insight(
        site_row={"site_id": "0167DE", "site_name": "Critical Site"},
        network_rows=[{
            "site_id": "0167DE",
            "battery_type": "Narada",
            "backup_status": "Good",
            "backup_minutes": 60,
            "no_of_strings": 2,
            "vip": "VIP",
        }],
        bdt_payload={
            "bdt_summary": {"rows": [{}], "returned": 1, "total": 1},
            "bdt_tests": {"rows": [{"battery_brand": "Narada", "discharge_minutes": 60}], "returned": 1, "total": 1},
            "validation_runs": {"rows": [{"overall_verdict": "Accepted"}], "returned": 1, "total": 1},
            "rule_results": {"rows": [], "returned": 0, "total": 0},
            "photos": {"rows": [{}], "returned": 1, "total": 1},
        },
        min_backup_minutes=90,
    )

    assert insight["network_summary"]["battery_declared"] is True
    assert insight["insight_status"] == "Critical Site With Weak Backup"
    assert "weak_measured_backup" in insight["insight_flags"]
    assert "no_usable_battery_declared" not in insight["insight_flags"]


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


def test_insight_blocking_rule_failures_ignore_non_blocking_rules():
    rules = [
        {"rule_id": "R1", "verdict": "Rejected"},
        {"rule_id": "R10", "verdict": "Rejected"},
        {"rule_id": "R11", "verdict": "No data"},
        {"rule_id": "R8", "verdict": "Revise"},
    ]
    failures = insight_blocking_rule_failures(rules)
    assert [rule["rule_id"] for rule in failures] == ["R8"]


def test_insight_blocking_rule_failures_honor_custom_verdict_policy():
    from alarm_app.bdt.validator import BDTVerdictPolicy

    rules = [
        {"rule_id": "R3", "verdict": "Rejected"},
        {"rule_id": "R10", "verdict": "Rejected"},
    ]
    policy = BDTVerdictPolicy.from_dict({"block_overall_r3": 0.0, "block_overall_r10": 1.0})
    failures = insight_blocking_rule_failures(rules, verdict_policy=policy)
    assert [rule["rule_id"] for rule in failures] == ["R10"]


def test_component_check_accepted_uses_component_check_insight_status():
    insight = build_battery_backup_insight(
        site_row={"site_id": "4962UP"},
        network_rows=[{
            "site_id": "4962UP",
            "backup_status": "ZERO BACKUP",
            "backup_minutes": 0,
            "no_of_strings": 0,
        }],
        bdt_payload={
            "validation_context": {
                "validation_mode": "component_check_no_backup_battery",
                "network_no_usable_backup": True,
            },
            "bdt_summary": {"rows": [{}], "returned": 1, "total": 1},
            "bdt_tests": {
                "rows": [{
                    "battery_brand": "SBS",
                    "discharge_minutes": 0,
                    "num_strings": 0,
                }],
                "returned": 1,
                "total": 1,
            },
            "validation_runs": {"rows": [{"overall_verdict": "Accepted"}], "returned": 1, "total": 1},
            "rule_results": {
                "rows": [
                    {"rule_id": "R1", "verdict": "Rejected"},
                    {"rule_id": "R10", "verdict": "Rejected"},
                    {"rule_id": "R11", "verdict": "No data"},
                ],
                "returned": 3,
                "total": 3,
            },
            "photos": {"rows": [], "returned": 0, "total": 0},
        },
    )

    assert insight["insight_status"] == COMPONENT_CHECK_INSIGHT_STATUS
    assert "failed_bdt_rules" not in insight["insight_flags"]
    assert "weak_measured_backup" not in insight["insight_flags"]


def test_accepted_with_only_non_blocking_rule_failures_is_bdt_passed():
    insight = build_battery_backup_insight(
        site_row={"site_id": "3750CA"},
        network_rows=[{
            "site_id": "3750CA",
            "battery_type": "Narada",
            "backup_status": "Good",
            "backup_minutes": 120,
            "no_of_strings": 2,
        }],
        bdt_payload={
            "bdt_summary": {"rows": [{}], "returned": 1, "total": 1},
            "bdt_tests": {
                "rows": [{"battery_brand": "Narada", "discharge_minutes": 120, "num_strings": 2}],
                "returned": 1,
                "total": 1,
            },
            "validation_runs": {"rows": [{"overall_verdict": "Accepted"}], "returned": 1, "total": 1},
            "rule_results": {
                "rows": [
                    {"rule_id": "R10", "verdict": "Rejected"},
                    {"rule_id": "R11", "verdict": "No data"},
                ],
                "returned": 2,
                "total": 2,
            },
            "photos": {"rows": [{}], "returned": 1, "total": 1},
        },
        min_backup_minutes=90,
    )

    assert insight["insight_status"] == "Battery Exists - BDT Passed"
    assert insight["severity"] == "low"
    assert "failed_bdt_rules" not in insight["insight_flags"]
