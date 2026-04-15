"""Minimal OOXML reader utilities for section-first BDT parsing."""

from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
_NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


@dataclass
class TwoCellAnchor:
    """Drawing anchor for one image object."""

    from_row: int
    from_col: int
    to_row: int
    to_col: int
    r_id: str
    drawing_path: str = ""
    media_path: str = ""


def _qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _resolve_part_path(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base_dir = posixpath.dirname(base_part)
    return posixpath.normpath(posixpath.join(base_dir, target))


def _col_to_index(col_ref: str) -> int:
    acc = 0
    for ch in col_ref.upper():
        if "A" <= ch <= "Z":
            acc = acc * 26 + (ord(ch) - ord("A") + 1)
    return acc


def _coord_to_row_col(coord: str) -> tuple[int, int]:
    m = re.match(r"^([A-Za-z]+)(\d+)$", coord or "")
    if not m:
        return 0, 0
    col = _col_to_index(m.group(1))
    row = int(m.group(2))
    return row, col


def _split_range(ref: str) -> tuple[int, int, int, int]:
    if ":" not in ref:
        r, c = _coord_to_row_col(ref)
        return r, c, r, c
    left, right = ref.split(":", 1)
    r1, c1 = _coord_to_row_col(left)
    r2, c2 = _coord_to_row_col(right)
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def _extract_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts = [t for t in el.itertext() if t]
    return "".join(parts).strip()


class OOXMLPackage:
    """Context manager exposing minimal OOXML workbook helpers."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._zip: zipfile.ZipFile | None = None

    def __enter__(self) -> "OOXMLPackage":
        self._zip = zipfile.ZipFile(self.file_path, "r")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None

    def _read(self, path: str) -> bytes:
        if self._zip is None:
            raise RuntimeError("OOXMLPackage is not opened")
        return self._zip.read(path)

    def _read_xml(self, path: str) -> ET.Element:
        return ET.fromstring(self._read(path))

    def read_workbook_xml(self) -> ET.Element:
        """Return parsed xl/workbook.xml root element."""

        return self._read_xml("xl/workbook.xml")

    def read_workbook_rels(self) -> dict[str, str]:
        """Return workbook relationship map of rId -> target path."""

        rels_path = "xl/_rels/workbook.xml.rels"
        rels = self._read_xml(rels_path)
        mapping: dict[str, str] = {}
        for rel in rels.findall(_qn(_NS_PKG_REL, "Relationship")):
            rid = rel.attrib.get("Id", "")
            target = rel.attrib.get("Target", "")
            if rid and target:
                mapping[rid] = _resolve_part_path("xl/workbook.xml", target)
        return mapping

    def resolve_worksheet_xml_path(self, sheet_name: str) -> str | None:
        """Resolve worksheet XML part path by sheet display name."""

        workbook = self.read_workbook_xml()
        rels = self.read_workbook_rels()
        for sheet in workbook.findall(f".//{_qn(_NS_MAIN, 'sheet')}"):
            if sheet.attrib.get("name") != sheet_name:
                continue
            rel_id = sheet.attrib.get(_qn(_NS_REL, "id"))
            if rel_id and rel_id in rels:
                return rels[rel_id]
        return None

    def list_media_files(self) -> list[str]:
        """List media paths in xl/media/."""

        if self._zip is None:
            raise RuntimeError("OOXMLPackage is not opened")
        return sorted(n for n in self._zip.namelist() if n.startswith("xl/media/"))

    def read_media(self, media_path: str) -> bytes:
        """Read one media blob by OOXML part path."""

        return self._read(media_path)

    def read_drawing_rels(self, drawing_xml_path: str) -> dict[str, str]:
        """Read drawing relationships mapping rId -> target part path."""

        rels_path = posixpath.join(
            posixpath.dirname(drawing_xml_path),
            "_rels",
            f"{posixpath.basename(drawing_xml_path)}.rels",
        )
        try:
            rels = self._read_xml(rels_path)
        except KeyError:
            return {}

        mapping: dict[str, str] = {}
        for rel in rels.findall(_qn(_NS_PKG_REL, "Relationship")):
            rid = rel.attrib.get("Id", "")
            target = rel.attrib.get("Target", "")
            if rid and target:
                mapping[rid] = _resolve_part_path(drawing_xml_path, target)
        return mapping

    def get_worksheet_drawing_paths(self, worksheet_xml_path: str) -> list[str]:
        """Return drawing XML paths linked from a worksheet."""

        ws_root = self._read_xml(worksheet_xml_path)
        rels_path = posixpath.join(
            posixpath.dirname(worksheet_xml_path),
            "_rels",
            f"{posixpath.basename(worksheet_xml_path)}.rels",
        )
        try:
            rels_root = self._read_xml(rels_path)
        except KeyError:
            return []

        rel_map: dict[str, str] = {}
        for rel in rels_root.findall(_qn(_NS_PKG_REL, "Relationship")):
            rid = rel.attrib.get("Id", "")
            target = rel.attrib.get("Target", "")
            rel_type = rel.attrib.get("Type", "")
            if rid and target and rel_type.endswith("/drawing"):
                rel_map[rid] = _resolve_part_path(worksheet_xml_path, target)

        drawing_paths: list[str] = []
        for drawing in ws_root.findall(f".//{_qn(_NS_MAIN, 'drawing')}"):
            rid = drawing.attrib.get(_qn(_NS_REL, "id"), "")
            if rid in rel_map:
                drawing_paths.append(rel_map[rid])
        return drawing_paths

    def resolve_rid_to_media_path(self, drawing_xml_path: str, r_id: str) -> str | None:
        """Resolve one drawing relationship id to a media path."""

        rels = self.read_drawing_rels(drawing_xml_path)
        return rels.get(r_id)

    def extract_two_cell_anchors(self, drawing_xml_path: str) -> list[TwoCellAnchor]:
        """Extract twoCellAnchor boxes and linked image relationship ids."""

        root = self._read_xml(drawing_xml_path)
        rels = self.read_drawing_rels(drawing_xml_path)
        anchors: list[TwoCellAnchor] = []

        for node in root.findall(_qn(_NS_XDR, "twoCellAnchor")):
            frm = node.find(_qn(_NS_XDR, "from"))
            to = node.find(_qn(_NS_XDR, "to"))
            if frm is None or to is None:
                continue

            from_row = int(_extract_text(frm.find(_qn(_NS_XDR, "row"))) or "0") + 1
            from_col = int(_extract_text(frm.find(_qn(_NS_XDR, "col"))) or "0") + 1
            to_row = int(_extract_text(to.find(_qn(_NS_XDR, "row"))) or "0") + 1
            to_col = int(_extract_text(to.find(_qn(_NS_XDR, "col"))) or "0") + 1

            blip = node.find(
                f".//{_qn(_NS_XDR, 'pic')}/{_qn(_NS_XDR, 'blipFill')}/{_qn(_NS_A, 'blip')}"
            )
            if blip is None:
                continue

            r_id = blip.attrib.get(_qn(_NS_REL, "embed"), "")
            anchors.append(
                TwoCellAnchor(
                    from_row=from_row,
                    from_col=from_col,
                    to_row=to_row,
                    to_col=to_col,
                    r_id=r_id,
                    drawing_path=drawing_xml_path,
                    media_path=rels.get(r_id, ""),
                )
            )

        return anchors

    def parse_shared_strings(self) -> list[str]:
        """Parse shared string table into a plain string list."""

        try:
            root = self._read_xml("xl/sharedStrings.xml")
        except KeyError:
            return []

        values: list[str] = []
        for si in root.findall(_qn(_NS_MAIN, "si")):
            txt = _extract_text(si)
            values.append(txt)
        return values

    def parse_worksheet_cells(
        self, worksheet_xml_path: str, shared_strings: list[str] | None = None
    ) -> tuple[dict[tuple[int, int], str], list[tuple[int, int, int, int]], dict[tuple[int, int], int]]:
        """Parse worksheet cells into sparse text map, merged ranges, and style ids."""

        shared_strings = shared_strings or []
        root = self._read_xml(worksheet_xml_path)

        cells: dict[tuple[int, int], str] = {}
        style_ids: dict[tuple[int, int], int] = {}

        for row in root.findall(f".//{_qn(_NS_MAIN, 'sheetData')}/{_qn(_NS_MAIN, 'row')}"):
            row_idx = int(row.attrib.get("r", "0"))
            for cell in row.findall(_qn(_NS_MAIN, "c")):
                ref = cell.attrib.get("r", "")
                r_idx, c_idx = _coord_to_row_col(ref)
                if r_idx <= 0:
                    r_idx = row_idx
                if c_idx <= 0:
                    continue

                key = (r_idx, c_idx)
                style_raw = cell.attrib.get("s")
                if style_raw and style_raw.isdigit():
                    style_ids[key] = int(style_raw)

                cell_type = cell.attrib.get("t", "")
                value = ""
                if cell_type == "s":
                    idx_text = _extract_text(cell.find(_qn(_NS_MAIN, "v")))
                    if idx_text.isdigit():
                        idx = int(idx_text)
                        if 0 <= idx < len(shared_strings):
                            value = shared_strings[idx]
                elif cell_type == "inlineStr":
                    value = _extract_text(cell.find(_qn(_NS_MAIN, "is")))
                else:
                    value = _extract_text(cell.find(_qn(_NS_MAIN, "v")))
                    if not value:
                        value = _extract_text(cell.find(_qn(_NS_MAIN, "is")))

                if value != "":
                    cells[key] = value

        merged_ranges: list[tuple[int, int, int, int]] = []
        for merge in root.findall(
            f".//{_qn(_NS_MAIN, 'mergeCells')}/{_qn(_NS_MAIN, 'mergeCell')}"
        ):
            ref = merge.attrib.get("ref", "")
            if ref:
                merged_ranges.append(_split_range(ref))

        return cells, merged_ranges, style_ids
