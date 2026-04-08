# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Alarm Viewer** is a PyQt5 desktop app for exploring telecom alarm data from Huawei and Nokia network management systems. Users load CSV/XLSX alarm exports, filter by site/date/category/vendor/duration, compute backup-time analytics (time between Power and Down alarms), and export results to Excel.

**Stack:** Python 3.14, PyQt5, pandas, openpyxl/xlrd, numpy.

## How to Run

```bash
cd "/Volumes/nvme 500/Alarms/codebase/alarm_app"
source ../../.venv/bin/activate
python -m alarm_app.main          # runs the app
pip install -r requirements.txt   # install deps (includes pyarrow for state caching)
```

Windows build: `scripts/build_windows.bat` → `dist/AlarmViewer.exe`

## Architecture

```
alarm_app/
├── main.py          Entry point — QApplication setup, High-DPI, Fusion style
├── constants.py     Schema maps (Huawei/Nokia), display column order, widths, app metadata
├── styles.py        Single STYLE string — full Catppuccin Mocha dark QSS theme
├── models.py        AlarmTableModel — QAbstractTableModel with pre-stringified 2D cache
├── parsers.py       File discovery (os.walk), CSV/XLSX parsing, LoaderThread, ExportThread
├── backup_time.py   compute_backup_times() + BackupTimeDialog + BackupTimeThread
├── state.py         Session persistence — saves UI state (JSON) + DataFrame cache (Parquet) to ~/.alarm_viewer/
└── viewer.py        AlarmViewer (QMainWindow) — all UI construction, filter logic, slots
```

**Data flow:** Files discovered → `LoaderThread` parses in parallel via `ThreadPoolExecutor` → normalised to internal schema → stored as `self._full_df` (master unfiltered DataFrame) → filters applied by `_search()` which always starts from `_full_df` → results loaded into `AlarmTableModel` → state optionally persisted to `~/.alarm_viewer/`.

**Schema detection:** Auto-detected by inspecting column headers. If `"Site ID"` + `"FM Office"` present → Nokia (`SCHEMA_2_MAP`). Otherwise → Huawei (`SCHEMA_1_MAP`). Both normalise to the same `ALL_INTERNAL_COLS` set. See `constants.py` for mappings.

**Backup-time algorithm:** Inner-joins Power and Down alarms by `site_id`, keeps Down alarms that fall within the Power alarm's `[occurred_on, cleared_on]` window, computes `backup_time = down_occurred_on - power_occurred_on`, keeps only the longest per incident.

## Key Conventions

1. **Do not change the UI** unless explicitly asked. Theme and layout are finalised.
2. Widget `objectName`s must match QSS selectors in `styles.py` (e.g. `btn_search`, `btn_clear`, `btn_export`, `btn_backup`, `btn_load`).
3. Duration values are `"HH:MM:SS"` strings, never `timedelta` objects. Pre-computed `_duration_secs` float column exists for fast filtering.
4. `self._full_df` is the master DataFrame. All filtering starts from it.
5. `self._lbl_count` shows visible row count in the header strip.
6. Stats panel (`self._stats` dict: `total`, `power`, `down`, `sites`) refreshes on every `_populate()`, `_search()`, and `_clear_filters()`.
7. The entry point (`main.py`) must stay thin — only app init and launch.
8. `AlarmTableModel` pre-stringifies all cells into a 2D Python list cache on `load()` — `data()` never touches pandas per-cell. Don't break this pattern.
9. Category (`_category`) is determined by filename keywords: `"power"` → Power, `"down"` → Down, else Unknown.
10. State persistence uses `~/.alarm_viewer/state.json` (UI settings) and `data_cache.parquet` (DataFrame). Object columns are coerced to strings before Parquet serialisation.

## Quick Edit Reference

| To change…               | Edit file        |
| ------------------------ | ---------------- |
| Column mappings / names  | `constants.py`   |
| Colours / theme          | `styles.py`      |
| Table model / rendering  | `models.py`      |
| File parsing / loading   | `parsers.py`     |
| Backup-time algorithm    | `backup_time.py` |
| Session persistence      | `state.py`       |
| UI layout / filter logic | `viewer.py`      |

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
