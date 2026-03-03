# Alarm ID Classification & BDT Validation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace filename-based alarm category detection with configurable alarm ID lists, and add a BDT validation tab that cross-references Battery Discharge Test reports against loaded alarm data to catch fraudulent tests.

**Architecture:** Two independent features sharing the alarm data. Alarm ID config lives in `~/.alarm_viewer/alarm_ids.json`, loaded/saved via `state.py`. BDT parsing and validation are separate modules (`bdt_parser.py`, `bdt_validator.py`). The main window gains a tab bar to hold the existing Alarms view and the new Test Validation tab.

**Tech Stack:** Python 3.14, PyQt5, pandas, openpyxl (already in requirements).

**Design doc:** `docs/plans/2026-03-02-alarm-id-classification-and-bdt-validation-design.md`

**How to run:** `cd "/Volumes/nvme 500/Alarms" && "/Volumes/nvme 500/Alarms/alarm_app/.venv/bin/python3" -m alarm_app.main`

**Note:** This is a PyQt5 desktop app with no test framework. Verification is done by running the app after each task.

---

## Task 1: Alarm ID Config — state.py + constants.py

Add alarm ID config load/save functions to `state.py` and add BDT-related constants.

**Files:**

- Modify: `alarm_app/state.py`
- Modify: `alarm_app/constants.py`

**Step 1: Add alarm ID config functions to state.py**

Add to the bottom of `alarm_app/state.py` (after `clear_cache()`):

```python
# ── Alarm ID configuration ────────────────────────────────
ALARM_IDS_FILE = STATE_DIR / "alarm_ids.json"

def load_alarm_ids() -> dict:
    """Return {"power": [...], "down": [...]} from config, or empty defaults."""
    try:
        if ALARM_IDS_FILE.exists():
            data = json.loads(ALARM_IDS_FILE.read_text(encoding="utf-8"))
            return {
                "power": [str(x).strip() for x in data.get("power", [])],
                "down":  [str(x).strip() for x in data.get("down", [])],
            }
    except Exception:
        pass
    return {"power": [], "down": []}


def save_alarm_ids(ids: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ALARM_IDS_FILE.write_text(
        json.dumps(ids, indent=2), encoding="utf-8")
```

**Step 2: Add BDT constants to constants.py**

Append to the bottom of `alarm_app/constants.py`:

```python
# ── BDT validation constants ──────────────────────────────
BDT_DEFAULT_TOLERANCE = 0.15   # 15%

BDT_RULES = [
    ("R1", "Photos"),
    ("R2", "Power Alarm Match"),
    ("R3", "Duration Match"),
    ("R4", "Discharge Table Match"),
    ("R5", "Start Ampere = 0"),
    ("R6", "End Voltage Range"),
    ("R7", "V/A Inverse"),
]

BDT_RESULT_HEADERS = [
    "File", "Site Code", "Test Date", "Verdict",
    "R1", "R2", "R3", "R4", "R5", "R6", "R7",
]

BDT_RESULT_WIDTHS = {
    "File": 200, "Site Code": 90, "Test Date": 100, "Verdict": 90,
    "R1": 65, "R2": 65, "R3": 65, "R4": 65,
    "R5": 65, "R6": 65, "R7": 65,
}
```

**Step 3: Commit**

```
feat: add alarm ID config functions and BDT constants
```

---

## Task 2: Replace Filename-Based Category Detection — parsers.py

Remove the filename keyword logic from `discover_alarm_files()` and `parse_alarm_file()`. Category is now determined by matching `alarm_id` against the configured lists, done post-load.

**Files:**

- Modify: `alarm_app/parsers.py`

**Step 1: Update discover_alarm_files — remove category from file discovery**

In `alarm_app/parsers.py`, function `discover_alarm_files()` (line 31-54), change the dict construction. Remove the `cat = ...` logic and the `"category"` key:

Replace lines 45-53 (inside the inner loop):

```python
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, directory)
            kb   = os.path.getsize(full) / 1024
            results.append({
                "path": full, "rel_path": rel,
                "filename": fname, "ext": ext,
                "size_kb": kb,
            })
```

**Step 2: Update parse_alarm_file — remove file-level category assignment**

In `parse_alarm_file()` (line 60-99), replace line 91:

```python
    df["alarm_category"] = info["category"]
```

with:

```python
    df["alarm_category"] = "Unknown"
```

The actual classification happens later via `classify_by_alarm_id()`.

**Step 3: Add classify_by_alarm_id function**

Add after `parse_alarm_file()` in `parsers.py`:

