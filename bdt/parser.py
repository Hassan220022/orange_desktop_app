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
    category: str = "other"


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
    after_reconnect_voltage: float | None = None
    after_reconnect_ampere: float | None = None
    discharge_minutes: float = 0.0

    # Battery info
    ibat_before_test: float | None = None
    starting_ibattery_ampere: float | None = None
    battery_brand: str = ""
    battery_ah: float | None = None
    battery_voltage: float | None = None
    num_strings: int | None = None
    num_batteries: int | None = None
    num_modules: int | None = None
    rectifier_brand: str = ""
    pld_value: str = ""
    string_discharge_readings: list[list[tuple[float | None, float | None]]] = field(default_factory=list)
    summary_data: dict[str, str] = field(default_factory=dict)
    door_alarm_condition: bool | None = None

    # Photos
    photo_count: int = 0
    photo_slots: list[PhotoSlot] = field(default_factory=list)
    photos_deferred: bool = False

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
    if s.lower() in {"nan", "none", "null", "unknown", "n/a", "na", "-", "--"}:
        return ""
    return s


def _has_meaningful_numeric(*vals: float | None, zero_eps: float = 0.01) -> bool:
    """True when at least one numeric value is meaningfully non-zero."""
    for v in vals:
        if v is None:
            continue
        try:
            if abs(float(v)) > zero_eps:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _find_text_in_row_window(cell_fn, max_col: int, row_start: int, row_end: int,
                             needles: tuple[str, ...], search_cols: int | None = None):
    """Return (row, col) of the first cell containing all needle tokens."""
    end_col = min(max_col, search_cols) if search_cols else max_col
    for r in range(max(1, row_start), max(1, row_end) + 1):
        for c in range(1, end_col + 1):
            txt = _safe_str(cell_fn(r, c)).lower()
            if txt and all(n in txt for n in needles):
                return r, c
    return None, None


def _extract_row_label(cell_fn, row: int, preferred_col: int | None,
                       max_scan_col: int = 6) -> str:
    """Read a row label from preferred column, then fallback scan of first columns."""
    if preferred_col is not None:
        label = _safe_str(cell_fn(row, preferred_col))
        if label:
            return label
    for c in range(1, max_scan_col + 1):
        label = _safe_str(cell_fn(row, c))
        if label:
            return label
    return ""


_BRAND_KEYWORDS = (
    "lithium", "lith", "huawei", "zte", "narada", "shoto",
    "sacred sun", "ritar", "vision", "coslight", "byd",
    "pylontech", "gel", "agm", "vrla", "opzv", "opzs",
)


def _parse_battery_info(max_column, cell_fn, data: BDTData):
    """Extract battery specs from the BDT sheet.

    Standard BDT template layout (col 1 = label, col 9 = value):
        row 40: Battery brand
        row 42: Number of batteries connected to the rectifier
        row 44: Battery nominal voltage
        row 46: Battery ampere hour
        row 48: Number of strings

    Falls back to keyword scanning rows 35-65 if fixed positions don't match.
    """
    brand_raw = ""
    ah_raw = None
    voltage_raw = None
    strings_raw = None

    # ── Fixed-position extraction — standard BDT template ──
    candidate = _safe_str(cell_fn(40, 9))
    if candidate:
        brand_raw = candidate

    parsed = _safe_float(cell_fn(44, 9))
    if parsed is not None and parsed > 0:
        voltage_raw = parsed

    parsed = _safe_float(cell_fn(46, 9))
    if parsed is not None and parsed > 0:
        ah_raw = parsed

    parsed = _safe_float(cell_fn(48, 9))
    if parsed is not None and parsed > 0:
        strings_raw = int(parsed)

    # ── Keyword-based scan (rows 35-65) as fallback ──
    for r in range(35, 66):
        val = _safe_str(cell_fn(r, 1)).lower()
        if not val:
            val = _safe_str(cell_fn(r, 2)).lower()
        if not val:
            continue

        # Battery brand
        if not brand_raw and "battery brand" in val:
            candidate = _safe_str(cell_fn(r, 9))
            if candidate:
                brand_raw = candidate

        # Nominal voltage
        if voltage_raw is None and "nominal voltage" in val:
            parsed = _safe_float(cell_fn(r, 9))
            if parsed is not None and parsed > 0:
                voltage_raw = parsed

        # AH
        if ah_raw is None and "ampere hour" in val:
            parsed = _safe_float(cell_fn(r, 9))
            if parsed is not None and parsed > 0:
                ah_raw = parsed

        # Number of strings
        if strings_raw is None and "number of string" in val:
            parsed = _safe_float(cell_fn(r, 9))
            if parsed is not None and parsed > 0:
                strings_raw = int(parsed)

    # ── Brand detection from known manufacturer keywords ──
    if brand_raw:
        data.battery_brand = brand_raw
    else:
        # Try to find brand by scanning battery section for known names
        for r in range(35, 66):
            for c in (1, 2, 9):
                val = _safe_str(cell_fn(r, c)).lower()
                for kw in _BRAND_KEYWORDS:
                    if kw in val:
                        data.battery_brand = _safe_str(cell_fn(r, c))
                        break
                if data.battery_brand:
                    break
            if data.battery_brand:
                break

    data.battery_ah = ah_raw
    data.battery_voltage = voltage_raw
    data.num_strings = strings_raw


