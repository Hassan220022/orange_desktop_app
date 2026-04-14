# Alarm App Codebase Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure alarm_app from a flat 15-file layout with a 3,355-line god class into a layered package with core/, data/, bdt/, and ui/ subpackages.

**Architecture:** Three layers with one directional rule: core/ and data/ never import from ui/. core/ is pure Python (no Qt, no I/O). data/ handles persistence and file I/O. ui/ owns all PyQt code and imports from the other layers. bdt/ is a self-contained subsystem.

**Tech Stack:** Python 3.14, PyQt5, pandas, openpyxl, numpy. Tests: pytest (321 passing baseline).

**Test command:** `/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q`

**Constraints:**

- 321 tests must pass after every task
- styles.py is never modified
- AlarmTableModel's 2D cache pattern is preserved
- User-visible behavior stays identical
- PyInstaller fallback imports in main.py must keep working

---

## Target Layout

```
alarm_app/
├── __init__.py
├── main.py                    # entry point (update imports)
├── constants.py               # stays
├── styles.py                  # untouched
│
├── core/                      # pure Python — no Qt, no I/O
│   ├── __init__.py
│   ├── filters.py             # compute_date_mask, _parse_manual_days
│   ├── backup_time.py         # compute_backup_times, _fmt_td
│   ├── duration.py            # _duration_to_secs, _secs_to_hhmmss
│   └── classify.py            # classify_by_alarm_id, compute_site_down_flag
│
├── data/                      # I/O — no UI
│   ├── __init__.py
│   ├── loaders.py             # discover_alarm_files, parse_alarm_file, dedup, schema detection
│   ├── state.py               # all of current state.py
│   ├── sync.py                # all of current sync_worker.py
│   └── site_report.py         # all of current site_report.py
│
├── bdt/                       # self-contained subsystem
│   ├── __init__.py
│   ├── parser.py              # all of current bdt_parser.py
│   ├── validator.py           # all of current bdt_validator.py
│   ├── export.py              # all of current bdt_export.py
│   └── history.py             # all of current bdt_history.py
│
└── ui/                        # PyQt — imports core/, data/, bdt/
    ├── __init__.py
    ├── viewer.py              # AlarmViewer (slimmed to ~800-1200 lines wiring)
    ├── model.py               # AlarmTableModel from models.py
    ├── threads.py             # LoaderThread, ExportThread, BDTValidationThread, BackupTimeThread, RestoreThread
    ├── dialogs.py             # ColumnFilterPopup, DailyReviewReportDialog, AlarmIdConfigDialog, BackupTimeDialog
    └── panels/
        ├── __init__.py
        ├── search_panel.py    # from _make_search_panel (346 lines)
        ├── bdt_validation_panel.py  # from _make_validation_tab + BDT table methods
        ├── bdt_detail_panel.py      # from _make_bdt_detail_panel + photos + populate
        └── left_panel.py            # from _make_left_panel
```

## Compatibility Shim Strategy

Each moved module gets a one-line re-export shim at the old location during its task. This keeps existing imports working until all consumers are updated. Example:

```python
# old bdt_parser.py becomes:
from alarm_app.bdt.parser import *  # noqa: F401,F403 — compatibility shim
```

Shims are removed in the final cleanup task once all imports point to new locations.

---

## Task 1: Create package skeleton

**Files:**

- Create: `core/__init__.py`, `data/__init__.py`, `bdt/__init__.py`, `ui/__init__.py`, `ui/panels/__init__.py`

- [ ] **Step 1: Create directories and empty **init**.py files**

```bash
cd /Users/mikawi/Developer/orange/alarm_app
mkdir -p core data bdt ui/panels
touch core/__init__.py data/__init__.py bdt/__init__.py ui/__init__.py ui/panels/__init__.py
```

