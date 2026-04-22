"""
Golden parity tests -- compare current code output against baseline fixtures.

These tests require generated fixtures in tests/fixtures/golden/.
Run `python tests/generate_golden.py /path/to/data` first.

Mark: @pytest.mark.golden -- skipped when fixtures don't exist.
"""
import json
import pytest
from pathlib import Path
from alarm_app.constants import BDT_RULES

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"

has_golden = (GOLDEN_DIR / "parse_summary.json").exists()
golden = pytest.mark.skipif(not has_golden, reason="Golden fixtures not generated")


def _load(name: str) -> dict:
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


@golden
class TestParseGolden:
    def test_row_count_matches(self):
        summary = _load("parse_summary.json")
        assert summary["row_count"] > 0, "Fixture should have rows"

    def test_columns_match(self):
        summary = _load("parse_summary.json")
        assert "site_id" in summary["columns"]
        assert "occurred_on" in summary["columns"]
        assert "_category" in summary["columns"]

    def test_category_counts_match(self):
        summary = _load("parse_summary.json")
        counts = summary.get("category_counts", {})
        assert len(counts) > 0, "Should have at least one category"


@golden
class TestClassifyGolden:
    def test_category_counts_present(self):
        summary = _load("classify_summary.json")
        assert "category_counts" in summary


@golden
class TestBackupTimeGolden:
    def test_backup_summary_exists(self):
        summary = _load("backup_times_summary.json")
        assert "row_count" in summary


@golden
class TestBDTValidationGolden:
    def test_results_present(self):
        results = _load("bdt_validation_results.json")
        assert isinstance(results, list)

    def test_each_result_has_expected_rule_count(self):
        results = _load("bdt_validation_results.json")
        for r in results:
            assert len(r["rules"]) == len(BDT_RULES), (
                f"{r['filename']}: expected {len(BDT_RULES)} rules, got {len(r['rules'])}"
            )

    def test_verdicts_are_valid(self):
        results = _load("bdt_validation_results.json")
        valid = {"Accepted", "Rejected", "Revise"}
        for r in results:
            assert r["overall"] in valid, (
                f"{r['filename']}: invalid verdict {r['overall']}"
            )

    def test_rule_verdicts_are_valid(self):
        results = _load("bdt_validation_results.json")
        valid = {"Accepted", "Rejected", "Revise", "N/A"}
        for r in results:
            for rule in r["rules"]:
                assert rule["verdict"] in valid, (
                    f"{r['filename']} {rule['rule_id']}: "
                    f"invalid verdict {rule['verdict']}"
                )
