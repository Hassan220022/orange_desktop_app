from xml.etree import ElementTree as ET

from alarm_app.bdt.image_assigner import (
    assign_anchors_to_sections,
    assign_manifest_images,
    group_adjacent_anchors,
)
from alarm_app.bdt.models import Section, WorkbookParseManifest
from alarm_app.bdt.normalization import normalize_header_text, resolve_section_category
from alarm_app.bdt.ooxml_reader import OOXMLPackage
from alarm_app.bdt.section_parser import build_workbook_manifest, detect_candidate_headers


class _FakePackage(OOXMLPackage):
    def __init__(self, xml_map):
        super().__init__("dummy.xlsx")
        self._xml_map = xml_map

    def _read_xml(self, path: str):
        if path not in self._xml_map:
            raise KeyError(path)
        return ET.fromstring(self._xml_map[path])


def test_normalization_and_category_resolution():
    assert normalize_header_text(" Rectifier / Module-Status ") == "rectifier module status"
    category = resolve_section_category("Rectifier info", ["module count", "dc output"])
    assert category == "rectifier"


def test_detect_headers_and_build_manifest():
    cell_map = {
        (2, 2): "Rectifier Section",
        (2, 10): "Battery Section",
        (3, 2): "Rectifier brand",
        (3, 10): "Battery voltage",
    }
    merged = [(2, 2, 2, 5), (2, 10, 2, 13)]
    style_ids = {(2, 2): 1, (2, 10): 1}

    headers = detect_candidate_headers(cell_map, merged, style_ids)
    assert len(headers) >= 2

    manifest = build_workbook_manifest(
        sheet_name="BDT sheet",
        cell_map=cell_map,
        merged_ranges=merged,
        style_ids=style_ids,
        family_guess="B",
        family_confidence="medium",
    )

    assert manifest.sheet_name == "BDT sheet"
    assert manifest.family_guess == "B"
    assert manifest.sections
    assert manifest.structural_signature


def test_assigner_assigns_and_groups_images():
    sections = [
        Section(
            section_id="sec_1",
            sheet_name="BDT sheet",
            top_row=1,
            left_col=1,
            bottom_row=20,
            right_col=10,
        )
    ]

    anchors = [
        {"from_row": 5, "from_col": 3, "to_row": 8, "to_col": 6, "r_id": "rId1"},
        {"from_row": 9, "from_col": 3, "to_row": 12, "to_col": 6, "r_id": "rId2"},
        {"from_row": 30, "from_col": 20, "to_row": 31, "to_col": 21, "r_id": "rId3"},
    ]

    assigned, orphans = assign_anchors_to_sections(sections, anchors, sheet_name="BDT sheet")
    assert len(assigned) == 2
    assert len(orphans) == 1

    groups = group_adjacent_anchors(assigned)
    assert groups
    assert all(img.group_id for group in groups for img in group)

    manifest = WorkbookParseManifest(sheet_name="BDT sheet", sections=sections)
    updated = assign_manifest_images(manifest, anchors)
    assert len(updated.orphan_images) == 1


def test_ooxml_parse_cells_shared_strings_and_merges():
    sheet_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
      <sheetData>
        <row r='1'>
          <c r='A1' t='s'><v>0</v></c>
          <c r='B1'><v>12.5</v></c>
          <c r='C1' t='inlineStr'><is><t>Inline</t></is></c>
        </row>
      </sheetData>
      <mergeCells count='1'><mergeCell ref='A1:B1'/></mergeCells>
    </worksheet>"""

    fake = _FakePackage({"xl/worksheets/sheet1.xml": sheet_xml})
    cells, merged, styles = fake.parse_worksheet_cells(
        "xl/worksheets/sheet1.xml", shared_strings=["Header"]
    )

    assert cells[(1, 1)] == "Header"
    assert cells[(1, 2)] == "12.5"
    assert cells[(1, 3)] == "Inline"
    assert merged == [(1, 1, 1, 2)]
    assert styles == {}