- [ ] **Step 2: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q
```

Expected: 321 passed

- [ ] **Step 3: Commit**

```bash
git add core/ data/ bdt/ ui/
git commit -m "chore: create package skeleton for core/, data/, bdt/, ui/"
```

---

## Task 2: Move BDT subsystem to bdt/

**Files:**

- Move: `bdt_parser.py` → `bdt/parser.py`
- Move: `bdt_validator.py` → `bdt/validator.py`
- Move: `bdt_export.py` → `bdt/export.py`
- Move: `bdt_history.py` → `bdt/history.py`
- Create: shims at old locations
- Modify: `bdt/validator.py` internal import (`.bdt_parser` → `.parser`)
- Modify: `bdt/export.py` internal import (`.constants` → `..constants`)
- Modify: `bdt/history.py` internal import (`.constants` → `..constants`)
- Modify: `bdt/__init__.py` — re-export public names

- [ ] **Step 1: Move files**

```bash
cd /Users/mikawi/Developer/orange/alarm_app
git mv bdt_parser.py bdt/parser.py
git mv bdt_validator.py bdt/validator.py
git mv bdt_export.py bdt/export.py
git mv bdt_history.py bdt/history.py
```

- [ ] **Step 2: Fix internal imports in moved files**

`bdt/validator.py` line 7 — change:

```python
# old
from .bdt_parser import BDTData
# new
from .parser import BDTData
```

Also fix any try/except ImportError fallbacks to reference the new location.

`bdt/export.py` — change:

```python
# old
from .constants import ...
# new
from ..constants import ...
```

`bdt/history.py` — change:

```python
# old
from .constants import APP_VERSION
# new
from ..constants import APP_VERSION
```

`bdt/parser.py` — no local imports to fix (standalone).

- [ ] **Step 3: Write re-export shims at old locations**

Create `bdt_parser.py`:

```python
from alarm_app.bdt.parser import *  # noqa: F401,F403
```

Create `bdt_validator.py`:

```python
from alarm_app.bdt.validator import *  # noqa: F401,F403
```

Create `bdt_export.py`:

```python
from alarm_app.bdt.export import *  # noqa: F401,F403
```

Create `bdt_history.py`:

```python
from alarm_app.bdt.history import *  # noqa: F401,F403
```

- [ ] **Step 4: Update bdt/**init**.py with public re-exports**

```python
from .parser import BDTData, PhotoSlot, parse_bdt_file, load_bdt_photos
from .validator import ValidationResult, RuleResult, validate_bdt
from .export import build_bdt_export_sheets, build_pm_summary_rows
from .history import (
    BDTTestRecord, BDTComparison,
    save_test_record, load_previous_test, compare_tests,
    save_validation_run, compute_alarm_input_sha256,
    HISTORY_DIR, PM_RUNS_DIR, PM_RULE_RESULTS_DIR,
)
```

- [ ] **Step 5: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q
```

Expected: 321 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: move BDT subsystem into bdt/ subpackage"
```

---

## Task 3: Move data layer to data/

**Files:**

- Move: `state.py` → `data/state.py`
- Move: `sync_worker.py` → `data/sync.py`
- Move: `site_report.py` → `data/site_report.py`
- Create: shims at old locations
- Modify: `data/sync.py` internal import (`.state` → `.state`)

- [ ] **Step 1: Move files**

```bash
cd /Users/mikawi/Developer/orange/alarm_app
git mv state.py data/state.py
git mv sync_worker.py data/sync.py
git mv site_report.py data/site_report.py
```

- [ ] **Step 2: Fix internal imports in moved files**

`data/sync.py` — change:

```python
# old
from .state import ...
# or try/except
from state import ...
# new (relative within data/)
from .state import ...
```

`data/state.py` — no local imports (standalone).

`data/site_report.py` — no local imports (standalone).

- [ ] **Step 3: Write re-export shims at old locations**

Create `state.py`:

```python
from alarm_app.data.state import *  # noqa: F401,F403
```

Create `sync_worker.py`:

```python
from alarm_app.data.sync import *  # noqa: F401,F403
```

Create `site_report.py`:

```python
from alarm_app.data.site_report import *  # noqa: F401,F403
```

- [ ] **Step 4: Update data/**init**.py with public re-exports**

```python
from .state import (
    STATE_DIR, STATE_FILE, CACHE_FILE,
    save_state, load_state,
    save_dataframe, load_dataframe,
    clear_cache, load_feature_flags,
    save_alarm_ids, load_alarm_ids,
    append_review_event, load_review_events, summarize_review_events_by_day,
    compute_file_hashes, files_changed,
    get_or_create_device_id,
    append_outbox_event, load_pending_outbox,
    save_sync_checkpoint, load_sync_checkpoint,
    mark_outbox_synced,
)
from .sync import LocalSyncWorker, TransientSyncError, compute_batch_idempotency_key
from .site_report import (
    normalize_site_key, infer_site_id_column, read_site_sheet,
    build_site_alarm_report, collect_site_sheet_keys,
    filter_site_sheet_to_matching_sites,
)
```

- [ ] **Step 5: Run tests**

Expected: 321 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: move data layer into data/ subpackage"
```

---

## Task 4: Extract core/duration.py from parsers.py

**Files:**

- Create: `core/duration.py`
- Modify: `parsers.py` — remove `_duration_to_secs()` (lines 511-530) and `_secs_to_hhmmss()` (lines 533-540), add import from core.duration
- Test: `tests/test_parsers.py` — update imports for TestDurationToSecs, TestSecsToHhmmss

- [ ] **Step 1: Create core/duration.py**

Extract `_duration_to_secs()` and `_secs_to_hhmmss()` from parsers.py. These are pure functions: string in, number out (and vice versa). No dependencies.