import re as _re

_DATE_IN_FILENAME = _re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
_SITE_CODE_TOKEN = _re.compile(r"(?<![A-Z0-9])(\d{4,5}[A-Z]{2})(?![A-Z0-9])")


def _extract_site_code_token(text: str) -> str:
    """Extract probable site code token (e.g. 0482SI, 4415DE) from text."""
    raw = _safe_str(text).upper()
    if not raw:
        return ""

    matches = [m.group(1) for m in _SITE_CODE_TOKEN.finditer(raw)]
    if not matches:
        return ""

    # Prefer the most frequent token; tie-break by first appearance.
    counts: dict[str, int] = {}
    first_idx: dict[str, int] = {}
    for i, token in enumerate(matches):
        counts[token] = counts.get(token, 0) + 1
        if token not in first_idx:
            first_idx[token] = i
    best = sorted(counts.keys(), key=lambda k: (-counts[k], first_idx[k]))[0]
    return best


def _resolve_bdt_sheet_name(sheet_names: list[str],
                            filename: str | None = None) -> str | None:
    """Return the best matching BDT sheet name, with pragmatic fallbacks."""
    if not sheet_names:
        return None

    # Exact canonical name first.
    for name in sheet_names:
        if str(name).strip() == "BDT sheet":
            return name

    # Case-insensitive match.
    for name in sheet_names:
        if str(name).strip().lower() == "bdt sheet":
            return name

    # Flexible normalization: allow variants like "BDT_Sheet", "Bdt-Sheet", "BDT SHEET(1)".
    def _norm(text: str) -> str:
        return "".join(ch for ch in str(text).lower() if ch.isalnum())

    for name in sheet_names:
        nm = _norm(name)
        if "bdt" in nm and "sheet" in nm:
            return name

    for name in sheet_names:
        nm = _norm(name)
        if nm.startswith("bdt"):
            return name

    # Last resort for BDT files: many real exports use a generic single/first sheet name.
    if filename and "bdt" in str(filename).lower():
        return sheet_names[0]

    return None