```python
def classify_by_alarm_id(df: pd.DataFrame, alarm_ids: dict) -> pd.DataFrame:
    """Classify alarm_category based on alarm_id matching configured ID lists.

    Args:
        df: DataFrame with 'alarm_id' and 'alarm_category' columns.
        alarm_ids: {"power": ["id1", ...], "down": ["id1", ...]}
    Returns:
        DataFrame with updated 'alarm_category' column.
    """
    if df.empty or "alarm_id" not in df.columns:
        return df
    power_set = set(alarm_ids.get("power", []))
    down_set  = set(alarm_ids.get("down", []))
    aid = df["alarm_id"].fillna("").astype(str).str.strip()
    df = df.copy()
    df.loc[aid.isin(power_set), "alarm_category"] = "Power"
    df.loc[aid.isin(down_set),  "alarm_category"] = "Down"
    return df
```

**Step 4: Commit**

```
feat: replace filename-based category with alarm ID classification
```

---

## Task 3: Wire Classification Into Viewer + LoaderThread

The viewer needs to call `classify_by_alarm_id()` after loading data, and re-classify when alarm IDs config changes.

**Files:**

- Modify: `alarm_app/viewer.py`

**Step 1: Add imports**

At top of `viewer.py`, update the parsers import (line 28):

```python
from .parsers import discover_alarm_files, LoaderThread, ExportThread, classify_by_alarm_id
```

Add state import for alarm IDs — `state` is already imported (line 30). No new import needed.

**Step 2: Classify after loading**

In `_on_loaded()` method (around line 1151), after `self._full_df = df`, add classification:

```python
    def _on_loaded(self, df: pd.DataFrame, msg: str):
        # Classify by alarm ID config
        alarm_ids = state.load_alarm_ids()
        df = classify_by_alarm_id(df, alarm_ids)
        self._full_df = df
```

(Move `self._full_df = df` to after the classify call.)

**Step 3: Classify after cache restore**

In `_on_cache_restored()` (around line 788), after setting `self._full_df = df`, add:

```python
        alarm_ids = state.load_alarm_ids()
        df = classify_by_alarm_id(df, alarm_ids)
        self._full_df = df
```

**Step 4: Add re-classify helper**

Add a method to `AlarmViewer`:

```python
    def _reclassify_alarms(self):
        """Re-classify all loaded alarms using current alarm ID config."""
        if self._full_df.empty:
            return
        alarm_ids = state.load_alarm_ids()
        self._full_df = classify_by_alarm_id(self._full_df, alarm_ids)
        view = self._apply_filters(self._full_df)
        self._populate(view)
        self._refresh_stats(view)
        self._lbl_count.setText(
            f"Showing  {len(view):,}  of  {len(self._full_df):,} records")
        self._sbar.showMessage("Alarms re-classified by alarm ID config")
```

**Step 5: Update \_scan — remove category display from file list**

In `_scan()` method, update the file list item creation. The `info["category"]` key no longer exists. Replace the tag/color logic (around lines 1091-1106):

```python
        for info in self._file_infos:
            line = (
                f"{info['filename']:<{max_f}}  "
                f"{info['ext'].upper().lstrip('.'):<4}  "
                f"{info['size_kb']:>9.1f} KB")
            rel_dir = os.path.dirname(info["rel_path"])
            if rel_dir:
                line += f"   -> {rel_dir}"
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, info)
            item.setForeground(QColor("#6c7086"))
            self._file_list.addItem(item)
```

Update the file count label (remove Power/Down counts):

```python
        n = len(self._file_infos)
        self._lbl_file_count.setText(f"  {n} file{'s' if n != 1 else ''}")
        self._lbl_file_count.setStyleSheet("color:#a6e3a1; font-size:11px;")
```

**Step 6: Verify** — Run the app, load alarm files, confirm alarms show "Unknown" category (since no IDs configured yet).

**Step 7: Commit**

```
feat: wire alarm ID classification into data loading pipeline
```

---

## Task 4: Alarm ID Config Dialog

**Files:**

- Modify: `alarm_app/viewer.py`

**Step 1: Add AlarmIdConfigDialog class**

Add before `class AlarmViewer` in `viewer.py`:

```python
class AlarmIdConfigDialog(QDialog):
    """Dialog to configure Power/Down alarm ID lists."""

    saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Alarm IDs")
        self.setFixedSize(460, 420)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        note = QLabel(
            "Enter alarm IDs (comma-separated) to classify alarms.\n"
            "IDs not in either list will be categorised as 'Unknown'.")
        note.setStyleSheet("color:#6c7086; font-size:11px;")
        note.setWordWrap(True)
        lay.addWidget(note)

        # Power IDs
        lbl_p = QLabel("Power Alarm IDs")
        lbl_p.setStyleSheet(
            "color:#f38ba8; font-size:12px; font-weight:600;")
        lay.addWidget(lbl_p)
        self._txt_power = QLineEdit()
        self._txt_power.setPlaceholderText("e.g. 22001, 22002, 22003")
        self._txt_power.setMinimumHeight(32)
        lay.addWidget(self._txt_power)

        # Down IDs
        lbl_d = QLabel("Down Alarm IDs")
        lbl_d.setStyleSheet(
            "color:#fab387; font-size:12px; font-weight:600;")
        lay.addWidget(lbl_d)
        self._txt_down = QLineEdit()
        self._txt_down.setPlaceholderText("e.g. 35001, 35002, 35003")
        self._txt_down.setMinimumHeight(32)
        lay.addWidget(self._txt_down)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_save = QPushButton("Save")
        btn_save.setObjectName("btn_search")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_clear")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        lay.addLayout(btn_row)

        # Load current config
        ids = state.load_alarm_ids()
        self._txt_power.setText(", ".join(ids.get("power", [])))
        self._txt_down.setText(", ".join(ids.get("down", [])))

    def _save(self):
        power = [x.strip() for x in self._txt_power.text().split(",")
                 if x.strip()]
        down  = [x.strip() for x in self._txt_down.text().split(",")
                 if x.strip()]
        state.save_alarm_ids({"power": power, "down": down})
        self.saved.emit()
        self.accept()
```

**Step 2: Add gear button to sidebar**

In `_make_left_panel()`, after the brand row (around line 304, before the DIRECTORY section label), add:

```python
        btn_config = QPushButton("Configure Alarm IDs")
        btn_config.setObjectName("btn_dir")
        btn_config.clicked.connect(self._show_alarm_id_config)
        lay.addWidget(btn_config)
```

**Step 3: Add the slot**

Add to `AlarmViewer`:

```python
    def _show_alarm_id_config(self):
        dlg = AlarmIdConfigDialog(parent=self)
        dlg.saved.connect(self._reclassify_alarms)
        dlg.exec_()
```

**Step 4: Verify** — Run app, click "Configure Alarm IDs", enter some IDs, save, confirm alarms get reclassified.

**Step 5: Commit**

```
feat: add alarm ID configuration dialog with live reclassification
```

---

## Task 5: BDT Parser — bdt_parser.py

Extract structured data from BDT Excel files.

**Files:**

- Create: `alarm_app/bdt_parser.py`

**Step 1: Create bdt_parser.py**

```python
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

    # Photo count
    photo_count: int = 0

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
        # Header row is discharge_start_row + 1 (Rectifier / String headers)
        # Time labels in col A, Rec Bus Bar V in col D, A in col E
        # String #1 V in col F, A in col G, etc.
        data_row = discharge_start_row + 3  # "Before disconnecting Rectifier"

        # Start readings (Before disconnecting)
        data.start_voltage = _safe_float(cell(data_row, 4))  # col D = Rec Bus Bar V
        data.start_ampere  = _safe_float(cell(data_row, 5))  # col E = Rec Bus Bar A

        # Discharge time-series (10 min, 30 min, ... 300 min)
        time_labels = ["10 Mins", "30 Mins", "60 Mins", "90 Mins",
                       "120 Mins", "150 Mins", "180 Mins", "210 Mins",
                       "240 Mins", "270 Mins", "300 Mins"]
        last_filled_mins = 0.0
        for i, label in enumerate(time_labels):
            r = data_row + 1 + i
            v = _safe_float(cell(r, 4))
            a = _safe_float(cell(r, 5))
            data.discharge_readings.append((label, v, a))
            if v is not None or a is not None:
                # Parse minutes from label
                try:
                    last_filled_mins = float(label.split()[0])
                except ValueError:
                    pass

        data.discharge_minutes = last_filled_mins

        # End readings (After Connecting Rectifier)
        end_row = data_row + 1 + len(time_labels)
        data.end_voltage = _safe_float(cell(end_row, 4))
        data.end_ampere  = _safe_float(cell(end_row, 5))

    # Ibat before test — scan for "Ibat before starting"
    for r in range(1, ws.max_row + 1):
        v = _safe_str(cell(r, 12))  # col L
        if "ibat before" in v.lower():
            # The value is typically in the row below or same row, next col area
            # Check the row below in the same column region
            data.ibat_before_test = _safe_float(cell(r + 1, 12))
            if data.ibat_before_test is None:
                data.ibat_before_test = _safe_float(cell(r, 13))
            break

    # Photo count — check all sheets for embedded images
    total_images = 0
    for sheet_name in wb.sheetnames:
        total_images += len(wb[sheet_name]._images)
    data.photo_count = total_images

    wb.close()
    return data
```

**Step 2: Verify** — Quick smoke test from terminal:

```bash
"/Volumes/nvme 500/Alarms/alarm_app/.venv/bin/python3" -c "
from alarm_app.bdt_parser import parse_bdt_file
d = parse_bdt_file('/Volumes/nvme 500/Alarms/test_pms/BDT   PARAMOS 0483DE.xlsx')
print(f'Site: {d.site_code}, Date: {d.test_date}, Photos: {d.photo_count}')
print(f'Start V/A: {d.start_voltage}/{d.start_ampere}')
print(f'End V/A: {d.end_voltage}/{d.end_ampere}')
print(f'Discharge mins: {d.discharge_minutes}')
print(f'Ibat before: {d.ibat_before_test}')
print(f'Readings: {d.discharge_readings}')
print(f'Errors: {d.errors}')
"
```

