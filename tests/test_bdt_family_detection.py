"""
Unit tests for BDT layout family detection per PRD FR-001, FR-002.

Tests deterministic family detection (A, B1, B2, C, SUMMARY_EXCLUDED, UNKNOWN)
and coordinate strategy by family.
"""

import pytest
from alarm_app.bdt.parser import _detect_layout_family


class TestLayoutFamilyDetection:
    """Test deterministic family detection per PRD FR-001."""

    def _mock_cell_fn(self, values: dict[tuple[int, int], str]) -> callable:
        """Create a mock cell function that returns predefined values."""
        def cell(row: int, col: int):
            return values.get((row, col), "")
        return cell

    def test_family_a_site_code_at_l4(self):
        """Layout A detected when site code token at L4."""
        cell_fn = self._mock_cell_fn({
            (4, 12): "0483DE",  # Valid site code token
        })
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=20, sheet_name="BDT", all_sheet_names=["BDT"]
        )
        assert family == "A"
        assert confidence == "high"
        assert "site_code_at_l4" in reasons

    def test_family_a_valid_date_at_t3(self):
        """Layout A detected when valid date at T3."""
        cell_fn = self._mock_cell_fn({
            (3, 20): "2024-01-28",  # Valid date
        })
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=20, sheet_name="BDT", all_sheet_names=["BDT"]
        )
        assert family == "A"
        assert confidence == "high"
        assert "valid_date_at_t3" in reasons

    def test_family_a_rectifier_brand_at_l13(self):
        """Layout A detected when rectifier brand at L13."""
        cell_fn = self._mock_cell_fn({
            (13, 12): "Huawei",
        })
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="BDT", all_sheet_names=["BDT"]
        )
        assert family == "A"
        assert confidence == "medium"
        assert "rectifier_brand_at_l13" in reasons

    def test_family_b1_rectifier_1_singleton(self):
        """Layout B1 detected for Rectifier 1 singleton sheet."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="Rectifier 1", all_sheet_names=["Rectifier 1"]
        )
        assert family == "B1"
        assert confidence == "high"
        assert "sheet_name_rectifier_1" in reasons

    def test_family_b2_rec1_variant(self):
        """Layout B2 detected for Rec1 sheet (uses Layout A coordinates)."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="Rec1", all_sheet_names=["Rec1"]
        )
        assert family == "B2"
        assert confidence == "high"
        assert "sheet_name_Rec1" in reasons
        assert "layout_b2_family" in reasons

    def test_family_b2_rec2_variant(self):
        """Layout B2 detected for Rec2 sheet."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="Rec2", all_sheet_names=["Rec2"]
        )
        assert family == "B2"
        assert confidence == "high"
        assert "sheet_name_Rec2" in reasons

    def test_family_b2_rec_space_variant(self):
        """Layout B2 detected for 'Rec 1' variant."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="Rec 1", all_sheet_names=["Rec 1"]
        )
        assert family == "B2"
        assert confidence == "high"

    def test_family_c_multi_sheet_test_pms(self):
        """Layout C detected for test_pms multi-sheet format."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="BDT sheet",
            all_sheet_names=["BDT sheet", "Power Alarm", "Config", "Summary "]
        )
        assert family == "C"
        assert confidence == "high"
        assert "multi_sheet_test_pms" in reasons
        assert "sheet_name_bdt_sheet" in reasons

    def test_family_c_bdt_sheet_fallback(self):
        """Layout C detected for single 'BDT sheet' without other sheets."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="BDT sheet",
            all_sheet_names=["BDT sheet"]
        )
        assert family == "C"
        assert confidence == "medium"
        assert "sheet_name_bdt_sheet_fallback" in reasons

    def test_summary_excluded_workbook(self):
        """SUMMARY_EXCLUDED for summary-only workbooks without BDT sheet."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="Summary",
            all_sheet_names=["Summary", "Config"]
        )
        assert family == "SUMMARY_EXCLUDED"
        assert confidence == "high"
        assert "summary_only_workbook" in reasons

    def test_unknown_low_confidence(self):
        """UNKNOWN family with low confidence when no Layout A signals."""
        cell_fn = self._mock_cell_fn({})
        family, confidence, reasons = _detect_layout_family(
            cell_fn, max_row=100, max_col=15, sheet_name="BDT", all_sheet_names=["BDT"]
        )
        assert family == "UNKNOWN"
        assert confidence == "low"
        assert "no_layout_a_signals" in reasons

    def test_coordinate_strategy_a_uses_layout_a_coords(self):
        """Family A and B2 use Layout A coordinate baseline."""
        cell_fn = self._mock_cell_fn({(4, 12): "0483DE"})
        from alarm_app.bdt.parser import _detect_layout, _LAYOUT_A
        layout = _detect_layout(
            cell_fn, max_row=100, max_col=20, sheet_name="BDT"
        )
        assert layout is _LAYOUT_A

    def test_coordinate_strategy_b1_uses_layout_b_coords(self):
        """Family B1 uses Layout B coordinate baseline."""
        cell_fn = self._mock_cell_fn({})
        from alarm_app.bdt.parser import _detect_layout, _LAYOUT_B
        layout = _detect_layout(
            cell_fn, max_row=100, max_col=15, sheet_name="Rectifier 1"
        )
        assert layout is _LAYOUT_B

    def test_coordinate_strategy_c_uses_layout_b_with_fallback(self):
        """Family C uses Layout B coordinates (will rely on fallback scanning)."""
        cell_fn = self._mock_cell_fn({})
        from alarm_app.bdt.parser import _detect_layout, _LAYOUT_B
        layout = _detect_layout(
            cell_fn, max_row=100, max_col=15, sheet_name="BDT sheet"
        )
        assert layout is _LAYOUT_B


class TestDetectionMetadataFields:
    """Test that BDTData gets populated with detection metadata."""

    def test_bdtdata_has_family_fields(self):
        """BDTData has new family detection metadata fields."""
        from alarm_app.bdt.parser import BDTData
        data = BDTData()
        assert hasattr(data, "core_layout_family")
        assert hasattr(data, "detection_confidence")
        assert hasattr(data, "detection_reasons")
        assert hasattr(data, "photo_categories_found")
        assert hasattr(data, "photo_mapping_confidence")
        assert hasattr(data, "photo_detection_mode")
        assert hasattr(data, "required_photo_categories")

    def test_photo_metadata_fields_initialized(self):
        """Photo metadata fields are properly initialized."""
        from alarm_app.bdt.parser import BDTData
        data = BDTData()
        assert data.core_layout_family == ""
        assert data.detection_confidence == ""
        assert data.detection_reasons == []
        assert data.photo_categories_found == []
        assert data.photo_mapping_confidence == ""
        assert data.photo_detection_mode == ""
        assert data.required_photo_categories == []
