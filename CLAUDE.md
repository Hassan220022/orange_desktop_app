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
├── db/              SQLAlchemy ORM + repositories
│   ├── engine.py        create_engine, get_session, init_db (SQLite local, Postgres later)
│   ├── models.py        14 ORM table models
│   ├── hashing.py       Canonical normalization, SHA-256, dHash for dedup
│   └── repos/           Repository pattern — one file per domain
│       ├── alarm_repo.py    Alarm records with row-hash dedup
│       ├── bdt_repo.py      BDT tests + photos with content-hash dedup
│       ├── blob_repo.py     Blob assets — images on disk, metadata in DB
│       ├── file_repo.py     Uploaded files with SHA-256 dedup
│       ├── pm_repo.py       PM validation runs + rule results
│       ├── state_repo.py    UI state key-value store
│       └── sync_repo.py     Sync outbox + checkpoints
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

**Layered architecture:** The codebase follows a strict three-layer split. `core/` contains pure Python with no Qt and no I/O, so every function there can be tested without a running app. `data/` handles file I/O, persistence, and sync. `ui/` owns all PyQt5 code and imports from the other two layers. The one directional rule: `core/` and `data/` never import from `ui/`.

**Data flow:** Files discovered → `LoaderThread` (in `ui/threads.py`) parses in parallel via `ThreadPoolExecutor` using logic from `data/loaders.py` → normalised to internal schema → stored as `self._full_df` (master unfiltered DataFrame) → filters applied by `_search()` using `core/filters.py`, always starting from `_full_df` → results loaded into `AlarmTableModel` → state optionally persisted to `~/.alarm_viewer/` via `data/state.py`.

**Schema detection:** Auto-detected by inspecting column headers. If `"Site ID"` + `"FM Office"` present → Nokia (`SCHEMA_2_MAP`). Otherwise → Huawei (`SCHEMA_1_MAP`). Both normalise to the same `ALL_INTERNAL_COLS` set. See `constants.py` for mappings.

**Backup-time algorithm:** Inner-joins Power and Down alarms by `site_id`, keeps Down alarms that fall within the Power alarm's `[occurred_on, cleared_on]` window, computes `backup_time = down_occurred_on - power_occurred_on`, keeps only the longest per incident. Pure logic lives in `core/backup_time.py`; the thread wrapper lives in `ui/threads.py`.

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
11. `core/` and `data/` must never import from `ui/`. This is the only architectural rule.
12. Panels receive data from AlarmViewer via bridge pattern or method calls.
13. `db/` handles all SQL. No raw SQL outside `db/repos/`. `data/state.py` is the adapter between the app and the DB layer.

## Quick Edit Reference

| To change...            | Edit file                           |
| ----------------------- | ----------------------------------- |
| Column mappings / names | `constants.py`                      |
| Colours / theme         | `styles.py`                         |
| Table model / rendering | `ui/model.py`                       |
| File parsing / loading  | `data/loaders.py`                   |
| Backup-time algorithm   | `core/backup_time.py`               |
| Session persistence     | `data/state.py`                     |
| UI layout / wiring      | `ui/viewer.py`                      |
| Filter logic            | `core/filters.py`                   |
| DB tables / columns     | `db/models.py`                      |
| DB queries / CRUD       | `db/repos/*.py`                     |
| Hash computation        | `db/hashing.py`                     |
| DB connection           | `db/engine.py`                      |
| BDT parsing             | `bdt/parser.py`                     |
| BDT validation rules    | `bdt/validator.py`                  |
| BDT export formatting   | `bdt/export.py`                     |
| BDT history tracking    | `bdt/history.py`                    |
| Search/filter panel     | `ui/panels/search_panel.py`         |
| BDT validation panel    | `ui/panels/bdt_validation_panel.py` |
| BDT detail/photo panel  | `ui/panels/bdt_detail_panel.py`     |
| Background threads      | `ui/threads.py`                     |
| Popup dialogs           | `ui/dialogs.py`                     |

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

| Tool                        | Use when                                               |
| --------------------------- | ------------------------------------------------------ |
| `detect_changes`            | Reviewing code changes — gives risk-scored analysis    |
| `get_review_context`        | Need source snippets for review — token-efficient      |
| `get_impact_radius`         | Understanding blast radius of a change                 |
| `get_affected_flows`        | Finding which execution paths are impacted             |
| `query_graph`               | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes`     | Finding functions/classes by name or keyword           |
| `get_architecture_overview` | Understanding high-level codebase structure            |
| `refactor_tool`             | Planning renames, finding dead code                    |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