Expected: Extracts site code "0483DE", start voltage ~53.6, photos = 0 (known empty file), discharge_minutes = 0 (this file has empty readings).

**Step 3: Fix any extraction issues** based on actual output, adjust row/col offsets if needed.

**Step 4: Commit**

```
feat: add BDT parser for extracting structured data from test files
```

---

## Task 6: BDT Validator — bdt_validator.py

Run the 7 validation rules against parsed BDT data + alarm data.

**Files:**

- Create: `alarm_app/bdt_validator.py`

**Step 1: Create bdt_validator.py**

```python
"""
BDT Validator — run validation rules against parsed BDT data.

Cross-references BDT (Battery Discharge Test) reports against loaded alarm
data to detect fraudulent or incorrect test submissions.
"""

from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from .bdt_parser import BDTData
from .constants import BDT_DEFAULT_TOLERANCE


@dataclass
class RuleResult:
    """Result of a single validation rule."""
    rule_id: str
    rule_name: str
    passed: bool | None  # None = cannot evaluate (missing data)
    verdict: str         # "Accepted", "Rejected", "Revise", "N/A"
    detail: str = ""     # Human-readable explanation


@dataclass
class ValidationResult:
    """Full validation result for one BDT file."""
    filename: str
    site_code: str
    test_date: str
    overall: str  # "Accepted", "Rejected", "Revise"
    rules: list[RuleResult] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


def validate_bdt(bdt: BDTData, alarm_df: pd.DataFrame | None,
                 tolerance: float = BDT_DEFAULT_TOLERANCE) -> ValidationResult:
    """Validate a parsed BDT file against alarm data.

    Args:
        bdt: Parsed BDT data from bdt_parser.
        alarm_df: Loaded alarm DataFrame (may be None if no alarms loaded).
        tolerance: Fractional tolerance for duration matching (0.15 = 15%).

    Returns:
        ValidationResult with per-rule verdicts and overall verdict.
    """
    result = ValidationResult(
        filename=bdt.filename,
        site_code=bdt.site_code,
        test_date=(bdt.test_date.strftime("%Y-%m-%d")
                   if bdt.test_date else "Unknown"),
        overall="Accepted",
        parse_errors=list(bdt.errors),
    )

    result.rules.append(_rule_1_photos(bdt))
    result.rules.append(_rule_2_power_alarm_match(bdt, alarm_df))
    result.rules.append(_rule_3_duration_match(bdt, alarm_df, tolerance))
    result.rules.append(_rule_4_discharge_table(bdt, tolerance))
    result.rules.append(_rule_5_start_ampere(bdt))
    result.rules.append(_rule_6_end_voltage(bdt))
    result.rules.append(_rule_7_inverse_relationship(bdt))

    # Overall verdict
    failed = [r for r in result.rules if r.verdict == "Rejected"]
    revise = [r for r in result.rules if r.verdict == "Revise"]

    if failed:
        result.overall = "Rejected"
    elif revise:
        result.overall = "Revise"
    else:
        result.overall = "Accepted"

    return result


# ── Rule implementations ──────────────────────────────────

def _rule_1_photos(bdt: BDTData) -> RuleResult:
    """R1: Photos exist in placeholders."""
    has = bdt.photo_count > 0
    return RuleResult(
        rule_id="R1", rule_name="Photos",
        passed=has,
        verdict="Accepted" if has else "Rejected",
        detail=(f"{bdt.photo_count} photo(s) found"
                if has else "No photos embedded in file"),
    )


def _rule_2_power_alarm_match(bdt: BDTData,
                               alarm_df: pd.DataFrame | None) -> RuleResult:
    """R2: Power alarm exists on test date for the same site."""
    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=None, verdict="N/A",
            detail="No alarm data loaded",
        )
    if bdt.test_date is None:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail="No test date found in BDT file",
        )

    test_date = pd.Timestamp(bdt.test_date).normalize()
    df = alarm_df
    mask = (
        (df["site_id"].astype(str).str.strip().str.upper()
         == bdt.site_code.strip().upper())
        & (df["alarm_category"] == "Power")
        & (df["occurred_on"].notna())
    )
    power = df[mask].copy()

    if power.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=f"No Power alarms found for site {bdt.site_code}",
        )

    # Check if any Power alarm occurred on the test date
    power_dates = power["occurred_on"].dt.normalize()
    match = power[power_dates == test_date]

    if match.empty:
        return RuleResult(
            rule_id="R2", rule_name="Power Alarm Match",
            passed=False, verdict="Rejected",
            detail=(f"No Power alarm on {test_date.date()} for site "
                    f"{bdt.site_code}. Power was never cut from the grid."),
        )

    return RuleResult(
        rule_id="R2", rule_name="Power Alarm Match",
        passed=True, verdict="Accepted",
        detail=f"Power alarm found on {test_date.date()} ({len(match)} match(es))",
    )


def _rule_3_duration_match(bdt: BDTData, alarm_df: pd.DataFrame | None,
                            tolerance: float) -> RuleResult:
    """R3: Test duration matches Power alarm duration."""
    if alarm_df is None or alarm_df.empty:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=None, verdict="N/A",
            detail="No alarm data loaded",
        )
    if bdt.test_date is None:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=False, verdict="Rejected",
            detail="No test date in BDT file",
        )

    test_date = pd.Timestamp(bdt.test_date).normalize()
    df = alarm_df
    mask = (
        (df["site_id"].astype(str).str.strip().str.upper()
         == bdt.site_code.strip().upper())
        & (df["alarm_category"] == "Power")
        & (df["occurred_on"].notna())
        & (df["occurred_on"].dt.normalize() == test_date)
    )
    power = df[mask]

    if power.empty:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=False, verdict="Rejected",
            detail="No matching Power alarm to compare duration",
        )

    # Get alarm duration in minutes
    alarm_dur_mins = None
    if "_duration_secs" in power.columns:
        alarm_dur_mins = power["_duration_secs"].max() / 60.0
    elif "duration" in power.columns:
        # Parse HH:MM:SS
        dur_str = power["duration"].iloc[0]
        try:
            parts = str(dur_str).split(":")
            alarm_dur_mins = (int(parts[0]) * 60 + int(parts[1])
                              + int(parts[2]) / 60.0)
        except (ValueError, IndexError):
            pass

    if alarm_dur_mins is None or alarm_dur_mins == 0:
        return RuleResult(
            rule_id="R3", rule_name="Duration Match",
            passed=None, verdict="N/A",
            detail="Cannot determine alarm duration",
        )

    bdt_mins = bdt.discharge_minutes
    diff_ratio = abs(bdt_mins - alarm_dur_mins) / alarm_dur_mins if alarm_dur_mins > 0 else 1.0

    passed = diff_ratio <= tolerance
    return RuleResult(
        rule_id="R3", rule_name="Duration Match",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"BDT: {bdt_mins:.0f} min, Alarm: {alarm_dur_mins:.0f} min "
                f"(diff: {diff_ratio*100:.0f}%, tolerance: {tolerance*100:.0f}%)"),
    )


def _rule_4_discharge_table(bdt: BDTData,
                             tolerance: float) -> RuleResult:
    """R4: Backup time matches discharge table calculation."""
    if not bdt.discharge_readings:
        return RuleResult(
            rule_id="R4", rule_name="Discharge Table Match",
            passed=None, verdict="N/A",
            detail="No discharge readings found",
        )

    # Find last reading with data
    last_mins = 0.0
    for label, v, a in bdt.discharge_readings:
        if v is not None or a is not None:
            try:
                last_mins = float(label.split()[0])
            except ValueError:
                pass

    if last_mins == 0:
        return RuleResult(
            rule_id="R4", rule_name="Discharge Table Match",
            passed=False, verdict="Revise",
            detail="Discharge table is empty — no readings recorded",
        )

    reported = bdt.discharge_minutes
    diff_ratio = (abs(reported - last_mins) / last_mins
                  if last_mins > 0 else 1.0)
    passed = diff_ratio <= tolerance

    return RuleResult(
        rule_id="R4", rule_name="Discharge Table Match",
        passed=passed,
        verdict="Accepted" if passed else "Revise",
        detail=(f"Table shows {last_mins:.0f} min of readings, "
                f"reported: {reported:.0f} min"),
    )


def _rule_5_start_ampere(bdt: BDTData) -> RuleResult:
    """R5: Ampere before test = 0."""
    if bdt.ibat_before_test is None:
        return RuleResult(
            rule_id="R5", rule_name="Start Ampere = 0",
            passed=None, verdict="N/A",
            detail="Ibat before test not found in file",
        )

    passed = bdt.ibat_before_test == 0.0
    return RuleResult(
        rule_id="R5", rule_name="Start Ampere = 0",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=f"Ibat before test: {bdt.ibat_before_test} A (expected: 0)",
    )


def _rule_6_end_voltage(bdt: BDTData) -> RuleResult:
    """R6: End voltage in 40.5–45V range."""
    if bdt.end_voltage is None:
        return RuleResult(
            rule_id="R6", rule_name="End Voltage Range",
            passed=None, verdict="N/A",
            detail="End voltage not found in file",
        )

    passed = 40.5 <= bdt.end_voltage <= 45.0
    return RuleResult(
        rule_id="R6", rule_name="End Voltage Range",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=f"End voltage: {bdt.end_voltage}V (range: 40.5–45.0V)",
    )


def _rule_7_inverse_relationship(bdt: BDTData) -> RuleResult:
    """R7: Voltage and ampere have inverse relationship throughout test."""
    voltages = [v for _, v, _ in bdt.discharge_readings if v is not None]
    amperes  = [a for _, _, a in bdt.discharge_readings if a is not None]

    if len(voltages) < 3 or len(amperes) < 3:
        return RuleResult(
            rule_id="R7", rule_name="V/A Inverse",
            passed=None, verdict="N/A",
            detail=f"Not enough readings ({len(voltages)} V, {len(amperes)} A, need 3+)",
        )

    # Use min length to align
    n = min(len(voltages), len(amperes))
    v_arr = np.array(voltages[:n])
    a_arr = np.array(amperes[:n])

    # Check correlation — should be negative (inverse)
    corr = np.corrcoef(v_arr, a_arr)[0, 1]

    if np.isnan(corr):
        return RuleResult(
            rule_id="R7", rule_name="V/A Inverse",
            passed=None, verdict="N/A",
            detail="Cannot compute correlation (constant values?)",
        )

    # Negative correlation = inverse relationship = good
    passed = corr < 0
    return RuleResult(
        rule_id="R7", rule_name="V/A Inverse",
        passed=passed,
        verdict="Accepted" if passed else "Rejected",
        detail=(f"V/A correlation: {corr:.3f} "
                f"({'inverse' if corr < 0 else 'direct'} relationship)"),
    )
```

