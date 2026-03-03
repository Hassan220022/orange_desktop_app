"""
BDT Parser — extract structured data from Battery Discharge Test Excel files.

BDT files have a non-tabular layout with multiple sections in a single sheet.
Data is extracted by known cell positions (row, col) based on the standard
BDT template.
"""

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook


@dataclass
class PhotoSlot:
    """One labelled photo placeholder in the BDT template."""
    label: str                       # e.g. "Battery current", "PLVD set point"
    image_data: bytes | None = None  # raw JPEG/PNG bytes, None if empty
    image_ext: str = ""              # "jpeg" or "png"


@dataclass
class BDTData:
    """Structured data extracted from one BDT file."""
    file_path: str = ""
    filename: str = ""
    site_code: str = ""
    site_name: str = ""
    test_date: datetime | None = None
    time_in: str = ""
    time_out: str = ""

    # Discharge readings: list of (time_label, voltage, ampere)
    discharge_readings: list[tuple[str, float | None, float | None]] = field(
        default_factory=list)
    start_voltage: float | None = None
    start_ampere: float | None = None
    end_voltage: float | None = None
    end_ampere: float | None = None
    discharge_minutes: float = 0.0

    # Battery info
    ibat_before_test: float | None = None

    # Photos
    photo_count: int = 0
    photo_slots: list[PhotoSlot] = field(default_factory=list)

    # Parse errors
    errors: list[str] = field(default_factory=list)