def _parse_test_date(cell_val, filename: str) -> datetime | None:
    """Coerce a cell value to a date, falling back to filename extraction.

    Calamine may return datetime.date, datetime.datetime, datetime.time,
    or garbage strings.
    """
    import datetime as _dt

    # datetime.date (calamine returns this for date-only cells)
    if isinstance(cell_val, _dt.date) and not isinstance(cell_val, datetime):
        if cell_val.year > 1900:
            return datetime(cell_val.year, cell_val.month, cell_val.day)

    # Already a proper datetime with a real year
    if isinstance(cell_val, datetime) and cell_val.year > 1900:
        return cell_val

    # String — try common formats
    if isinstance(cell_val, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(cell_val.strip(), fmt)
            except ValueError:
                continue

    # Fallback: extract date from filename (e.g. "14-1-2026")
    m = _DATE_IN_FILENAME.search(filename)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    return None


def _parse_summary_sheet(file_path: str, sheet_names: list[str]) -> dict[str, str]:
    """Read row 2 of the Summary sheet into a header->value dict."""
    target = None
    for name in sheet_names:
        if str(name).strip().lower() == "summary":
            target = name
            break
    if target is None:
        return {}

    rows = None
    try:
        import python_calamine
        wb = python_calamine.CalamineWorkbook.from_path(file_path)
        rows = wb.get_sheet_by_name(target).to_python()
    except Exception:
        pass

    if rows is None:
        try:
            owb = load_workbook(file_path, data_only=True)
            ws = owb[target]
            rows = []
            for row_cells in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 2),
                                          max_col=ws.max_column):
                rows.append([c.value for c in row_cells])
            owb.close()
        except Exception:
            return {}

    if not rows or len(rows) < 2:
        return {}

    headers = rows[0]
    values = rows[1]
    result: dict[str, str] = {}
    for i, hdr in enumerate(headers):
        hdr_str = _safe_str(hdr)
        if not hdr_str:
            continue
        val = values[i] if i < len(values) else None
        result[hdr_str] = _safe_str(val) if val is not None else ""
    return result