**Step 2: Verify** — Quick smoke test:

```bash
"/Volumes/nvme 500/Alarms/alarm_app/.venv/bin/python3" -c "
from alarm_app.bdt_parser import parse_bdt_file
from alarm_app.bdt_validator import validate_bdt
d = parse_bdt_file('/Volumes/nvme 500/Alarms/test_pms/BDT   PARAMOS 0483DE.xlsx')
r = validate_bdt(d, None)
print(f'Overall: {r.overall}')
for rule in r.rules:
    print(f'  {rule.rule_id}: {rule.verdict} — {rule.detail}')
"
```

**Step 3: Commit**

```
feat: add BDT validator with 7 validation rules
```

---

## Task 7: Tab Bar + Test Validation Tab UI — viewer.py + styles.py

Restructure the right content area to use a QTabWidget, keeping the existing Alarms view as tab 1 and adding the BDT Validation tab as tab 2.

**Files:**

- Modify: `alarm_app/viewer.py`
- Modify: `alarm_app/styles.py`

**Step 1: Add imports to viewer.py**

Add to the imports at top of `viewer.py`:

```python
from PyQt5.QtWidgets import QTabWidget
```

Add to internal imports:

```python
from .bdt_parser import parse_bdt_file, BDTData
from .bdt_validator import validate_bdt, ValidationResult
```