Make them public (drop underscore prefix): `duration_to_secs()`, `secs_to_hhmmss()`.

```python
"""Duration string ↔ seconds conversion."""


def duration_to_secs(val: object) -> float:
    """Convert HH:MM:SS or seconds-as-string to float seconds.

    Returns NaN for unparseable values.
    """
    # copy the body of _duration_to_secs from parsers.py lines 511-530


def secs_to_hhmmss(total: float) -> str:
    """Format seconds as HH:MM:SS string."""
    # copy the body of _secs_to_hhmmss from parsers.py lines 533-540
```

- [ ] **Step 2: Update parsers.py**

Remove the two functions. Add import at top:

```python
from .core.duration import duration_to_secs as _duration_to_secs
from .core.duration import secs_to_hhmmss as _secs_to_hhmmss
```

This preserves internal references to `_duration_to_secs` and `_secs_to_hhmmss` without changing any call sites within parsers.py.

- [ ] **Step 3: Update tests/test_parsers.py**

`TestDurationToSecs` (lines 324-364) and `TestSecsToHhmmss` (lines 366-393) import from parsers. Update them to import from `alarm_app.core.duration` directly, using the new public names.

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add core/duration.py parsers.py tests/test_parsers.py
git commit -m "refactor: extract duration helpers into core/duration.py"
```

---

## Task 5: Extract core/backup_time.py from backup_time.py

**Files:**

- Create: `core/backup_time.py`
- Modify: `backup_time.py` — remove `compute_backup_times()` and `_fmt_td()`, import from core
- Test: `tests/test_backup_time.py` — update import

- [ ] **Step 1: Create core/backup_time.py**

Extract `compute_backup_times()` (lines 27-99) and `_fmt_td()` (lines 102-106) from backup_time.py. These are pure pandas functions. Only dependency: `pandas`, `datetime`.

```python
"""Backup-time computation — pure DataFrame logic, no Qt."""

import pandas as pd
from datetime import datetime


def compute_backup_times(df: pd.DataFrame) -> pd.DataFrame:
    # copy body from backup_time.py lines 27-99


def fmt_td(td) -> str:
    # copy body from backup_time.py lines 102-106
```

- [ ] **Step 2: Update backup_time.py**

Remove the two functions. Add import:

```python
from .core.backup_time import compute_backup_times, fmt_td as _fmt_td
```

All existing references within backup_time.py continue to work.

- [ ] **Step 3: Update tests/test_backup_time.py**

Change import from `from alarm_app.backup_time import compute_backup_times` to `from alarm_app.core.backup_time import compute_backup_times`.

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add core/backup_time.py backup_time.py tests/test_backup_time.py
git commit -m "refactor: extract backup time computation into core/backup_time.py"
```

---

## Task 6: Extract core/filters.py from viewer.py

**Files:**

- Create: `core/filters.py`
- Modify: `viewer.py` — remove `compute_date_mask()` (lines 65-126) and `_parse_manual_days()` (lines 3109-3120), import from core
- Test: `tests/test_date_filters.py` — update imports

- [ ] **Step 1: Create core/filters.py**

Extract `compute_date_mask()` (viewer.py lines 65-126) and `_parse_manual_days()` (viewer.py lines 3109-3120). Both are pure functions: DataFrame/Series in, mask/set out. No Qt.

```python
"""Date and filter computation — pure Python, no Qt."""

import re
from datetime import datetime
import pandas as pd


def compute_date_mask(
    occurred: pd.Series,
    range_active: bool,
    from_dt: datetime | None,
    to_dt: datetime | None,
    days_active: bool,
    specific_days: set,
) -> pd.Series | None:
    # copy body from viewer.py lines 65-126


def parse_manual_days(text: str) -> tuple[set, list[str]]:
    """Parse comma/space-separated date strings into a set of dates.
    Returns (valid_days_set, list_of_invalid_tokens).
    """
    # copy body from viewer.py lines 3109-3120
```

Note: `_parse_manual_days` becomes public `parse_manual_days` since it's now in its own module.

- [ ] **Step 2: Update viewer.py**

Remove `compute_date_mask()` function (lines 65-126).
Remove `_parse_manual_days()` method (lines 3109-3120).

Add import at top of viewer.py:

```python
from .core.filters import compute_date_mask, parse_manual_days
```

Replace `self._parse_manual_days(text)` calls with `parse_manual_days(text)`.

- [ ] **Step 3: Update tests/test_date_filters.py**

Change imports:

```python
# old
from alarm_app.viewer import compute_date_mask
# AlarmViewer._parse_manual_days was accessed via class

# new
from alarm_app.core.filters import compute_date_mask, parse_manual_days
```

