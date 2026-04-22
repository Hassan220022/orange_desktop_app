"""
R1 (Photos) validation rule unit tests.

All branches of _rule_1_photos are tested against hand-constructed BDTData
objects so results are deterministic and don't depend on embedded images in
fixture files. Tests cover:
  - deferred mode with count > 0 → Accepted (count path)
  - deferred mode with count = 0 → Rejected (count path)
  - low mapping confidence → N/A
  - category-based path: both required categories present → Accepted
  - category-based path: missing batteries → Rejected
  - category-based path: missing rectifier → Rejected
  - no categories + slots present → count-based fallback
  - fallback path (no slot objects, only photo_count integer)
"""

import pytest

from alarm_app.bdt.parser import BDTData, PhotoSlot
from alarm_app.bdt.validator import _rule_1_photos


def _slot(category: str, filled: bool = True) -> PhotoSlot:
    return PhotoSlot(
        label=category,
        image_data=b"\xff\xd8\xff" if filled else None,
        image_ext="jpeg" if filled else "",
        category=category,
    )


def _bdt(**kwargs) -> BDTData:
    defaults = dict(
        filename="test.xlsx",
        photo_slots=[],
        photo_count=0,
        required_photo_count=6,
        photos_deferred=False,
    )
    defaults.update(kwargs)
    return BDTData(**defaults)


# ── Deferred mode (Branch 1: count-based fallback) ────────────────────────────

def test_r1_deferred_fallback_count():
    """Deferred mode with full count → Accepted via count path."""
    bdt = _bdt(
        photo_detection_mode="deferred",
        photo_count=16,
        required_photo_count=16,
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "Accepted"
    assert result.passed is True


def test_r1_deferred_zero_photos():
    """Deferred mode with zero photos → Rejected via count path."""
    bdt = _bdt(
        photo_detection_mode="deferred",
        photo_count=0,
        required_photo_count=16,
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "Rejected"
    assert result.passed is False


# ── Low mapping confidence (Branch 2) ─────────────────────────────────────────

def test_r1_na_when_low_confidence():
    """Low mapping confidence → N/A regardless of categories found."""
    bdt = _bdt(
        photo_mapping_confidence="low",
        photo_categories_found=["rectifier"],
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "N/A"
    assert result.passed is None
    assert "confidence" in result.detail.lower()


# ── Category-based path (Branch 3) ────────────────────────────────────────────

def test_r1_accepted_by_category():
    """Both required categories present → Accepted."""
    bdt = _bdt(
        photo_categories_found=["rectifier", "batteries"],
        photo_mapping_confidence="high",
        required_photo_categories=["rectifier", "batteries"],
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "Accepted"
    assert result.passed is True


def test_r1_rejected_missing_batteries():
    """Missing batteries category → Rejected, detail mentions batteries."""
    bdt = _bdt(
        photo_categories_found=["rectifier"],
        photo_mapping_confidence="high",
        required_photo_categories=["rectifier", "batteries"],
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "Rejected"
    assert result.passed is False
    assert "batteries" in result.detail


def test_r1_rejected_missing_rectifier():
    """Missing rectifier category → Rejected, detail mentions rectifier."""
    bdt = _bdt(
        photo_categories_found=["batteries"],
        photo_mapping_confidence="high",
        required_photo_categories=["rectifier", "batteries"],
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "Rejected"
    assert result.passed is False


def test_r1_rejects_ai_flagged_photo_slots():
    slot = _slot("rectifier")
    slot.verification = {"synthid": {"status": "detected", "confidence": 0.91}}
    bdt = _bdt(photo_slots=[slot], required_photo_count=1)

    result = _rule_1_photos(bdt)

    assert result.verdict == "Rejected"
    assert result.passed is False
    assert "SynthID" in result.detail
    assert "rectifier" in result.detail


def test_r1_accepted_extra_categories():
    """Extra categories beyond required still pass."""
    bdt = _bdt(
        photo_categories_found=["rectifier", "batteries", "modules"],
        photo_mapping_confidence="medium",
        required_photo_categories=["rectifier", "batteries"],
    )
    result = _rule_1_photos(bdt)
    assert result.verdict == "Accepted"
    assert result.passed is True


# ── Slot-based count fallback (Branch 4: slots present, no categories) ─────────

def test_all_slots_filled_categories_met_accepted():
    slots = [_slot("rectifier")] * 3 + [_slot("batteries")] * 3
    bdt = _bdt(photo_slots=slots, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Accepted"
    assert result.passed is True
    assert "6/6" in result.detail


def test_zero_filled_slots_rejected():
    slots = [_slot("rectifier", filled=False)] * 3 + [_slot("batteries", filled=False)] * 3
    bdt = _bdt(photo_slots=slots, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Rejected"
    assert result.passed is False
    assert "0/6" in result.detail


def test_partial_fill_revise_with_missing_count():
    slots = [_slot("rectifier")] * 2 + [_slot("batteries")] + [_slot("batteries", filled=False)] * 3
    bdt = _bdt(photo_slots=slots, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Revise"
    assert result.passed is False
    assert "3/6" in result.detail
    assert "missing 3" in result.detail


# ── Integer count fallback (Branch 5: no slots) ───────────────────────────────

def test_no_slots_zero_count_rejected():
    bdt = _bdt(photo_slots=[], photo_count=0, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Rejected"
    assert result.passed is False


def test_no_slots_count_meets_required_accepted():
    bdt = _bdt(photo_slots=[], photo_count=6, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Accepted"
    assert result.passed is True


def test_no_slots_count_below_required_revise():
    bdt = _bdt(photo_slots=[], photo_count=4, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Revise"
    assert result.passed is False
    assert "4/6" in result.detail
    assert "missing 2" in result.detail


# ── required_photo_count is layout-specific, not the global constant ───────────

def test_r1_uses_bdt_required_count_not_global():
    """R1 must read bdt.required_photo_count, never the module-level constant."""
    # 6-photo layout: 6 photos should pass (would fail if constant 16 were used)
    slots = [_slot("rectifier")] * 3 + [_slot("batteries")] * 3
    bdt = _bdt(photo_slots=slots, required_photo_count=6)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Accepted", (
        "R1 rejected a 6-photo file with 6 photos — likely still using the "
        "global BDT_REQUIRED_PHOTO_COUNT=16 instead of bdt.required_photo_count"
    )


def test_r1_uses_bdt_required_count_for_16_photo():
    # 16-photo layout: 15 photos should be Revise (missing 1)
    slots = [_slot("rectifier")] * 4 + [_slot("batteries")] * 4 + \
            [_slot("modules")] * 4 + [_slot("load")] * 3
    bdt = _bdt(photo_slots=slots, required_photo_count=16)
    result = _rule_1_photos(bdt)
    assert result.verdict == "Revise"
    assert "15/16" in result.detail
    assert "missing 1" in result.detail