def parse_bdt_file(file_path: str, *, skip_photos: bool = False) -> BDTData:
    """Parse a single BDT Excel file and return structured data.

    Uses python-calamine (Rust-based reader, ~100x faster than openpyxl)
    for cell data extraction.  Falls back to openpyxl if calamine fails.

    Args:
        skip_photos: If True, skip photo extraction for faster batch
            processing.  Photos can be loaded later via
            ``load_bdt_photos()``.
    """
    import os
    data = BDTData(file_path=file_path, filename=os.path.basename(file_path))

    # ── Read sheet data with calamine (fast path) ────────
    rows = None
    all_sheet_names: list[str] = []
    try:
        import python_calamine
        wb = python_calamine.CalamineWorkbook.from_path(file_path)
        all_sheet_names = list(wb.sheet_names)
        bdt_sheet_name = _resolve_bdt_sheet_name(all_sheet_names, data.filename)
        if bdt_sheet_name is None:
            data.errors.append("Missing 'BDT sheet'")
            return data
        rows = wb.get_sheet_by_name(bdt_sheet_name).to_python()
    except Exception:
        pass

    # ── Fallback to openpyxl whenever calamine didn't yield rows ──
    if rows is None:
        try:
            owb = load_workbook(file_path, data_only=True)
        except Exception as e:
            data.errors.append(f"Cannot open file: {e}")
            return data
        all_sheet_names = list(owb.sheetnames)
        bdt_sheet_name = _resolve_bdt_sheet_name(all_sheet_names, data.filename)
        if bdt_sheet_name is None:
            data.errors.append("Missing 'BDT sheet'")
            owb.close()
            return data
        ows = owb[bdt_sheet_name]
        rows = []
        for row_cells in ows.iter_rows(min_row=1, max_row=ows.max_row,
                                        max_col=ows.max_column):
            rows.append([c.value for c in row_cells])
        owb.close()

    if rows is None:
        if not data.errors:
            data.errors.append("Failed to read BDT sheet")
        return data

    max_row = len(rows)
    max_col = max((len(r) for r in rows), default=0)

    def cell(row, col):
        """1-indexed cell access (matches Excel row/col numbers)."""
        r, c = row - 1, col - 1
        if r < 0 or r >= max_row:
            return None
        row_data = rows[r]
        if c < 0 or c >= len(row_data):
            return None
        return row_data[c]

    # Site info (fixed positions + fallback keyword scan)
    data.site_name = _safe_str(cell(4, 3))
    data.site_code = _safe_str(cell(4, 9))
    data.test_date = _parse_test_date(cell(3, 15), data.filename)
    data.time_in = _safe_str(cell(4, 15))
    data.time_out = _safe_str(cell(5, 15))

    # Alternate fixed positions for test_date when the default cell is empty
    if data.test_date is None:
        for rr, cc in ((2, 15), (4, 15), (3, 14), (3, 16), (1, 15), (5, 15)):
            parsed = _parse_test_date(cell(rr, cc), data.filename)
            if parsed is not None:
                data.test_date = parsed
                break

    # Keyword-based fallback scan for test_date
    if data.test_date is None:
        for r in range(1, min(max_row, 25) + 1):
            found = False
            for c in range(1, min(max_col, 12) + 1):
                text = _safe_str(cell(r, c)).lower()
                if not text:
                    continue
                if any(kw in text for kw in ("test date", "date of test",
                                              "التاريخ")) or text == "date":
                    for nc in range(c + 1, min(max_col, c + 6) + 1):
                        parsed = _parse_test_date(cell(r, nc), data.filename)
                        if parsed is not None:
                            data.test_date = parsed
                            found = True
                            break
                    if found:
                        break
            if data.test_date is not None:
                break

    # Final filename-only fallback (in case no cell yielded a date)
    if data.test_date is None:
        data.test_date = _parse_test_date(None, data.filename)

    for r in range(1, min(max_row, 20) + 1):
        label = _safe_str(cell(r, 1)).lower()
        if not label:
            label = _safe_str(cell(r, 2)).lower()
        if not label:
            continue

        if not data.site_code and ("site code" in label or label == "site id"):
            for c in range(2, min(max_col, 12) + 1):
                candidate = _safe_str(cell(r, c))
                token = _extract_site_code_token(candidate)
                if token:
                    data.site_code = token
                    break
                if candidate and "site" not in candidate.lower():
                    data.site_code = candidate
                    break

        if not data.site_name and "site name" in label:
            for c in range(2, min(max_col, 12) + 1):
                candidate = _safe_str(cell(r, c))
                if candidate and "site" not in candidate.lower():
                    data.site_name = candidate
                    break

        if not data.time_in and "time in" in label:
            for c in range(2, min(max_col, 20) + 1):
                candidate = _safe_str(cell(r, c))
                if candidate:
                    data.time_in = candidate
                    break

        if not data.time_out and "time out" in label:
            for c in range(2, min(max_col, 20) + 1):
                candidate = _safe_str(cell(r, c))
                if candidate:
                    data.time_out = candidate
                    break

    # Normalize + fallback site-code extraction:
    # Prefer explicit token sources over any free-text value.
    filename_token = _extract_site_code_token(data.filename)
    sheet_site_token = _extract_site_code_token(data.site_code)
    site_name_token = _extract_site_code_token(data.site_name)

    if sheet_site_token:
        data.site_code = sheet_site_token
    elif filename_token:
        data.site_code = filename_token
    elif site_name_token:
        data.site_code = site_name_token
    elif data.site_code:
        # Keep legacy free-text only as last resort.
        data.site_code = data.site_code.strip().upper()

    # Discharge test table — find by scanning for "Batteries discharge test"
    discharge_start_row = None
    for r in range(1, max_row + 1):
        for c in range(1, min(max_col, 8) + 1):
            v = _safe_str(cell(r, c))
            if "batteries discharge test" in v.lower():
                discharge_start_row = r
                break
        if discharge_start_row is not None:
            break

    if discharge_start_row:
        # Detect table columns by header row ("Rec Bus Bar", "String #")
        rec_v_col, rec_a_col = 4, 5
        string_a_cols: list[int] = []
        hdr_row, hdr_col = _find_text_in_row_window(
            cell, max_col, discharge_start_row, discharge_start_row + 8,
            needles=("rec", "bus", "bar"),
        )
        if hdr_row and hdr_col:
            rec_v_col = hdr_col
            rec_a_col = min(max_col, hdr_col + 1)
            for c in range(hdr_col + 2, max_col + 1):
                txt = _safe_str(cell(hdr_row, c)).lower()
                if "string" in txt:
                    a_col = c + 1
                    if a_col <= max_col:
                        string_a_cols.append(a_col)
        else:
            # Legacy fixed template
            for sc in range(7, 22, 2):
                if sc <= max_col:
                    string_a_cols.append(sc)

        # Scan for "Before disconnecting Rectifier" row
        data_row, label_col = _find_text_in_row_window(
            cell, max_col, discharge_start_row + 1, discharge_start_row + 12,
            needles=("before", "disconnect"),
            search_cols=6,
        )
        if data_row is None:
            data_row = discharge_start_row + 3
        if label_col is None:
            label_col = 1

        data.start_voltage = _safe_float(cell(data_row, rec_v_col))
        data.start_ampere = _safe_float(cell(data_row, rec_a_col))

        string_amps = []
        for sc in string_a_cols:
            sa = _safe_float(cell(data_row, sc))
            if sa is not None:
                string_amps.append(sa)
        if string_amps:
            data.ibat_before_test = max(string_amps)
            data.starting_ibattery_ampere = data.ibat_before_test

        # Capture per-string (V, A) pairs for the "Before disconnecting" row
        all_string_readings: list[list[tuple[float | None, float | None]]] = []
        if string_a_cols:
            before_row_pairs: list[tuple[float | None, float | None]] = []
            for sc in string_a_cols:
                sv = _safe_float(cell(data_row, sc - 1))
                sa = _safe_float(cell(data_row, sc))
                before_row_pairs.append((sv, sa))
            all_string_readings.append(before_row_pairs)

        # Discharge time-series
        last_filled_mins = 0.0
        last_filled_voltage = None
        last_filled_ampere = None
        r = data_row + 1
        while r <= data_row + 30:
            lbl = _extract_row_label(cell, r, label_col)
            if "after connecting" in lbl.lower():
                data.after_reconnect_voltage = _safe_float(cell(r, rec_v_col))
                data.after_reconnect_ampere = _safe_float(cell(r, rec_a_col))
                break
            if not lbl:
                r += 1
                continue
            v = _safe_float(cell(r, rec_v_col))
            a = _safe_float(cell(r, rec_a_col))
            row_string_vals = [_safe_float(cell(r, sc)) for sc in string_a_cols]
            if string_a_cols:
                row_string_pairs: list[tuple[float | None, float | None]] = []
                for sc in string_a_cols:
                    sv = _safe_float(cell(r, sc - 1))
                    sa = _safe_float(cell(r, sc))
                    row_string_pairs.append((sv, sa))
                all_string_readings.append(row_string_pairs)
            has_data = _has_meaningful_numeric(v, a, *row_string_vals)

            if not has_data:
                # Hide formula-driven zeros/placeholder rows from parsed readings.
                v = None
                a = None

            data.discharge_readings.append((lbl, v, a))
            if v is not None:
                last_filled_voltage = v
            if a is not None:
                last_filled_ampere = a
            if has_data:
                try:
                    last_filled_mins = float(str(lbl).split()[0])
                except (ValueError, TypeError, IndexError):
                    pass
            r += 1

        data.discharge_minutes = last_filled_mins
        data.end_voltage = last_filled_voltage
        data.end_ampere  = last_filled_ampere
        data.string_discharge_readings = all_string_readings

    _parse_battery_info(max_col, cell, data)

    # ── Rectifier / module / battery-count / PLVD fields ──
    # Fixed-position extraction
    data.rectifier_brand = _safe_str(cell(13, 9))
    _mod_raw = _safe_float(cell(17, 9))
    if _mod_raw is not None and _mod_raw > 0:
        data.num_modules = int(_mod_raw)
    _batt_raw = _safe_float(cell(43, 9))
    if _batt_raw is not None and _batt_raw > 0:
        data.num_batteries = int(_batt_raw)
    data.pld_value = _safe_str(cell(29, 9))

    # Keyword-fallback scanning
    if not data.rectifier_brand:
        _r, _c = _find_text_in_row_window(cell, max_col, 10, 16,
                                           needles=("rectifier", "type"))
        if _r is not None:
            data.rectifier_brand = _safe_str(cell(_r, 9))

    if data.num_modules is None:
        _r, _c = _find_text_in_row_window(cell, max_col, 15, 20,
                                           needles=("number", "modules"))
        if _r is not None:
            _v = _safe_float(cell(_r, 9))
            if _v is not None and _v > 0:
                data.num_modules = int(_v)

    if data.num_batteries is None:
        _r, _c = _find_text_in_row_window(cell, max_col, 40, 46,
                                           needles=("number", "batteries", "connected"))
        if _r is not None:
            _v = _safe_float(cell(_r, 9))
            if _v is not None and _v > 0:
                data.num_batteries = int(_v)

    if not data.pld_value:
        _r, _c = _find_text_in_row_window(cell, max_col, 25, 32,
                                           needles=("plvd", "set"))
        if _r is None:
            _r, _c = _find_text_in_row_window(cell, max_col, 25, 32,
                                               needles=("lvd", "disconnect"))
        if _r is not None:
            data.pld_value = _safe_str(cell(_r, 9))

    # Summary sheet
    data.summary_data = _parse_summary_sheet(file_path, all_sheet_names)

    # Photo slots
    if not skip_photos:
        data.photo_slots, data.photo_count = _extract_photo_slots(file_path)
        data.photos_deferred = False
    else:
        data.photos_deferred = True

    return data


