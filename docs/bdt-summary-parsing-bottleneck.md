# BDT Summary Workbook Parsing Bottleneck — Architecture Analysis

## Problem

Large BDT summary workbooks (e.g. `Huawel_BDT Summary_2024.xlsx`) take 10+ minutes to
process during batch BDT validation. A progress indicator showing 3496/3497 files stuck for
extended periods indicates a single-file bottleneck in the parsing chain.

## Root Cause: Multi-Layer Silent Fallback Cascade

The bottleneck forms when `python-calamine` (the Rust-based fast reader) fails on a large
workbook. The code silently falls back to `openpyxl`, which then re-opens the file up to
**three times** in a single `parse_bdt_file` call. Each openpyxl open on a large workbook
is expensive, and the cumulative cost produces the observed 10+ minute hang.

### The three file opens in one `parse_bdt_file` call

```
parse_bdt_file(file_path)
 ├─ [OPEN 1] calamine → fails silently → openpyxl loads ALL sheets
 │   bdt/parser.py:725-755
 │
 ├─ [OPEN 2] _parse_summary_sheet → calamine fails again → openpyxl loads ALL sheets again
 │   bdt/parser.py:1092 → bdt/parser.py:670-688
 │
 └─ [OPEN 3] _extract_photo_slots → opens as ZIP/OOXML, reads XML + images
     bdt/parser.py:1095 → bdt/parser.py:1275-1416
```

## Detailed Trace Through the Parsing Chain

### Step 1 — Calamine silent failure (`bdt/parser.py:725-734`)

```python
try:
    wb = python_calamine.CalamineWorkbook.from_path(file_path)
    all_sheet_names = list(wb.sheet_names)
    bdt_sheet_name = _resolve_bdt_sheet_name(all_sheet_names, data.filename)
    if bdt_sheet_name is None:
        data.errors.append("Missing 'BDT sheet'")
        return data
    rows = wb.get_sheet_by_name(bdt_sheet_name).to_python()
except Exception:
    pass  # ← silently swallows ALL calamine failures. No log. No visibility.
```

If calamine throws any exception — unsupported Excel feature, password protection,
malformed XML, memory error — the entire block is discarded without a trace.

### Step 2 — openpyxl full load fallback (`bdt/parser.py:737-755`)

```python
if rows is None:
    owb = load_workbook(file_path, data_only=True)  # pure Python, parses EVERY sheet
    ows = owb[bdt_sheet_name]
    rows = []
    for row_cells in ows.iter_rows(min_row=1, max_row=ows.max_row,
                                    max_col=ows.max_column):
        rows.append([c.value for c in row_cells])
    owb.close()
```

`load_workbook(data_only=True)` constructs Python DOM objects for every cell, style
definition, and shared string across **all sheets** in the workbook. For a summary
workbook with hundreds of site sheets and thousands of rows per sheet, this pure-Python
XML parse and object allocation is the dominant time cost — typically 5-15 minutes.

### Step 3 — Summary sheet re-open (`bdt/parser.py:1092`)

```python
data.summary_data = _parse_summary_sheet(file_path, all_sheet_names)
```

`_parse_summary_sheet` (`bdt/parser.py:670-688`) has its own independent calamine →
openpyxl fallback chain. Since calamine already failed in step 1, it fails here too.
openpyxl re-loads the **entire** workbook a second time, just to read row 1 and row 2
of the "Summary" sheet.

### Step 4 — Photo extraction re-open (`bdt/parser.py:1095`)

```python
if not skip_photos:
    data.photo_slots, ... = _extract_photo_slots(file_path, ...)
```

`_extract_photo_slots_structural` (`bdt/parser.py:1275-1416`) opens the file as a ZIP
archive, parses worksheet XML with ElementTree, extracts drawing anchors, and reads
embedded image bytes. For a summary workbook with many embedded photos, this is a
third full file read and parse.

## Secondary Issues

### Overly broad sheet-name resolution (`bdt/parser.py:608`)

```python
if nm.startswith("bdt"):
    return name
```

If calamine does succeed but the workbook has a sheet named `"BDT Summary"`, this
check matches it because the normalized version `"bdtsummary"` starts with `"bdt"`.
The parser then loads and scans the summary sheet as a BDT template, searching every
row for discharge table headers (`bdt/parser.py:916`).

The `_resolve_bdt_sheet_name` function has a summary-detection escape hatch at
line 554-563, but it only triggers when the workbook has **no** sheet matching BDT
variants. Since `"bdt"` is one of the variant keywords (`_BDT_SHEET_VARIANTS` at
line 479), any sheet name containing "bdt" disables the escape.

### No observable logging for calamine failures

The `except Exception: pass` at line 734 means operators and developers have zero
visibility into calamine compatibility issues. Without logs, any field report of
"the app is stuck" requires code-level debugging to trace.

### `_parse_summary_sheet` re-implements the dual-engine pattern

The calamine → openpyxl fallback logic is duplicated across `parse_bdt_file`,
`_parse_summary_sheet`, `_quick_header_check`, `_extract_summary_rows`, and
`read_site_sheet`. Each copy handles exceptions independently. A unified engine
abstraction would eliminate the re-open problem in `_parse_summary_sheet` by
allowing it to reuse the already-loaded workbook.

## Impact Summary

| Layer | What happens | Time cost (est.) |
|-------|-------------|-----------------|
| calamine `from_path` | Fails silently on large/special workbooks | < 1s |
| openpyxl `load_workbook` | Parses all sheets, styles, strings in pure Python | 3-10 min |
| `_parse_summary_sheet` | Second full openpyxl load | 3-10 min |
| `_extract_photo_slots_structural` | Third open, ZIP + XML parse + image read | 1-3 min |
| **Cumulative** | Three back-to-back file opens | **7-25 min** |

## File Reference Map

| File | Lines | Role |
|------|-------|------|
| `bdt/parser.py` | 705-761 | Main `parse_bdt_file` entry: calamine → openpyxl fallback |
| `bdt/parser.py` | 660-702 | `_parse_summary_sheet`: independent dual-engine re-open |
| `bdt/parser.py` | 537-621 | `_resolve_bdt_sheet_name`: summary detection + sheet name matching |
| `bdt/parser.py` | 1275-1416 | `_extract_photo_slots_structural`: OOXML ZIP open for photo extraction |
| `bdt/parser.py` | 1441-1662 | `_extract_photo_slots_layout`: image extraction via ZIP + openpyxl labels |
| `ui/threads.py` | 434-594 | `BDTValidationThread`: batch orchestration, parallel file processing |
| `data/loaders.py` | 219-276 | `_extract_summary_rows`: calamine → openpyxl for summary extraction |
| `data/loaders.py` | 279-295 | `_load_external_summary_lookup`: pre-processing summary candidate discovery |
