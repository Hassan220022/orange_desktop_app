# Agent Instructions — Alarm Viewer

## GitNexus CLI Requirement

This repository is indexed by GitNexus as **orange_desktop_app**. Codex, OpenCode, Claude Code, and any other AI agent working in this repo must use the local GitNexus CLI, not MCP.

- Use `/opt/homebrew/bin/gitnexus` or `gitnexus` from PATH.
- Never use GitNexus MCP, code-review-graph MCP, or `gitnexus://...` MCP resources for this repo.
- Run `gitnexus status` at the start of code work.
- Run `gitnexus query -r orange_desktop_app "<concept>"` before Grep/Glob/Read when exploring unfamiliar code.
- Run `gitnexus impact -r orange_desktop_app -d upstream <symbol>` before editing any function, class, or method.
- Run `gitnexus detect-changes -r orange_desktop_app --scope all` before committing.
- If the index is stale, run `gitnexus analyze` and retry the GitNexus command.

## Project Overview

**Alarm Viewer** is a PyQt5 desktop application for exploring, filtering, and analysing telecom alarm data exported from Huawei and Nokia NMS platforms. It reads CSV/XLSX files containing Power and Down alarm records, normalises them into a unified schema, and provides a fast, professional dark-themed UI for searching, filtering, sorting, exporting, and computing backup-time analytics.

---

## Folder Structure

```
/Volumes/nvme 500/Alarms/
│
├── alarm_viewer.py              # Entry point — thin launcher (≈35 lines)
├── requirements.txt             # Python dependencies
├── build_windows.bat            # PyInstaller build script for Windows .exe
├── AGENT.md                     # This file — agent instructions
├── CLAUDE.md                    # Project reference for Claude / LLMs
│
├── alarm_app/                   # Main application package
│   ├── __init__.py              # Package marker
│   ├── constants.py             # Schema maps, display columns, col widths, app metadata
│   ├── styles.py                # Full QSS stylesheet (Catppuccin Mocha dark theme)
│   ├── models.py                # AlarmTableModel — high-performance QAbstractTableModel
│   ├── parsers.py               # File discovery, CSV/XLSX parsing, LoaderThread
│   ├── backup_time.py           # Backup-time computation + BackupTimeDialog
│   └── viewer.py                # AlarmViewer main window — all UI + slots
│
├── csv/                         # Alarm data files (8 CSV files)
│   ├── Down_Alarm_01_Dec_2025.csv
│   ├── Down_Alarm_01_Feb_to_15_Feb_2026.csv
│   ├── Down_Alarm_18_Jan_to_01_Feb_2026.csv
│   ├── Down_Alarm_Dec_2025_to_Jan_2026.csv
│   ├── Power_Alarm_01_Dec_2025.csv
│   ├── Power_Alarm_01_Feb_to_15_Feb_2026.csv
│   ├── Power_Alarm_18_Jan_to_01_Feb_2026.csv
│   └── Power_Alarm_Dec_2025_to_Jan_2026.csv
│
├── .venv/                       # Python virtual environment (Python 3.14.0)
└── .git/                        # Git repo
```

---

## Tech Stack

| Component        | Technology                     |
|------------------|--------------------------------|
| Language         | Python 3.14.0                  |
| GUI Framework    | PyQt5 5.15.11                  |
| Data Processing  | pandas 3.0.1, numpy 2.4.2     |
| Excel I/O        | openpyxl 3.1.5, xlrd 2.0.2    |
| Packaging        | PyInstaller (Windows .exe)     |
| Platform         | macOS (dev), Windows (target)  |

---

## Data Schemas

The app auto-detects which schema a file uses based on column headers.

### Schema 1 — Huawei (identified by `"Site Name"` column)

| CSV Header                | Internal Key         |
|---------------------------|----------------------|
| Alarm Source              | alarm_source         |
| Site Name                 | site_id              |
| Last Occurred On          | occurred_on          |
| Cleared On                | cleared_on           |
| Duration(hh:mm:ss)        | duration             |
| Alarm ID                  | alarm_id             |
| Alarm Name                | alarm_name           |
| Clearance Status          | clearance_status     |
| Network Type              | network_type         |
| Vendor                    | vendor               |

### Schema 2 — Nokia (identified by `"Site ID"` + `"FM Office"`)