def load_bdt_photos(bdt: BDTData) -> None:
    """Lazy-load photo slots for a BDTData that was parsed with skip_photos."""
    if bdt.photo_slots:
        bdt.photos_deferred = False
        return  # already loaded
    bdt.photo_slots, bdt.photo_count = _extract_photo_slots(bdt.file_path)
    bdt.photos_deferred = False


# ── Photo slot definitions ────────────────────────────────────
# Each slot: (label_row_1indexed, label_col_1indexed)
# 5 row bands × 3 column groups = 15 photo placeholders.
# Row bands (0-indexed anchor rows) and column groups for photo slot mapping.
# 4 column groups per band = 20 total slots (5 bands × 4 cols).
_SLOT_DEFS: list[tuple[int, int]] = [
    # Band 0 — Rectifier (outside, inside, modules, extra)
    (9, 13), (9, 18), (9, 23), (9, 28),
    # Band 1 — Batteries (photo1, photo2, settings, extra)
    (21, 13), (21, 18), (21, 23), (21, 28),
    # Band 2 — CBs / Rack / LVD / extra
    (34, 13), (34, 18), (34, 23), (34, 28),
    # Band 3 — Current / Load / PLVD / extra
    (46, 13), (46, 18), (46, 23), (46, 28),
    # Band 4 — Charging / Disconnect / Reconnect / After-reconnect current
    (58, 13), (58, 18), (58, 23), (58, 28),
]