def _safe_float(val) -> float | None:
    """Try to convert a cell value to float, return None on failure."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        s = str(val).strip().replace(",", ".")
        # Strip units like "AH", "AM", "V"
        for suffix in ("ah", "am", "a", "v", "vdc"):
            if s.lower().endswith(suffix):
                s = s[:-len(suffix)].strip()
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_str(val) -> str:
    """Convert cell value to stripped string, empty on None/NaN."""
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def parse_bdt_file(file_path: str) -> BDTData:
    """Parse a single BDT Excel file and return structured data.

    Uses openpyxl directly (not pandas) because the file layout is
    non-tabular — data is scattered across specific cell positions.
    """
    import os
    data = BDTData(file_path=file_path, filename=os.path.basename(file_path))

    try:
        wb = load_workbook(file_path, data_only=True)
    except Exception as e:
        data.errors.append(f"Cannot open file: {e}")
        return data

    # ── BDT sheet ─────────────────────────────────────────
    if "BDT sheet" not in wb.sheetnames:
        data.errors.append("Missing 'BDT sheet'")
        return data

    ws = wb["BDT sheet"]

    def cell(row, col):
        """1-indexed cell access (matches Excel row/col numbers)."""
        return ws.cell(row=row, column=col).value

    # Site info (rows 4-6 in 1-indexed = rows 3-5 in 0-indexed pandas)
    data.site_name = _safe_str(cell(5, 3))    # row 5, col C
    data.site_code = _safe_str(cell(5, 9))    # row 5, col I
    data.test_date = cell(4, 15)              # row 4, col O
    if isinstance(data.test_date, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                data.test_date = datetime.strptime(data.test_date.strip(), fmt)
                break
            except ValueError:
                continue
    data.time_in  = _safe_str(cell(5, 15))    # row 5, col O
    data.time_out = _safe_str(cell(6, 15))    # row 6, col O

    # Discharge test table — find it by scanning for "Batteries discharge test"
    discharge_start_row = None
    for r in range(1, ws.max_row + 1):
        v = _safe_str(cell(r, 2))
        if "batteries discharge test" in v.lower():
            discharge_start_row = r
            break

    if discharge_start_row:
        # Scan for "Before disconnecting Rectifier" row
        data_row = None
        for r in range(discharge_start_row + 1, discharge_start_row + 10):
            lbl = _safe_str(cell(r, 1)).lower()
            if "before disconnecting" in lbl:
                data_row = r
                break
        if data_row is None:
            data_row = discharge_start_row + 3  # fallback

        # Start readings (Before disconnecting)
        # Rec Bus Bar V/A are cols 4-5; String A values are cols 7,9,11,...
        data.start_voltage = _safe_float(cell(data_row, 4))
        data.start_ampere  = _safe_float(cell(data_row, 5))

        # Ibat before test = max of String A columns at "Before disconnecting"
        # String #1 A=col7, #2 A=col9, #3 A=col11, ... up to #8 A=col21
        string_amps = []
        for sc in range(7, 22, 2):  # cols 7, 9, 11, 13, 15, 17, 19, 21
            sa = _safe_float(cell(data_row, sc))
            if sa is not None:
                string_amps.append(sa)
        if string_amps:
            data.ibat_before_test = max(string_amps)

        # Discharge time-series — scan dynamically until "After Connecting"
        last_filled_mins = 0.0
        last_filled_voltage = None
        r = data_row + 1
        while r <= data_row + 30:  # safety limit
            lbl = _safe_str(cell(r, 1))
            if "after connecting" in lbl.lower():
                # End readings from "After Connecting" row if present
                data.end_voltage = _safe_float(cell(r, 4))
                data.end_ampere  = _safe_float(cell(r, 5))
                break
            if not lbl:
                r += 1
                continue
            v = _safe_float(cell(r, 4))
            a = _safe_float(cell(r, 5))
            data.discharge_readings.append((lbl, v, a))
            if v is not None:
                last_filled_voltage = v
            if v is not None or a is not None:
                try:
                    last_filled_mins = float(lbl.split()[0])
                except ValueError:
                    pass
            r += 1

        data.discharge_minutes = last_filled_mins

        # Fallback: if "After Connecting" row had no voltage, use last
        # filled Rec Bus Bar V from the discharge readings
        if data.end_voltage is None and last_filled_voltage is not None:
            data.end_voltage = last_filled_voltage

    wb.close()

    # Photo slots — extract labelled photos from drawing XML
    data.photo_slots, data.photo_count = _extract_photo_slots(file_path)

    return data


# ── Photo slot definitions ────────────────────────────────────
# Each slot: (label_row_1indexed, label_col_1indexed)
# 5 row bands × 3 column groups = 15 photo placeholders.
# Row bands (0-indexed anchor rows): 9-19, 21-32, 34-44, 46-56, 58-68
# Column groups (0-indexed): 12-16, 17-21, 22-26
_SLOT_DEFS: list[tuple[int, int]] = [
    # Band 0 — Rectifier
    (9, 13), (9, 18), (9, 23),
    # Band 1 — Batteries
    (21, 13), (21, 18), (21, 23),
    # Band 2 — CBs / Rack / LVD
    (34, 13), (34, 18), (34, 23),
    # Band 3 — Current / Load / PLVD
    (46, 13), (46, 18), (46, 23),
    # Band 4 — Charging / Disconnect / Reconnect
    (58, 13), (58, 18), (58, 23),
]

# Map (band_index, col_group_index) → slot index in _SLOT_DEFS
_BAND_RANGES = [(9, 19), (21, 32), (34, 44), (46, 56), (58, 68)]
_COL_GROUPS = [(12, 16), (17, 21), (22, 26)]


def _anchor_to_slot(from_row: int, from_col: int) -> int | None:
    """Map a 0-indexed anchor position to a slot index (0-14), or None."""
    band = None
    for bi, (lo, hi) in enumerate(_BAND_RANGES):
        if lo <= from_row <= hi:
            band = bi
            break
    if band is None:
        return None

    col_grp = None
    for ci, (lo, hi) in enumerate(_COL_GROUPS):
        if lo <= from_col <= hi:
            col_grp = ci
            break
    if col_grp is None:
        return None

    return band * 3 + col_grp


def _extract_photo_slots(file_path: str) -> tuple[list[PhotoSlot], int]:
    """Extract labelled photo slots from a BDT xlsx file.

    Returns (list_of_PhotoSlot, total_media_count).
    """
    import zipfile
    import xml.etree.ElementTree as ET

    ns_xdr = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"

    try:
        zf = zipfile.ZipFile(file_path)
    except Exception:
        return [], 0

    try:
        # Total media count (for backwards compat)
        media_files = [n for n in zf.namelist() if n.startswith("xl/media/")]
        total_media = len(media_files)

        # Find drawing rels path — look for drawing1.xml.rels
        drawing_rels_path = "xl/drawings/_rels/drawing1.xml.rels"
        drawing_path = "xl/drawings/drawing1.xml"
        if drawing_path not in zf.namelist():
            return [], total_media

        # Build rId → media zip path map from drawing rels
        rid_to_path: dict[str, str] = {}
        if drawing_rels_path in zf.namelist():
            rels_xml = ET.fromstring(zf.read(drawing_rels_path))
            for rel in rels_xml:
                rid = rel.get("Id", "")
                target = rel.get("Target", "")
                if target.startswith("../media/"):
                    rid_to_path[rid] = "xl/media/" + target.split("/")[-1]

        # Parse drawing XML — extract twoCellAnchor positions + rIds
        drawing_xml = ET.fromstring(zf.read(drawing_path))
        # slot_index → (rId, media_path)
        slot_images: dict[int, tuple[str, str]] = {}

        for anchor in drawing_xml.findall(f"{{{ns_xdr}}}twoCellAnchor"):
            frm = anchor.find(f"{{{ns_xdr}}}from")
            if frm is None:
                continue
            from_col = int(frm.find(f"{{{ns_xdr}}}col").text)
            from_row = int(frm.find(f"{{{ns_xdr}}}row").text)

            # Skip non-photo anchors (logo at col 0, etc.)
            if from_col < 12:
                continue

            slot_idx = _anchor_to_slot(from_row, from_col)
            if slot_idx is None or slot_idx in slot_images:
                continue

            # Find embedded image rId
            blip = anchor.find(f".//{{{ns_a}}}blip")
            if blip is None:
                continue
            rid = blip.get(f"{{{ns_r}}}embed", "")
            if not rid or rid not in rid_to_path:
                continue
            slot_images[slot_idx] = (rid, rid_to_path[rid])

        # Read labels from the worksheet and build PhotoSlot list
        # Re-open with openpyxl just for label reading
        wb = load_workbook(file_path, data_only=True)
        ws = wb["BDT sheet"] if "BDT sheet" in wb.sheetnames else None

        slots: list[PhotoSlot] = []
        for idx, (label_row, label_col) in enumerate(_SLOT_DEFS):
            # Read label from worksheet
            label = ""
            if ws is not None:
                raw = ws.cell(row=label_row, column=label_col).value
                label = _safe_str(raw) if raw else ""
            if not label:
                label = f"Slot {idx + 1}"

            img_data = None
            img_ext = ""
            if idx in slot_images:
                _, media_path = slot_images[idx]
                try:
                    img_data = zf.read(media_path)
                    img_ext = media_path.rsplit(".", 1)[-1].lower()
                except Exception:
                    pass

            slots.append(PhotoSlot(
                label=label, image_data=img_data, image_ext=img_ext))

        wb.close()
        return slots, total_media

    finally:
        zf.close()