Update TestParseManualDays to call `parse_manual_days()` directly instead of through AlarmViewer.

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add core/filters.py viewer.py tests/test_date_filters.py
git commit -m "refactor: extract date filter logic into core/filters.py"
```

---

## Task 7: Extract core/classify.py from parsers.py

**Files:**

- Create: `core/classify.py`
- Modify: `parsers.py` — remove `classify_by_alarm_id()` (lines 431-461) and `compute_site_down_flag()` (lines 464-505), import from core
- Test: `tests/test_parsers.py` — update imports for TestClassifyByAlarmId, TestComputeSiteDownFlag

- [ ] **Step 1: Create core/classify.py**

Extract `classify_by_alarm_id()` and `compute_site_down_flag()`. Both are pure DataFrame transforms.

```python
"""Alarm classification and site-down flag computation."""

import pandas as pd


def classify_by_alarm_id(df: pd.DataFrame, power_ids: list, down_ids: list, door_ids: list | None = None) -> pd.DataFrame:
    # copy body from parsers.py lines 431-461


def compute_site_down_flag(df: pd.DataFrame) -> pd.DataFrame:
    # copy body from parsers.py lines 464-505
```

- [ ] **Step 2: Update parsers.py**

Remove both functions. Add import:

```python
from .core.classify import classify_by_alarm_id, compute_site_down_flag
```

- [ ] **Step 3: Update tests/test_parsers.py**

Update `TestClassifyByAlarmId` (lines 514-604) and `TestComputeSiteDownFlag` (lines 606-790) to import from `alarm_app.core.classify`.

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add core/classify.py parsers.py tests/test_parsers.py
git commit -m "refactor: extract alarm classification into core/classify.py"
```

---

## Task 8: Move models.py to ui/model.py

**Files:**

- Move: `models.py` → `ui/model.py`
- Create: shim at `models.py`
- Modify: `ui/model.py` internal import

- [ ] **Step 1: Move file**

```bash
git mv models.py ui/model.py
```

- [ ] **Step 2: Fix internal import**

`ui/model.py` — change:

```python
# old
from .constants import DISPLAY_COLUMNS
# new
from ..constants import DISPLAY_COLUMNS
```

- [ ] **Step 3: Write shim at old location**

Create `models.py`:

```python
from alarm_app.ui.model import *  # noqa: F401,F403
```

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move AlarmTableModel to ui/model.py"
```

---

## Task 9: Extract ui/threads.py from parsers.py and backup_time.py

**Files:**

- Create: `ui/threads.py`
- Modify: `parsers.py` — remove LoaderThread (596-733), ExportThread (739-772), BDTValidationThread (775-915)
- Modify: `backup_time.py` — remove BackupTimeThread (243-266)
- Modify: `viewer.py` — remove RestoreThread (276-287), import from ui.threads
- Create: shim updates at old locations if needed

- [ ] **Step 1: Create ui/threads.py**

Collect all QThread subclasses into one file:

```python
"""Background worker threads — all QThread subclasses."""

import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

from ..constants import SCHEMA_1_MAP, SCHEMA_2_MAP, ALL_INTERNAL_COLS
from ..core.duration import duration_to_secs
from ..core.backup_time import compute_backup_times
from ..data import state
from ..bdt.parser import parse_bdt_file, load_bdt_photos
from ..bdt.validator import validate_bdt
from ..bdt.history import save_test_record, save_validation_run


class RestoreThread(QThread):
    # copy from viewer.py lines 276-287


class LoaderThread(QThread):
    # copy from parsers.py lines 596-733
    # update internal references to use new imports


class ExportThread(QThread):
    # copy from parsers.py lines 739-772


class BDTValidationThread(QThread):
    # copy from parsers.py lines 775-915
    # update internal references to use new imports


class BackupTimeThread(QThread):
    # copy from backup_time.py lines 243-266
    # update to import compute_backup_times from core
```

- [ ] **Step 2: Update parsers.py**

Remove LoaderThread, ExportThread, BDTValidationThread classes. The parsers.py shim (or the file itself if shims are still active) should re-export from ui.threads for backwards compat:

```python
from alarm_app.ui.threads import LoaderThread, ExportThread, BDTValidationThread  # noqa: F401
```

- [ ] **Step 3: Update backup_time.py**

Remove BackupTimeThread class. Add re-export:

```python
from alarm_app.ui.threads import BackupTimeThread  # noqa: F401
```

- [ ] **Step 4: Update viewer.py**

Remove RestoreThread class (lines 276-287). Add import:

```python
from .ui.threads import RestoreThread, LoaderThread, ExportThread, BDTValidationThread, BackupTimeThread
```

Or if viewer.py is already inside ui/:

```python
from .threads import RestoreThread, LoaderThread, ExportThread, BDTValidationThread, BackupTimeThread
```

Note: viewer.py has NOT been moved to ui/ yet at this point. It stays at root. So use:

```python
from alarm_app.ui.threads import RestoreThread
```

- [ ] **Step 5: Run tests**

Expected: 321 passed. The BDTValidationThread tests in test_parsers.py should still work via the parsers.py shim.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: consolidate all QThread workers into ui/threads.py"
```