_BAND_CATEGORIES = {
    0: "rectifier",
    1: "batteries",
    2: "modules",
    3: "load",
    4: "charging",
}

# Band ranges use exclusive upper bound (lo <= row < hi) to avoid overlap.
# Widened by 1 row on each side to catch boundary-anchored images.
_BAND_RANGES = [(8, 21), (21, 34), (34, 46), (46, 58), (58, 70)]
# 4 column groups: original 3 + cols 27-31 for extra photo slot.
# Start at col 11 to catch images placed 1 column left of the expected position.
_COL_GROUPS = [(11, 16), (17, 21), (22, 26), (27, 31)]
_COLS_PER_BAND = len(_COL_GROUPS)  # 4


def _anchor_to_slot(from_row: int, from_col: int) -> int | None:
    """Map a 0-indexed anchor position to a slot index (0-19), or None."""
    band = None
    for bi, (lo, hi) in enumerate(_BAND_RANGES):
        if lo <= from_row < hi:  # exclusive upper bound prevents overlap
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

    return band * _COLS_PER_BAND + col_grp


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

        # Find the drawing XML that belongs to the BDT sheet only.
        # Each worksheet references its own drawing via its .rels file.
        # We must NOT parse drawings from other sheets (e.g. Power Alarm)
        # because their images (alarm emails, BTS screenshots) would
        # contaminate the BDT photo grid.
        all_names = zf.namelist()

        # Step 1: Find which sheet XML file is the BDT sheet
        ns_ss = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        bdt_sheet_file = None
        try:
            wb_xml = ET.fromstring(zf.read("xl/workbook.xml"))
            wb_rels_xml = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rid_to_sheet = {}
            for rel in wb_rels_xml:
                rid_to_sheet[rel.get("Id", "")] = rel.get("Target", "")
            bdt_sheet_name = _resolve_bdt_sheet_name(
                [s.get("name", "") for s in wb_xml.findall(f".//{{{ns_ss}}}sheet")])
            if bdt_sheet_name:
                ns_r_wb = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                for s in wb_xml.findall(f".//{{{ns_ss}}}sheet"):
                    if s.get("name") == bdt_sheet_name:
                        rid = s.get(f"{{{ns_r_wb}}}id", "")
                        target = rid_to_sheet.get(rid, "")
                        if target:
                            bdt_sheet_file = "xl/" + target if not target.startswith("xl/") else target
                        break
        except Exception:
            pass

        # Step 2: Find drawing path from BDT sheet's rels
        drawing_paths = []
        if bdt_sheet_file:
            sheet_basename = bdt_sheet_file.rsplit("/", 1)[-1]
            sheet_rels = f"xl/worksheets/_rels/{sheet_basename}.rels"
            if sheet_rels in all_names:
                try:
                    sr_xml = ET.fromstring(zf.read(sheet_rels))
                    for rel in sr_xml:
                        target = rel.get("Target", "")
                        if "drawing" in target.lower():
                            # Resolve relative path
                            dp = "xl/drawings/" + target.rsplit("/", 1)[-1]
                            if dp in all_names:
                                drawing_paths.append(dp)
                except Exception:
                    pass

        # Fallback: if we couldn't determine the BDT sheet's drawing,
        # use only drawing1.xml (the first sheet's drawing)
        if not drawing_paths:
            fallback = "xl/drawings/drawing1.xml"
            if fallback in all_names:
                drawing_paths = [fallback]

        if not drawing_paths:
            return [], total_media

        # Build rId → media zip path map from BDT drawing rels only
        rid_to_path: dict[str, str] = {}
        for dp in drawing_paths:
            dp_basename = dp.rsplit("/", 1)[-1]
            rels_path = f"xl/drawings/_rels/{dp_basename}.rels"
            if rels_path in all_names:
                rels_xml = ET.fromstring(zf.read(rels_path))
                for rel in rels_xml:
                    rid = rel.get("Id", "")
                    target = rel.get("Target", "")
                    if target.startswith("../media/"):
                        rid_to_path[rid] = "xl/media/" + target.split("/")[-1]

        # Parse BDT drawing only — extract twoCellAnchor positions + rIds
        slot_images: dict[int, tuple[str, str, int]] = {}  # slot_idx -> (rId, media_path, anchor_row)

        for dp in drawing_paths:
            drawing_xml = ET.fromstring(zf.read(dp))
            for anchor in drawing_xml.findall(f"{{{ns_xdr}}}twoCellAnchor"):
                frm = anchor.find(f"{{{ns_xdr}}}from")
                if frm is None:
                    continue
                from_col = int(frm.find(f"{{{ns_xdr}}}col").text)
                from_row = int(frm.find(f"{{{ns_xdr}}}row").text)

                # Skip non-photo anchors (logo at col 0, etc.)
                if from_col < 11:
                    continue

                slot_idx = _anchor_to_slot(from_row, from_col)
                if slot_idx is None:
                    continue
                # On duplicate, keep the anchor whose row is closest to the
                # slot's expected label row so the right image wins.
                if slot_idx in slot_images:
                    expected_row = _SLOT_DEFS[slot_idx][0] if slot_idx < len(_SLOT_DEFS) else 0
                    prev_row = slot_images[slot_idx][2]
                    if abs(from_row - expected_row) >= abs(prev_row - expected_row):
                        continue  # existing anchor is closer, keep it

                # Find embedded image rId
                blip = anchor.find(f".//{{{ns_a}}}blip")
                if blip is None:
                    continue
                rid = blip.get(f"{{{ns_r}}}embed", "")
                if not rid or rid not in rid_to_path:
                    continue
                slot_images[slot_idx] = (rid, rid_to_path[rid], from_row)

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
                _, media_path, _ = slot_images[idx]
                try:
                    img_data = zf.read(media_path)
                    img_ext = media_path.rsplit(".", 1)[-1].lower()
                except Exception:
                    pass

            slots.append(PhotoSlot(
                label=label,
                image_data=img_data,
                image_ext=img_ext,
                category=_BAND_CATEGORIES.get(idx // _COLS_PER_BAND, "other"),
            ))

        wb.close()
        return slots, total_media

    finally:
        zf.close()
