"""Human-calibrated BDT validation characterization tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from alarm_app.bdt.evidence_metrics import discharge_trend_metrics, worst_r3_evidence
from alarm_app.bdt.human_calibration import (
    find_bdt_file,
    parse_book1,
    run_calibration,
)
from alarm_app.bdt.parser import parse_bdt_file
from alarm_app.bdt.validator import BDTTolerances, validate_bdt

BOOK1 = Path("/Users/mikawi/Desktop/Book1.xlsx")
BDT_FOLDER = Path("/Volumes/nvme 500/Alarms/BDT_May2026")

GOLDEN_CASES = {
    "0161CA": {
        "human": "Rejected",
        "expect_r3": ("Rejected", "Revise"),
        "reason_contains": "imbalance",
    },
    "0307RE": {
        "human": "Rejected",
        "expect_r9": ("Rejected", "Revise"),
        "reason_contains": "slope",
    },
    "3907CA": {
        "human": "Rejected",
        "expect_r3": ("Rejected",),
    },
    "0218UP": {
        "human": "Rejected",
        "expect_overall": ("Rejected", "Revise"),
    },
    "3565CA": {
        "human": "Accepted",
        "expect_overall": ("Accepted", "Revise"),
        "expect_not_overall": ("Rejected",),
    },
    "4476UP": {
        "human": "Rejected",
        "expect_overall": ("Rejected", "Revise"),
    },
}


def _rule_verdict(result, rule_id: str) -> str:
    return next(r.verdict for r in result.rules if r.rule_id == rule_id)


@pytest.fixture(scope="module")
def calibration_rows():
    if not BOOK1.exists() or not BDT_FOLDER.exists():
        pytest.skip("Calibration fixtures not available on this machine")
    rows, _ = run_calibration(BOOK1, BDT_FOLDER)
    return rows


@pytest.fixture(scope="module")
def human_rows():
    if not BOOK1.exists():
        pytest.skip("Book1 not available")
    return parse_book1(BOOK1)


@pytest.mark.parametrize("site_code,spec", list(GOLDEN_CASES.items()))
def test_golden_site_alignment(site_code, spec):
    if not BDT_FOLDER.exists():
        pytest.skip("BDT_May2026 folder not available")

    bdt_path = find_bdt_file(BDT_FOLDER, site_code)
    assert bdt_path is not None, f"missing BDT for {site_code}"

    bdt = parse_bdt_file(str(bdt_path), skip_photos=True)
    result = validate_bdt(bdt, None, tolerances=BDTTolerances.defaults())

    if "expect_overall" in spec:
        assert result.overall in spec["expect_overall"]
    if "expect_not_overall" in spec:
        assert result.overall not in spec["expect_not_overall"]

    if "expect_r3" in spec:
        assert _rule_verdict(result, "R3") in spec["expect_r3"]

    if "expect_r9" in spec:
        assert _rule_verdict(result, "R9") in spec["expect_r9"]

    if spec.get("reason_contains") == "imbalance":
        r3 = _rule_verdict(result, "R3")
        detail = next(r.detail for r in result.rules if r.rule_id == "R3")
        assert r3 == "Rejected"
        assert "imbalance" in detail.lower()

    if spec.get("reason_contains") == "slope":
        r9 = _rule_verdict(result, "R9")
        detail = next(r.detail for r in result.rules if r.rule_id == "R9")
        assert r9 in ("Rejected", "Revise")
        assert "slope" in detail.lower()


def test_0161CA_string_imbalance_evidence():
    if not BDT_FOLDER.exists():
        pytest.skip("BDT_May2026 folder not available")
    bdt = parse_bdt_file(str(find_bdt_file(BDT_FOLDER, "0161CA")), skip_photos=True)
    evidence = worst_r3_evidence(bdt)
    assert evidence is not None
    assert evidence.worst_imbalance_ratio >= 0.85


def test_0161CA_component_check_still_rejects_imbalance():
    if not BDT_FOLDER.exists():
        pytest.skip("BDT_May2026 folder not available")
    bdt = parse_bdt_file(str(find_bdt_file(BDT_FOLDER, "0161CA")), skip_photos=True)
    result = validate_bdt(
        bdt,
        None,
        tolerances=BDTTolerances.defaults(),
        network_no_usable_backup=True,
        network_backup_reasons=["Network Summary backup status is ZERO BACKUP"],
    )
    assert _rule_verdict(result, "R3") == "Rejected"
    assert result.overall == "Rejected"


def test_0307RE_vs_3565CA_slope_separates_overlap():
    if not BDT_FOLDER.exists():
        pytest.skip("BDT_May2026 folder not available")
    re_bdt = parse_bdt_file(str(find_bdt_file(BDT_FOLDER, "0307RE")), skip_photos=True)
    ca_bdt = parse_bdt_file(str(find_bdt_file(BDT_FOLDER, "3565CA")), skip_photos=True)
    re_metrics = discharge_trend_metrics(re_bdt)
    ca_metrics = discharge_trend_metrics(ca_bdt)
    assert re_metrics is not None and ca_metrics is not None
    assert re_metrics.bus_amp_slope > ca_metrics.bus_amp_slope
    re_r3 = worst_r3_evidence(re_bdt)
    ca_r3 = worst_r3_evidence(ca_bdt)
    assert re_r3 is not None and ca_r3 is not None
    assert abs(re_r3.max_pos_delta - ca_r3.max_pos_delta) < 2.0


def test_human_rejected_never_auto_accepted(calibration_rows, human_rows):
    by_key = {(r.site_code.upper(), r.test_date): r for r in calibration_rows}
    false_accepts = []
    for human in human_rows:
        if human.human_verdict != "Rejected":
            continue
        key = (human.site_code.upper(), human.test_date)
        row = by_key.get(key)
        if row is None or not row.bdt_path:
            continue
        bdt = parse_bdt_file(row.bdt_path, skip_photos=True)
        result = validate_bdt(bdt, None, tolerances=BDTTolerances.defaults())
        if result.overall == "Accepted":
            false_accepts.append(human.site_code)
    assert false_accepts == []


def test_human_calibration_matrix_coverage(calibration_rows, human_rows):
    assert len(human_rows) == 82
    assert len(calibration_rows) == 82
    parsed = [r for r in calibration_rows if r.bdt_path and not r.parse_error]
    assert len(parsed) == 82


def test_r11_na_non_blocking_on_summary_only_failure():
    """R11 missing data alone must not block overall acceptance."""
    bdt = parse_bdt_file(str(find_bdt_file(BDT_FOLDER, "3565CA")), skip_photos=True)
    result = validate_bdt(bdt, None, tolerances=BDTTolerances.defaults())
    assert _rule_verdict(result, "R11") == "N/A"
    blocking = [
        r.rule_id for r in result.rules
        if r.verdict == "Rejected" and r.rule_id not in {"R1", "R10"}
    ]
    assert "R11" not in blocking


def test_human_calibration_agreement_targets(calibration_rows):
    """Regression guardrails from the May 2026 human batch."""
    reject_auto_accept = []
    accepted_auto_reject = []
    aligned = 0
    for row in calibration_rows:
        if not row.bdt_path:
            continue
        bdt = parse_bdt_file(row.bdt_path, skip_photos=True)
        result = validate_bdt(bdt, None, tolerances=BDTTolerances.defaults())
        if row.human_verdict == "Rejected" and result.overall == "Accepted":
            reject_auto_accept.append(row.site_code)
        if row.human_verdict == "Accepted" and result.overall == "Rejected":
            accepted_auto_reject.append(row.site_code)
        if row.human_verdict == "Accepted" and result.overall in ("Accepted", "Revise"):
            aligned += 1
        if row.human_verdict == "Rejected" and result.overall in ("Rejected", "Revise"):
            aligned += 1
    assert reject_auto_accept == []
    assert len(accepted_auto_reject) < 15
    assert aligned / len(calibration_rows) >= 0.70
