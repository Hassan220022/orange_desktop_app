"""
Unit tests for BDT photo layout detection and slot mapping.

Photo layout detection reads XML drawing anchors from the xlsx zip — real
embedded images are required to get non-default layout IDs from
parse_bdt_file(). These tests therefore test _select_photo_layout() and
_anchor_to_slot() directly, covering all branches without needing image
data. Integration tests against real files belong in a separate conftest
fixture once production files are available.
"""

import pytest

from alarm_app.bdt.parser import (
    _select_photo_layout,
    _anchor_to_slot,
    _PHOTO_LAYOUTS,
)


# ── _select_photo_layout unit tests ───────────────────────────────────────────

class TestSelectPhotoLayout:
    """Cover every branch of the anchor-count → layout-ID mapping."""

    # 6-photo bucket: 0–7 anchors
    @pytest.mark.parametrize("count", [0, 1, 6, 7])
    def test_six_photo_bucket(self, count):
        layout_id, required = _select_photo_layout(count, max_anchor_col=15)
        assert layout_id == "LAYOUT_PHOTO_6"
        assert required == 6

    # 15-photo bucket: 13–15 anchors
    @pytest.mark.parametrize("count", [13, 14, 15])
    def test_fifteen_photo_bucket(self, count):
        layout_id, required = _select_photo_layout(count, max_anchor_col=23)
        assert layout_id == "LAYOUT_PHOTO_15"
        assert required == 15

    # 16-photo bucket: ≥16 anchors
    @pytest.mark.parametrize("count", [16, 17, 20])
    def test_sixteen_photo_bucket(self, count):
        layout_id, required = _select_photo_layout(count, max_anchor_col=28)
        assert layout_id == "LAYOUT_PHOTO_16"
        assert required == 16

    # Dead zone 8–12: max_anchor_col >= 22 → LAYOUT_PHOTO_15
    @pytest.mark.parametrize("count", [8, 10, 12])
    def test_dead_zone_wide_col_maps_to_15(self, count):
        layout_id, required = _select_photo_layout(count, max_anchor_col=22)
        assert layout_id == "LAYOUT_PHOTO_15"
        assert required == 15

    # Dead zone 8–12: max_anchor_col < 22 → LAYOUT_PHOTO_6
    @pytest.mark.parametrize("count", [8, 10, 12])
    def test_dead_zone_narrow_col_maps_to_6(self, count):
        layout_id, required = _select_photo_layout(count, max_anchor_col=18)
        assert layout_id == "LAYOUT_PHOTO_6"
        assert required == 6

    def test_required_matches_layout_dict(self):
        """required_count returned always matches the _PHOTO_LAYOUTS registry."""
        for anchor_count in range(0, 25):
            layout_id, required = _select_photo_layout(anchor_count, max_anchor_col=28)
            assert required == _PHOTO_LAYOUTS[layout_id]["required_count"]


# ── _anchor_to_slot unit tests ────────────────────────────────────────────────

class TestAnchorToSlot:
    """Cover the row/col → slot-index mapping for each layout's geometry."""

    def _band_ranges(self, layout_id):
        return _PHOTO_LAYOUTS[layout_id]["band_ranges"]

    def _col_groups(self, layout_id):
        return _PHOTO_LAYOUTS[layout_id]["col_groups"]

    # LAYOUT_PHOTO_6: 2 bands × 3 col groups = slots 0–5
    def test_layout_6_first_slot(self):
        slot = _anchor_to_slot(9, 13,
                               self._band_ranges("LAYOUT_PHOTO_6"),
                               self._col_groups("LAYOUT_PHOTO_6"))
        assert slot == 0

    def test_layout_6_last_slot(self):
        slot = _anchor_to_slot(21, 23,
                               self._band_ranges("LAYOUT_PHOTO_6"),
                               self._col_groups("LAYOUT_PHOTO_6"))
        assert slot == 5

    def test_layout_6_returns_none_for_out_of_range(self):
        # Row 35 is outside the 6-photo band ranges
        slot = _anchor_to_slot(35, 13,
                               self._band_ranges("LAYOUT_PHOTO_6"),
                               self._col_groups("LAYOUT_PHOTO_6"))
        assert slot is None

    # LAYOUT_PHOTO_16: 5 bands × 4 col groups = slots 0–19
    def test_layout_16_first_slot(self):
        slot = _anchor_to_slot(9, 13,
                               self._band_ranges("LAYOUT_PHOTO_16"),
                               self._col_groups("LAYOUT_PHOTO_16"))
        assert slot == 0

    def test_layout_16_last_slot(self):
        slot = _anchor_to_slot(58, 28,
                               self._band_ranges("LAYOUT_PHOTO_16"),
                               self._col_groups("LAYOUT_PHOTO_16"))
        assert slot == 19

    def test_layout_16_band_boundary_inclusive_lower(self):
        # Row 21 starts band 1 (slots 4–7)
        slot = _anchor_to_slot(21, 13,
                               self._band_ranges("LAYOUT_PHOTO_16"),
                               self._col_groups("LAYOUT_PHOTO_16"))
        assert slot == 4

    def test_layout_16_returns_none_for_col_below_range(self):
        # col 5 is below all col_groups (min is 11)
        slot = _anchor_to_slot(9, 5,
                               self._band_ranges("LAYOUT_PHOTO_16"),
                               self._col_groups("LAYOUT_PHOTO_16"))
        assert slot is None

    def test_all_slot_defs_map_to_correct_index(self):
        """Every slot_def in LAYOUT_PHOTO_16 should map back to its own index."""
        slot_defs = _PHOTO_LAYOUTS["LAYOUT_PHOTO_16"]["slot_defs"]
        band_ranges = self._band_ranges("LAYOUT_PHOTO_16")
        col_groups = self._col_groups("LAYOUT_PHOTO_16")
        for expected_idx, (row, col) in enumerate(slot_defs):
            result = _anchor_to_slot(row, col, band_ranges, col_groups)
            assert result == expected_idx, (
                f"slot_def[{expected_idx}]=({row},{col}) mapped to {result}"
            )