| CSV Header                | Internal Key         |
|---------------------------|----------------------|
| Site ID                   | site_id              |
| FM Office                 | fm_office            |
| Alarm Source              | alarm_source         |
| Alarm Name                | alarm_name           |
| Network Type              | network_type         |
| Last Occurred On          | occurred_on          |
| Cleared On                | cleared_on           |
| Site Down Flag            | site_down_flag       |
| Vendor                    | vendor               |

---

## Key Features

1. **Recursive file discovery** — `os.walk()` scans any directory for `.csv`, `.xlsx`, `.xls` files
2. **Multi-file loading** — background `QThread` with progress bar
3. **Search & filter** — Site ID (partial, case-insensitive), date range, category, network type, vendor
4. **≥ 15 min duration filter** — enabled by default, togglable checkbox; hides alarms < 15 minutes
5. **Backup Time analysis** — `pd.merge_asof(direction="forward", tolerance=72h)` pairs Power→Down alarms per site
6. **Export** — filtered results to `.xlsx` via openpyxl
7. **Copy support** — double-click cell, right-click menu (Copy Cell / Copy Row), Ctrl+C for multi-selection
8. **Professional dark theme** — Catppuccin Mocha palette, glassmorphism-inspired, colour-coded buttons

---

## Performance Optimisations

- **Pre-stringified display cache** in `AlarmTableModel` — `data()` never touches pandas per-cell; 5–10× faster scrolling
- **Pre-allocated QBrush/QColor singletons** — colour objects created once at module level
- **Smart sort** — datetime columns sort natively; text columns use `.str.lower()` key
- **Reduced encoding fallbacks** — `utf-8-sig` → `latin-1` (2 attempts, not 4)
- **Zero-copy concat** — `pd.concat(copy=False)` during file merge

---

## Module Responsibilities

### `alarm_viewer.py` (entry point)
- Sets High-DPI attributes
- Creates `QApplication` with Fusion style
- Instantiates and shows `AlarmViewer`

### `alarm_app/constants.py`
- `APP_NAME`, `APP_VERSION`
- `SCHEMA_1_MAP`, `SCHEMA_2_MAP` — column rename dicts
- `DISPLAY_COLUMNS`, `ALL_INTERNAL_COLS` — ordered display config
- `COL_WIDTHS` — per-column pixel widths
- `BT_HEADERS`, `BT_WIDTHS` — backup-time dialog config

### `alarm_app/styles.py`
- Single `STYLE` string (~8800 chars of QSS)
- Palette: `#13131f` base, `#0f0f1a` sidebar/header, `#1a1a2a` inputs, `#2a2a3e` borders
- Button types: `btn_search` (blue), `btn_clear` (red), `btn_export` (green), `btn_backup` (purple), `btn_load` (amber), `btn_small`, `btn_dir`

### `alarm_app/models.py`
- `AlarmTableModel(QAbstractTableModel)` — pandas-backed with cache
- Roles: DisplayRole (from cache), BackgroundRole (category/network colours), ForegroundRole (status/site/vendor), TextAlignmentRole

### `alarm_app/parsers.py`
- `discover_alarm_files(directory)` — returns list of info dicts
- `parse_alarm_file(info)` — reads one file, auto-detects schema, normalises columns
- `LoaderThread(QThread)` — loads multiple files with progress signals

### `alarm_app/backup_time.py`
- `compute_backup_times(df)` — pairs Power→Down per site using `merge_asof`
- `BackupTimeDialog(QDialog)` — summary stats + sortable table + CSV export

### `alarm_app/viewer.py`
- `AlarmViewer(QMainWindow)` — complete UI
- Layout: sidebar (260px) | header strip (48px) + search panel (2 rows) + table
- Slots: `_browse`, `_scan`, `_load`, `_search`, `_clear_filters`, `_export`, `_show_backup_times`
- Copy: `_copy_cell`, `_copy_row`, `keyPressEvent` (Ctrl+C)
- Duration filter: `_dur_to_sec()` helper, `_chk_min15` checkbox

---

## How to Run

```bash
# macOS / Linux
cd "/Volumes/nvme 500/Alarms"
source .venv/bin/activate
python alarm_viewer.py

# Windows (after building)
build_windows.bat
dist\AlarmViewer.exe
```

---

## Coding Conventions

- **No UI changes** unless explicitly requested — UI is finalised
- All widget `objectName`s must match the QSS selectors in `styles.py`
- Duration values are `"HH:MM:SS"` strings, not timedeltas
- `self._full_df` holds the complete unfiltered dataset; `_search()` always starts from it
- `self._lbl_count` in the header strip shows current view count
- Stats panel (`self._stats` dict) refreshes on every populate/search/clear