---

## Task 10: Extract ui/dialogs.py from viewer.py and backup_time.py

**Files:**

- Create: `ui/dialogs.py`
- Modify: `viewer.py` — remove ColumnFilterPopup (128-274), DailyReviewReportDialog (289-351), AlarmIdConfigDialog (353-442)
- Modify: `backup_time.py` — remove BackupTimeDialog (112-237)

- [ ] **Step 1: Create ui/dialogs.py**

Move all QDialog subclasses that are NOT the main window:

```python
"""Standalone dialog windows."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget,
    QListWidgetItem, QCheckBox, QLineEdit, QFileDialog, QComboBox,
    QGroupBox, QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from ..constants import BT_HEADERS, BT_WIDTHS
from ..data.state import load_alarm_ids, save_alarm_ids, summarize_review_events_by_day


class ColumnFilterPopup(QDialog):
    # copy from viewer.py lines 128-274


class DailyReviewReportDialog(QDialog):
    # copy from viewer.py lines 289-351


class AlarmIdConfigDialog(QDialog):
    # copy from viewer.py lines 353-442


class BackupTimeDialog(QDialog):
    # copy from backup_time.py lines 112-237
    # update _fmt_td import: from ..core.backup_time import fmt_td
```

- [ ] **Step 2: Update viewer.py**

Remove the three dialog classes. Add import:

```python
from alarm_app.ui.dialogs import ColumnFilterPopup, DailyReviewReportDialog, AlarmIdConfigDialog
```

- [ ] **Step 3: Update backup_time.py**

Remove BackupTimeDialog. Add re-export:

```python
from alarm_app.ui.dialogs import BackupTimeDialog  # noqa: F401
```

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: extract dialog classes into ui/dialogs.py"
```

---

## Task 11: Move parsers.py remainder to data/loaders.py

After tasks 4, 7, and 9, parsers.py has had its pure functions and threads removed. What remains: file discovery, file parsing, schema detection, deduplication, summary helpers.

**Files:**

- Move: remaining parsers.py → `data/loaders.py`
- Update: parsers.py becomes shim-only

- [ ] **Step 1: Move remaining content to data/loaders.py**

Copy the remaining functions from parsers.py into data/loaders.py. Update imports:

- `from ..constants import ...` (up one level now)
- `from .state import ...` (same package)
- `from ..core.duration import duration_to_secs` (was inline before)
- `from ..core.classify import classify_by_alarm_id, compute_site_down_flag`
- `from ..bdt.parser import parse_bdt_file, load_bdt_photos`
- `from ..bdt.validator import validate_bdt`
- `from ..bdt.history import save_test_record, save_validation_run`

Functions remaining in this file:

- `_is_alarm_header()`, `_quick_header_check()`
- `_normalize_summary_key()`, `_summary_text()`, `_summary_date_key()`, `_summary_site_key()`
- `_summary_candidate_files()`, `_extract_summary_rows()`, `_load_external_summary_lookup()`, `_match_external_summary_row()`
- `discover_alarm_files()`, `parse_alarm_file()`
- `_canonical_hash_value()`, `_row_sha256()`, `deduplicate_alarm_rows()`
- Module constants: `_EXTS`, `_ENCODINGS`, `_SCHEMA_KEYS_*`, `_MIN_MATCH`, `_ALARM_NAME_HINTS`, summary constants, `_ROW_HASH_COLUMNS`

- [ ] **Step 2: Replace parsers.py with comprehensive shim**

```python
# Compatibility shim — real code is in data.loaders and ui.threads
from alarm_app.data.loaders import *  # noqa: F401,F403
from alarm_app.ui.threads import LoaderThread, ExportThread, BDTValidationThread  # noqa: F401
```

- [ ] **Step 3: Run tests**

Expected: 321 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: move file loading into data/loaders.py"
```

---

## Task 12: Move viewer.py to ui/viewer.py and backup_time.py to ui/backup_time_dialog.py

At this point viewer.py has had dialogs and RestoreThread removed but still contains AlarmViewer (the big class). Move the whole file into ui/ and fix imports.

**Files:**

- Move: `viewer.py` → `ui/viewer.py`
- Move: `backup_time.py` → `ui/backup_time_dialog.py`
- Create: shims at old locations
- Update: `main.py` imports

- [ ] **Step 1: Move viewer.py**

```bash
git mv viewer.py ui/viewer.py
```

- [ ] **Step 2: Fix all imports in ui/viewer.py**