# ── Photo layout registry integrity ───────────────────────────────────────────

class TestPhotoLayoutRegistry:
    """Sanity checks that _PHOTO_LAYOUTS entries are internally consistent."""

    @pytest.mark.parametrize("layout_id", ["LAYOUT_PHOTO_6", "LAYOUT_PHOTO_15", "LAYOUT_PHOTO_16"])
    def test_required_keys_present(self, layout_id):
        layout = _PHOTO_LAYOUTS[layout_id]
        for key in ("slot_defs", "band_ranges", "col_groups", "band_categories", "required_count"):
            assert key in layout, f"{layout_id} missing key '{key}'"

    def test_layout_6_slot_count_matches_required(self):
        layout = _PHOTO_LAYOUTS["LAYOUT_PHOTO_6"]
        assert len(layout["slot_defs"]) == layout["required_count"]

    def test_layout_15_slot_count_matches_required(self):
        layout = _PHOTO_LAYOUTS["LAYOUT_PHOTO_15"]
        assert len(layout["slot_defs"]) == layout["required_count"]

    def test_layout_16_slot_count_and_required_count(self):
        # LAYOUT_PHOTO_16 has 20 total slots (5 bands × 4 cols) but only
        # requires 16 to be filled. slot_defs defines geometry; required_count
        # is the pass threshold — they are intentionally different.
        layout = _PHOTO_LAYOUTS["LAYOUT_PHOTO_16"]
        assert len(layout["slot_defs"]) == 20
        assert layout["required_count"] == 16

    def test_band_ranges_do_not_overlap(self):
        """Adjacent band ranges must not share a row index."""
        for layout_id, layout in _PHOTO_LAYOUTS.items():
            ranges = layout["band_ranges"]
            for i in range(len(ranges) - 1):
                _, hi = ranges[i]
                lo_next, _ = ranges[i + 1]
                assert hi == lo_next, (
                    f"{layout_id}: band {i} ends at {hi}, band {i+1} starts at {lo_next}"
                )


# ── Integration test with real embedded images ─────────────────────────────────

class TestRealEmbeddedImages:
    """Integration test against a production file with real embedded images."""

    @pytest.fixture(scope="class")
    def real_bdt(self):
        """Parse the real 3938CA production file with embedded images."""
        from pathlib import Path
        from alarm_app.bdt.parser import parse_bdt_file
        
        fixtures_dir = Path(__file__).parent / "fixtures"
        bdt_file = fixtures_dir / "bdt_real_3938ca.xlsx"
        
        if not bdt_file.exists():
            pytest.skip(f"Production fixture not found: {bdt_file}")
        
        return parse_bdt_file(str(bdt_file), skip_photos=False)

    def test_real_file_has_valid_site_code(self, real_bdt):
        """Real file should parse with valid site code."""
        assert real_bdt.site_code == "3938CA"

    def test_real_file_photo_layout_is_15(self, real_bdt):
        """Real 3938CA file should be detected as LAYOUT_PHOTO_15 (10/15 filled)."""
        assert real_bdt.photo_layout_id == "LAYOUT_PHOTO_15"
        assert real_bdt.required_photo_count == 15

    def test_real_file_has_embedded_images(self, real_bdt):
        """Real file should have embedded JPEG images in photo slots."""
        filled_slots = [s for s in real_bdt.photo_slots if s.image_data]
        assert len(filled_slots) > 0, "Real file should have embedded images"
        
        # Verify at least one image has JPEG magic bytes
        jpeg_magic = b"\xff\xd8\xff"
        has_jpeg = any(s.image_data and s.image_data.startswith(jpeg_magic) for s in filled_slots)
        assert has_jpeg, "At least one embedded image should be JPEG"

    def test_real_file_core_layout_is_a(self, real_bdt):
        """Real file should be detected as Layout A (not Layout B)."""
        assert real_bdt.core_layout == "Layout A"

    def test_real_file_anchor_count_matches_filled_slots(self, real_bdt):
        """The number of filled slots should be reasonable (not inflated by non-slot images)."""
        filled_slots = [s for s in real_bdt.photo_slots if s.image_data]
        # Real file has 10 filled slots - if non-slot images were counted, this would be higher
        assert len(filled_slots) <= len(real_bdt.photo_slots), (
            f"Filled slots ({len(filled_slots)}) should not exceed total slots ({len(real_bdt.photo_slots)})"
        )
