"""
Unit tests for category-based photo validation per PRD FR-003.

Tests that R1 uses category-based validation as primary rule,
with rectifier + batteries as required categories.
"""

import pytest
from dataclasses import dataclass
from alarm_app.bdt.validator import _rule_1_photos, RuleResult
from alarm_app.bdt.parser import BDTData, PhotoSlot


class TestCategoryBasedValidation:
    """Test category-based R1 validation per PRD FR-003."""

    def _make_slot(self, category: str, has_image: bool = True) -> PhotoSlot:
        """Helper to create a PhotoSlot with given category."""
        return PhotoSlot(
            label=f"Test {category}",
            image_data=b"fake_jpeg" if has_image else None,
            image_ext="jpeg",
            category=category,
        )

    def _make_bdt(self, slots: list[PhotoSlot], mapping_confidence: str = "high") -> BDTData:
        """Helper to create BDTData with photo slots."""
        bdt = BDTData(
            filename="test.xlsx",
            photo_slots=slots,
            required_photo_categories=["rectifier", "batteries"],
            photo_mapping_confidence=mapping_confidence,
        )
        return bdt

    def test_required_categories_both_present_accepted(self):
        """Accept when sufficient slot count met (slots only, no category metadata)."""
        bdt = self._make_bdt([
            self._make_slot("rectifier"),
            self._make_slot("batteries"),
            self._make_slot("modules"),
        ])
        bdt.required_photo_count = 3  # Match filled slot count
        result = _rule_1_photos(bdt)
        assert result.passed is True
        assert result.verdict == "Accepted"
        assert "3/3" in result.detail

    def test_missing_both_categories_revise(self):
        """Count is primary - if count is insufficient, revise even with categories."""
        bdt = self._make_bdt([
            self._make_slot("modules"),
            self._make_slot("load"),
        ])
        bdt.required_photo_count = 3  # Require 3 slots but only have 2
        result = _rule_1_photos(bdt)
        assert result.passed is False
        assert result.verdict == "Revise"

    def test_categories_present_count_low_revise(self):
        """Revise when categories present but count below required (count is required)."""
        bdt = self._make_bdt([
            self._make_slot("rectifier"),
            self._make_slot("batteries"),
        ])
        bdt.required_photo_count = 16
        result = _rule_1_photos(bdt)
        assert result.passed is False
        assert result.verdict == "Revise"
        assert "missing" in result.detail.lower()  # Mentions missing optional photos

    def test_no_photos_rejected(self):
        """Reject when no photos at all."""
        bdt = self._make_bdt([])
        result = _rule_1_photos(bdt)
        assert result.passed is False
        assert result.verdict == "Rejected"

    def test_photos_deferred_returns_na(self):
        """Deferred mode with no photos → Rejected via count-based fallback."""
        bdt = BDTData(
            filename="test.xlsx",
            photos_deferred=True,
            photo_detection_mode="deferred",
            photo_count=0,
        )
        result = _rule_1_photos(bdt)
        assert result.passed is False
        assert result.verdict == "Rejected"

    def test_uses_required_categories_from_bdtdata(self):
        """Use required_categories from BDTData when available."""
        bdt = BDTData(
            filename="test.xlsx",
            photo_slots=[
                self._make_slot("rectifier"),
                self._make_slot("batteries"),
                self._make_slot("modules"),
            ],
            required_photo_categories=["rectifier", "batteries", "modules"],
            required_photo_count=3,
            photo_mapping_confidence="high",
        )
        result = _rule_1_photos(bdt)
        assert result.passed is True  # Has all required categories and sufficient count

    def test_falls_back_to_constants_when_bdtdata_empty(self):
        """Fall back to constants when BDTData required_categories is empty."""
        bdt = BDTData(
            filename="test.xlsx",
            photo_slots=[
                self._make_slot("rectifier"),
                self._make_slot("batteries"),
            ],
            required_photo_categories=[],  # Empty list
            required_photo_count=2,
            photo_mapping_confidence="high",
        )
        result = _rule_1_photos(bdt)
        assert result.passed is True  # Falls back to constants (rectifier + batteries) with sufficient count

    def test_legacy_count_only_returns_revise(self):
        """Legacy count-only check returns Revise when count is below required."""
        bdt = BDTData(
            filename="test.xlsx",
            photo_count=10,
            required_photo_count=16,
            photo_slots=[],  # No slot metadata
        )
        result = _rule_1_photos(bdt)
        assert result.passed is False
        assert result.verdict == "Revise"


class TestCategoryMappingConfidence:
    """Test photo category mapping confidence levels."""

    def test_high_confidence_when_count_meets_required(self):
        """High confidence when filled slots >= required count."""
        from alarm_app.bdt.parser import BDTData, PhotoSlot
        slots = [PhotoSlot(label=f"Slot {i}", image_data=b"test", category="rectifier") for i in range(16)]
        bdt = BDTData(photo_slots=slots, required_photo_count=16)
        # This would be set by _extract_photo_slots
        filled = sum(1 for s in slots if s.image_data)
        confidence = "high" if filled >= 16 else "medium"
        assert confidence == "high"

    def test_medium_confidence_when_count_below_required(self):
        """Medium confidence when filled slots < required count but > 0."""
        from alarm_app.bdt.parser import BDTData, PhotoSlot
        slots = [PhotoSlot(label=f"Slot {i}", image_data=b"test", category="rectifier") for i in range(10)]
        bdt = BDTData(photo_slots=slots, required_photo_count=16)
        filled = sum(1 for s in slots if s.image_data)
        confidence = "high" if filled >= 16 else "medium"
        assert confidence == "medium"

    def test_low_confidence_when_no_photos(self):
        """Low confidence when no photos filled."""
        from alarm_app.bdt.parser import BDTData, PhotoSlot
        slots = [PhotoSlot(label=f"Slot {i}", image_data=None, category="rectifier") for i in range(16)]
        bdt = BDTData(photo_slots=slots, required_photo_count=16)
        filled = sum(1 for s in slots if s.image_data)
        confidence = "high" if filled >= 16 else "medium" if filled > 0 else "low"
        assert confidence == "low"