**Step 2: Restructure \_build_ui to use tabs**

In `_build_ui()`, the current right content area builds:

- header strip
- splitter (search panel + table)

Wrap these in a tab widget. Replace the section that builds `right_wrap` (around lines 224-244):

```python
        # Right content area
        right_wrap = QWidget()
        right_wrap.setObjectName("right_wrap")
        rl = QVBoxLayout(right_wrap)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Thin top header strip
        header = self._make_header_strip()
        header.setObjectName("header")
        rl.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setObjectName("main_tabs")

        # Tab 1: Alarms (existing content)
        alarms_tab = QWidget()
        al = QVBoxLayout(alarms_tab)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._make_search_panel())
        splitter.addWidget(self._make_table())
        splitter.setSizes([130, 800])
        al.addWidget(splitter, 1)
        self._tabs.addTab(alarms_tab, "Alarms")

        # Tab 2: Test Validation
        validation_tab = self._make_validation_tab()
        self._tabs.addTab(validation_tab, "Test Validation")

        rl.addWidget(self._tabs, 1)
        main.addWidget(right_wrap, 1)
```

(Remove the old splitter + `rl.addWidget(splitter, 1)` and `rl.addWidget(right_wrap, 1)` lines that this replaces.)

**Step 3: Build the validation tab**

Add this method to `AlarmViewer`:

```python
    def _make_validation_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8)

        # ── Top bar ──────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(10)

        self._bdt_dir_edit = QLineEdit()
        self._bdt_dir_edit.setPlaceholderText("BDT files directory…")
        top.addWidget(self._bdt_dir_edit, 1)

        btn_bdt_browse = QPushButton("Browse")
        btn_bdt_browse.setObjectName("btn_dir")
        btn_bdt_browse.clicked.connect(self._browse_bdt)
        top.addWidget(btn_bdt_browse)

        btn_validate = QPushButton("Validate")
        btn_validate.setObjectName("btn_search")
        btn_validate.clicked.connect(self._run_validation)
        top.addWidget(btn_validate)

        top.addWidget(self._vline())

        lbl_tol = QLabel("Tolerance")
        lbl_tol.setStyleSheet(
            "color:#7f849c; font-size:12px; background:transparent;")
        top.addWidget(lbl_tol)

        self._spn_tolerance = QSpinBox()
        self._spn_tolerance.setRange(10, 20)
        self._spn_tolerance.setValue(15)
        self._spn_tolerance.setSuffix("%")
        self._spn_tolerance.setFixedWidth(70)
        top.addWidget(self._spn_tolerance)

        lay.addLayout(top)

        # ── Results table ────────────────────────────────
        from .constants import BDT_RESULT_HEADERS, BDT_RESULT_WIDTHS
        cols = BDT_RESULT_HEADERS
        self._bdt_table = QTableWidget(0, len(cols))
        self._bdt_table.setHorizontalHeaderLabels(cols)
        self._bdt_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._bdt_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._bdt_table.setAlternatingRowColors(True)
        self._bdt_table.verticalHeader().setVisible(False)
        self._bdt_table.verticalHeader().setDefaultSectionSize(28)
        hdr = self._bdt_table.horizontalHeader()
        for i, col in enumerate(cols):
            hdr.resizeSection(i, BDT_RESULT_WIDTHS.get(col, 80))
        hdr.setStretchLastSection(True)
        self._bdt_table.clicked.connect(self._on_bdt_row_clicked)
        lay.addWidget(self._bdt_table, 1)

        # ── Detail label (shows on row click) ────────────
        self._bdt_detail = QLabel("")
        self._bdt_detail.setStyleSheet(
            "color:#6c7086; font-size:11px; background:#0a0a14; "
            "border:1px solid #1e1e2e; border-radius:6px; padding:8px;")
        self._bdt_detail.setWordWrap(True)
        self._bdt_detail.setMinimumHeight(60)
        lay.addWidget(self._bdt_detail)

        # ── Bottom bar ───────────────────────────────────
        bot = QHBoxLayout()
        self._bdt_summary = QLabel("")
        self._bdt_summary.setStyleSheet(
            "color:#6c7086; font-size:12px; background:transparent;")
        bot.addWidget(self._bdt_summary)
        bot.addStretch()

        btn_export = QPushButton("Export Results XLSX")
        btn_export.setObjectName("btn_export")
        btn_export.clicked.connect(self._export_bdt_results)
        bot.addWidget(btn_export)

        lay.addLayout(bot)

        # Store validation results for detail view & export
        self._bdt_results: list[ValidationResult] = []

        return w
```

**Step 4: Add validation slots**

Add these methods to `AlarmViewer`:

```python
    # ── BDT validation slots ─────────────────────────────────
    def _browse_bdt(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select BDT Files Directory",
            self._bdt_dir_edit.text() or str(Path.home()))
        if d:
            self._bdt_dir_edit.setText(d)

    def _run_validation(self):
        directory = self._bdt_dir_edit.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(
                self, "No Directory", "Select a valid BDT files directory.")
            return

        # Find xlsx files
        bdt_files = []
        for f in os.listdir(directory):
            if f.lower().endswith(".xlsx") and not f.startswith("~$"):
                bdt_files.append(os.path.join(directory, f))

        if not bdt_files:
            QMessageBox.information(
                self, "No Files", "No .xlsx files found in directory.")
            return

        alarm_df = self._full_df if not self._full_df.empty else None
        tolerance = self._spn_tolerance.value() / 100.0

        self._sbar.showMessage(f"Validating {len(bdt_files)} BDT file(s)…")
        self._bdt_results = []

        for fp in sorted(bdt_files):
            bdt_data = parse_bdt_file(fp)
            result = validate_bdt(bdt_data, alarm_df, tolerance)
            self._bdt_results.append(result)

        self._populate_bdt_table()
        self._sbar.showMessage(
            f"Validated {len(self._bdt_results)} BDT file(s)")

    def _populate_bdt_table(self):
        from .constants import BDT_RESULT_HEADERS
        results = self._bdt_results
        self._bdt_table.setRowCount(len(results))

        colors = {
            "Accepted": QColor("#a6e3a1"),
            "Rejected": QColor("#f38ba8"),
            "Revise":   QColor("#fab387"),
            "N/A":      QColor("#45475a"),
        }

        for r, res in enumerate(results):
            vals = [
                res.filename, res.site_code, res.test_date, res.overall,
            ] + [rule.verdict for rule in res.rules]

            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                # Color the verdict and rule columns
                if c >= 3:  # Verdict + R1-R7 columns
                    item.setForeground(colors.get(val, QColor("#cdd6f4")))
                self._bdt_table.setItem(r, c, item)

        # Summary
        n_acc = sum(1 for r in results if r.overall == "Accepted")
        n_rej = sum(1 for r in results if r.overall == "Rejected")
        n_rev = sum(1 for r in results if r.overall == "Revise")
        self._bdt_summary.setText(
            f"<span style='color:#a6e3a1;'>{n_acc} Accepted</span>"
            f"  |  <span style='color:#f38ba8;'>{n_rej} Rejected</span>"
            f"  |  <span style='color:#fab387;'>{n_rev} Revise</span>")

    def _on_bdt_row_clicked(self, index):
        row = index.row()
        if row >= len(self._bdt_results):
            return
        res = self._bdt_results[row]
        lines = [f"<b>{res.filename}</b>  —  Site: {res.site_code}"]
        for rule in res.rules:
            color = {"Accepted": "#a6e3a1", "Rejected": "#f38ba8",
                     "Revise": "#fab387", "N/A": "#45475a"}.get(
                         rule.verdict, "#cdd6f4")
            lines.append(
                f"<span style='color:{color};'>[{rule.verdict}]</span> "
                f"<b>{rule.rule_id}</b> {rule.rule_name}: {rule.detail}")
        if res.parse_errors:
            lines.append(
                f"<span style='color:#f38ba8;'>Parse errors: "
                f"{'; '.join(res.parse_errors)}</span>")
        self._bdt_detail.setText("<br>".join(lines))

    def _export_bdt_results(self):
        if not self._bdt_results:
            QMessageBox.information(
                self, "Nothing to Export", "Run validation first.")
            return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Validation Results",
            f"bdt_validation_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            "Excel Files (*.xlsx)")
        if not fp:
            return
        rows = []
        for res in self._bdt_results:
            row = {
                "File": res.filename,
                "Site Code": res.site_code,
                "Test Date": res.test_date,
                "Verdict": res.overall,
            }
            for rule in res.rules:
                row[rule.rule_id] = rule.verdict
                row[f"{rule.rule_id} Detail"] = rule.detail
            rows.append(row)
        pd.DataFrame(rows).to_excel(fp, index=False, engine="openpyxl")
        QMessageBox.information(
            self, "Export OK", f"Saved to:\n{fp}")
```

**Step 5: Add QSS for the tab widget to styles.py**

Append to the STYLE string in `alarm_app/styles.py` (before the final `"""`):

```css
/* ── Tab widget ────────────────────────────────────────── */
QTabWidget::pane {
  border: none;
  background: #13131f;
}
QTabBar::tab {
  background: #1a1a2a;
  color: #6c7086;
  border: 1px solid #2a2a3e;
  border-bottom: none;
  border-top-left-radius: 6px;
  border-top-right-radius: 6px;
  padding: 8px 20px;
  margin-right: 2px;
  font-size: 12px;
  font-weight: 600;
}
QTabBar::tab:selected {
  background: #13131f;
  color: #89b4fa;
  border-color: #2a2a3e;
}
QTabBar::tab:hover:!selected {
  background: #1e1e30;
  color: #cdd6f4;
}
```

**Step 6: Verify** — Run the app. Confirm two tabs appear. Switch to "Test Validation", browse to test_pms folder, click Validate. Verify results appear with color-coded verdicts. Click a row to see details.

**Step 7: Commit**

```
feat: add Test Validation tab with BDT file validation UI
```

---

## Task 8: Clean Up Dead Code

Remove the dead code identified in the earlier analysis.

**Files:**

- Modify: `alarm_app/constants.py`
- Modify: `alarm_app/styles.py`

**Step 1: Remove dead SCHEMA_1_MAP entries from constants.py**

Remove these two lines from `SCHEMA_1_MAP`:

```python
    "Cleared By":             "cleared_by",
    "Alarm Reporting Type":   "reporting_type",
```

**Step 2: Remove orphaned QSS selector from styles.py**

Remove the `QLabel#lbl_record_count` block (lines 367-370):

```css
QLabel#lbl_record_count {
  color: #45475a;
  font-size: 11px;
}
```

**Step 3: Commit**

```
chore: remove dead schema mappings and orphaned QSS selector
```

---

## Summary

| Task | What                                 | Files                       |
| ---- | ------------------------------------ | --------------------------- |
| 1    | Alarm ID config + BDT constants      | `state.py`, `constants.py`  |
| 2    | Replace filename category detection  | `parsers.py`                |
| 3    | Wire classification into viewer      | `viewer.py`                 |
| 4    | Alarm ID config dialog               | `viewer.py`                 |
| 5    | BDT parser                           | `bdt_parser.py` (new)       |
| 6    | BDT validator                        | `bdt_validator.py` (new)    |
| 7    | Tab bar + validation tab UI + styles | `viewer.py`, `styles.py`    |
| 8    | Clean up dead code                   | `constants.py`, `styles.py` |