All imports change from flat siblings to package-relative:

```python
# old
from .constants import ...
from .styles import STYLE
from .core.filters import ...
# etc.

# new
from ..constants import ...
from ..styles import STYLE
from ..core.filters import compute_date_mask, parse_manual_days
from ..data.state import ...
from ..data.site_report import ...
from ..bdt.parser import ...
from ..bdt.export import ...
from .model import AlarmTableModel
from .threads import LoaderThread, ExportThread, BDTValidationThread, BackupTimeThread, RestoreThread
from .dialogs import ColumnFilterPopup, DailyReviewReportDialog, AlarmIdConfigDialog, BackupTimeDialog
```

- [ ] **Step 3: Move backup_time.py**

```bash
git mv backup_time.py ui/backup_time_dialog.py
```

What remains in this file is just re-exports pointing to core/backup_time.py and ui/dialogs.py and ui/threads.py. Simplify it or just keep it as the home for BackupTimeDialog if preferred.

- [ ] **Step 4: Write shims at old locations**

Create `viewer.py`:

```python
from alarm_app.ui.viewer import *  # noqa: F401,F403
```

Create `backup_time.py`:

```python
from alarm_app.core.backup_time import compute_backup_times, fmt_td  # noqa: F401
from alarm_app.ui.dialogs import BackupTimeDialog  # noqa: F401
from alarm_app.ui.threads import BackupTimeThread  # noqa: F401
```

- [ ] **Step 5: Update main.py**

```python
try:
    from .constants import APP_NAME, APP_VERSION
    from .ui.viewer import AlarmViewer
except ImportError:
    from constants import APP_NAME, APP_VERSION
    from ui.viewer import AlarmViewer  # PyInstaller fallback
```

- [ ] **Step 6: Run tests**

Expected: 321 passed

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: move viewer and backup_time dialog into ui/"
```

---

## Task 13: Extract ui/panels/search_panel.py from AlarmViewer

This is the first panel extraction. `_make_search_panel` is 346 lines (viewer.py:1153-1498) and builds the entire command-console-style filter panel.

**Files:**

- Create: `ui/panels/search_panel.py`
- Modify: `ui/viewer.py` — remove `_make_search_panel`, import SearchPanel

- [ ] **Step 1: Create ui/panels/search_panel.py**

Create a `SearchPanel(QWidget)` class that:

- Receives a reference to `AlarmViewer` (or a typed protocol with the signals/state it needs)
- Contains all the widgets currently built by `_make_search_panel`
- Exposes the same widget references (`_txt_search`, `_chk_date_filter`, `_date_from`, `_date_to`, etc.) that AlarmViewer currently accesses

```python
"""Search/filter panel — command console layout."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, ...
from PyQt5.QtCore import Qt, QDate, pyqtSignal


class SearchPanel(QWidget):
    """Filter panel containing all search controls."""

    # Signals that the viewer connects to
    search_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    date_filter_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        # move body of _make_search_panel here
        # all self._widget references become self.widget references
        # the panel builds and owns its own widgets
```

- [ ] **Step 2: Update ui/viewer.py**

In `_build_ui()`, replace:

```python
search_panel = self._make_search_panel()
```

with:

```python
from .panels.search_panel import SearchPanel
self._search_panel = SearchPanel(self)
search_panel = self._search_panel
```

Wire signals from the panel to AlarmViewer slots.

Update all `self._txt_search`, `self._chk_date_filter`, etc. references to go through `self._search_panel.*` instead. This is the most mechanical part — find-and-replace across AlarmViewer methods.

- [ ] **Step 3: Delete \_make_search_panel method from AlarmViewer**

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: extract SearchPanel from AlarmViewer"
```

---

## Task 14: Extract ui/panels/left_panel.py from AlarmViewer

**Files:**

- Create: `ui/panels/left_panel.py`
- Modify: `ui/viewer.py` — remove `_make_left_panel` (lines 1071-1150)

- [ ] **Step 1: Create LeftPanel(QWidget)**

Extract `_make_left_panel` (80 lines). This panel contains the directory browser, file list, and load/scan controls.

- [ ] **Step 2: Update ui/viewer.py**

Replace `self._make_left_panel()` call with `LeftPanel(self)`. Wire signals.

- [ ] **Step 3: Run tests**

Expected: 321 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: extract LeftPanel from AlarmViewer"
```

---

## Task 15: Extract ui/panels/bdt_validation_panel.py from AlarmViewer

**Files:**

- Create: `ui/panels/bdt_validation_panel.py`
- Modify: `ui/viewer.py` — remove `_make_validation_tab` (610-755) and BDT table methods

- [ ] **Step 1: Create BdtValidationPanel(QWidget)**

Extract:

- `_make_validation_tab` (610-755)
- `_run_validation` (1580-1624)
- `_on_validation_done` (1626-1633)
- `_on_validation_error` (1635-1638)
- `_populate_bdt_table` (1640-1687)
- `_filter_bdt_table` (1719-1749)
- `_on_bdt_row_clicked` (1751-1769)
- `_rule_cell_text` (1689-1694)
- `_is_lithium_brand` (1696-1698)
- `_lead_acid_soh_percent` (1700-1705)
- `_format_end_rectifier_voltage` (1707-1711)
- `_format_lead_acid_soh` (1713-1717)
- `_export_bdt_results` (2548-2570)
- `_on_bdt_export_done` (2572-2576)
- `_on_bdt_export_error` (2578-2581)
- `_show_daily_review_report` (2603-2605)
- `_record_review_event` (2583-2601)

The panel emits signals when a BDT row is selected (so the detail panel can respond).

- [ ] **Step 2: Update ui/viewer.py**

Replace validation tab construction with `BdtValidationPanel(self)`. Wire signals.

- [ ] **Step 3: Run tests**

Expected: 321 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: extract BdtValidationPanel from AlarmViewer"
```

---

## Task 16: Extract ui/panels/bdt_detail_panel.py from AlarmViewer

**Files:**

- Create: `ui/panels/bdt_detail_panel.py`
- Modify: `ui/viewer.py` — remove `_make_bdt_detail_panel` (757-1068) and all photo/comparison methods

- [ ] **Step 1: Create BdtDetailPanel(QWidget)**

Extract:

- `_make_bdt_detail_panel` (757-1068)
- `_populate_bdt_detail` (1771-1970)
- `_open_current_bdt_file` (1971-1976)
- `_show_photo_fullsize` (1978-2105)
- `_relayout_bdt_photos_if_needed` (2120-2136)
- `_compute_photo_thumb_width` (2138-2157)
- `_render_bdt_photo_bands` (2159-2219)
- `_populate_bdt_photos` (2221-2290)
- `_slot_category` (2293-2298)
- `_build_compare_category_summary` (2300-2306)
- `_category_summary_text` (2308-2315)
- `_comparison_slot_indices` (2317-2329)
- `_normalize_site_token` (2331-2334)
- `_filename_contains_site_code` (2336-2343)
- `_comparison_candidates_for_site` (2345-2380)
- `_setup_photo_comparison` (2382-2412)
- `_on_compare_year_changed` (2414-2417)
- `_show_photo_comparison` (2419-2521)
- `_make_compare_photo_widget` (2523-2546)

This is the largest extraction (~800 lines). The panel receives a `ValidationResult` and renders it.

- [ ] **Step 2: Update ui/viewer.py**

Replace detail panel construction with `BdtDetailPanel(self)`. Connect the validation panel's row-selected signal to the detail panel's populate slot.

- [ ] **Step 3: Run tests**

Expected: 321 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: extract BdtDetailPanel from AlarmViewer"
```

---

## Task 17: Remove compatibility shims and update all imports

Now that everything is in its final location, remove the one-line shim files at the root level and update all remaining imports to point directly to the new locations.

**Files:**

- Delete: `bdt_parser.py`, `bdt_validator.py`, `bdt_export.py`, `bdt_history.py` (shims)
- Delete: `state.py`, `sync_worker.py`, `site_report.py` (shims)
- Delete: `models.py`, `parsers.py`, `backup_time.py`, `viewer.py` (shims)
- Modify: all test files — update imports to new paths
- Modify: `main.py` — final import cleanup

- [ ] **Step 1: Update all test imports**

For each test file, replace old imports with new package paths:

| Old import                                               | New import                                                                        |
| -------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `from alarm_app.backup_time import compute_backup_times` | `from alarm_app.core.backup_time import compute_backup_times`                     |
| `from alarm_app.bdt_parser import ...`                   | `from alarm_app.bdt.parser import ...`                                            |
| `from alarm_app.bdt_validator import ...`                | `from alarm_app.bdt.validator import ...`                                         |
| `from alarm_app.bdt_export import ...`                   | `from alarm_app.bdt.export import ...`                                            |
| `from alarm_app.bdt_history import ...`                  | `from alarm_app.bdt.history import ...`                                           |
| `from alarm_app.parsers import ...`                      | `from alarm_app.data.loaders import ...`                                          |
| `from alarm_app.state import ...`                        | `from alarm_app.data.state import ...`                                            |
| `from alarm_app.sync_worker import ...`                  | `from alarm_app.data.sync import ...`                                             |
| `from alarm_app.site_report import ...`                  | `from alarm_app.data.site_report import ...`                                      |
| `from alarm_app.viewer import ...`                       | `from alarm_app.ui.viewer import ...` or `from alarm_app.core.filters import ...` |
| `from alarm_app.models import ...`                       | `from alarm_app.ui.model import ...`                                              |

- [ ] **Step 2: Delete shim files**

```bash
cd /Users/mikawi/Developer/orange/alarm_app
rm bdt_parser.py bdt_validator.py bdt_export.py bdt_history.py
rm state.py sync_worker.py site_report.py
rm models.py parsers.py backup_time.py viewer.py
```

- [ ] **Step 3: Update main.py PyInstaller fallback**

```python
try:
    from .constants import APP_NAME, APP_VERSION
    from .ui.viewer import AlarmViewer
except ImportError:
    from alarm_app.constants import APP_NAME, APP_VERSION
    from alarm_app.ui.viewer import AlarmViewer
```

- [ ] **Step 4: Run tests**

Expected: 321 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove compatibility shims, all imports point to final locations"
```

---

## Task 18: Update CLAUDE.md and final cleanup

**Files:**

- Modify: `CLAUDE.md`
- Modify: `core/__init__.py`, `data/__init__.py` — add convenience re-exports

- [ ] **Step 1: Update CLAUDE.md architecture section**

Replace the architecture diagram with:

```
alarm_app/
├── main.py          Entry point — QApplication setup, High-DPI, Fusion style
├── constants.py     Schema maps (Huawei/Nokia), display column order, widths, app metadata
├── styles.py        Single STYLE string — full Catppuccin Mocha dark QSS theme
│
├── core/            Pure Python — no Qt, no I/O
│   ├── filters.py       compute_date_mask, parse_manual_days
│   ├── backup_time.py   compute_backup_times (pure DataFrame logic)
│   ├── duration.py      HH:MM:SS ↔ seconds conversion
│   └── classify.py      classify_by_alarm_id, compute_site_down_flag
│
├── data/            I/O layer — no UI
│   ├── loaders.py       File discovery, CSV/XLSX parsing, schema detection, dedup
│   ├── state.py         Session persistence (JSON + Parquet) to ~/.alarm_viewer/
│   ├── sync.py          LocalSyncWorker background sync
│   └── site_report.py   Site report read/build/export
│
├── bdt/             Self-contained BDT subsystem
│   ├── parser.py        BDT Excel file parsing → BDTData dataclass
│   ├── validator.py     11-rule validation engine → ValidationResult
│   ├── export.py        Export formatting for PM summary sheets
│   └── history.py       Test record persistence and comparison
│
└── ui/              PyQt5 — imports from core/, data/, bdt/
    ├── viewer.py        AlarmViewer (QMainWindow) — wiring and state only
    ├── model.py         AlarmTableModel — pre-stringified 2D cache
    ├── threads.py       All QThread workers (Loader, Export, BDTValidation, BackupTime, Restore)
    ├── dialogs.py       Standalone dialogs (ColumnFilter, DailyReview, AlarmIdConfig, BackupTime)
    └── panels/
        ├── search_panel.py          Filter controls (command console layout)
        ├── bdt_validation_panel.py  BDT results table + validation controls
        ├── bdt_detail_panel.py      BDT detail view + photo gallery
        └── left_panel.py            Directory browser + file list
```

Update the Quick Edit Reference table. Update the data flow description.

- [ ] **Step 2: Verify the architectural rule**

```bash
# core/ must not import from ui/
grep -r "from.*ui\." core/ && echo "VIOLATION" || echo "OK: core/ clean"
# data/ must not import from ui/
grep -r "from.*ui\." data/ && echo "VIOLATION" || echo "OK: data/ clean"
```

- [ ] **Step 3: Run full test suite one final time**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -v
```

Expected: 321 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: update CLAUDE.md architecture for new package structure"
```

---

## Execution Dependencies

```
Task 1 (skeleton)
├── Task 2 (BDT move)        ─┐
├── Task 3 (data move)        │ can run in parallel
├── Task 8 (models move)     ─┘
│
├── Task 4 (core/duration)   ─┐
├── Task 5 (core/backup_time) │ can run in parallel after 2,3
├── Task 6 (core/filters)     │
├── Task 7 (core/classify)   ─┘
│
├── Task 9 (ui/threads)       ─ depends on 4,5 (imports core modules)
├── Task 10 (ui/dialogs)      ─ depends on 5 (imports core/backup_time)
├── Task 11 (data/loaders)    ─ depends on 4,7,9 (threads extracted, core imported)
├── Task 12 (move viewer)     ─ depends on 9,10
│
├── Task 13 (search panel)   ─┐
├── Task 14 (left panel)      │ serial — each reduces viewer.py
├── Task 15 (BDT valid panel) │
├── Task 16 (BDT detail panel)┘
│
├── Task 17 (remove shims)    ─ depends on all above
└── Task 18 (CLAUDE.md)       ─ depends on 17
```
