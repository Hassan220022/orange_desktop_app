# Alarm Viewer v2 — Full Rethink Design

**Status:** Draft, pending user approval
**Date:** 2026-06-03
**Branch:** `v2` (long-lived release branch, cut from `main` at `ce401c4`)
**Author:** brainstormed with user, drafted by agent

## 1. Context & Motivation

Alarm Viewer is a mature PyQt5 desktop app for exploring Huawei and Nokia
telecom alarm data. The repo is **8,191 symbols across 298 execution flows**
(GitNexus index). The current code works, but the user reports it has become
hard to maintain. This design proposes a v2 of the product that:

- swaps the UI layer from PyQt5 widgets to **PySide6 (Qt6) + QML**
- keeps the proven Python core, I/O, and DB layers (with consolidation)
- delivers a modern, polished UI as the v2 MVP non-negotiable
- ships on Windows and macOS

The user has explicitly chosen a **full rethink** of every layer, not a
UI-only refresh. The non-negotiable for v2 is **a modern, demo-ready UI**.
The DB layer gets consolidated during the rewrite (Section 7).

## 2. Goals (v2)

| #   | Goal                                              | Measure                                                                             |
| --- | ------------------------------------------------- | ----------------------------------------------------------------------------------- |
| G1  | Modern, polished UI the user is proud to demo     | Visual review + user sign-off                                                       |
| G2  | Clean module boundaries, no circular imports      | `pydeps` / `import-linter` passes                                                   |
| G3  | 100% of `core/` and `data/` covered by unit tests | `pytest --cov` ≥ 100% for those layers                                              |
| G4  | 100% type hints on new code                       | `mypy --strict` clean on new modules                                                |
| G5  | Boots in < 3s with 100k alarm rows                | `time python -m alarm_app.main` after warm cache                                    |
| G6  | Filters and search return in < 200ms over 1M rows | Instrumented benchmark on the `_search()` path                                      |
| G7  | Ships on Windows 10/11 and macOS 13+              | CI builds both artifacts                                                            |
| G8  | v2 ships with zero data loss vs v1                | Round-trip test: load v1 cache, run all workflows, diff against v1 reference output |

## 3. Non-Goals (v2)

- **No new features.** v2 is a faithful re-implementation of v1's feature set
  with a better UI and better internals. New features go in v2.1.
- **No Linux support.** Windows + macOS only. The codebase stays
  cross-platform-compatible (no Windows-only APIs in shared code) but we
  don't ship or test a Linux build.
- **No migration of v1 user settings beyond what `data/state.py` already does.**
- **No rewrite of the BDT 11-rule validator.** The rules are domain knowledge;
  we port them and the parser as-is, and add tests.
- **No replacement of SQLAlchemy or pandas.** Both stay. They are the moat.

## 4. Architectural Decisions

### 4.1 Stack

| Layer       | v1                           | v2                                                 |
| ----------- | ---------------------------- | -------------------------------------------------- |
| UI toolkit  | PyQt5                        | **PySide6 (Qt6)** + **QML**                        |
| Python      | 3.14                         | 3.14 (unchanged)                                   |
| Data        | pandas, numpy                | unchanged                                          |
| Persistence | SQLAlchemy + SQLite/Postgres | unchanged                                          |
| Excel I/O   | openpyxl, xlrd               | unchanged                                          |
| Packaging   | PyInstaller                  | unchanged (spec file is regenerated)               |
| Theme       | Catppuccin Mocha (QSS)       | **Catppuccin Mocha (QML)** + Material 3 components |

### 4.2 Layered Architecture

```
v2/
├── main.py                      # Entry: QApplication, QML engine, theme
├── app/
│   ├── __init__.py
│   ├── engine.py                # QGuiApplication + QQmlApplicationEngine setup
│   └── theme.py                 # QML theme singleton (colors, fonts, spacing)
│
├── core/                        # UNCHANGED from v1
│   ├── filters.py
│   ├── backup_time.py
│   ├── duration.py
│   └── classify.py
│
├── data/                        # MINOR CHANGES: state.py moves into services/
│   ├── loaders.py               # UNCHANGED
│   └── site_report.py           # UNCHANGED
│
├── services/                    # NEW: persistence + business orchestration
│   ├── __init__.py
│   ├── persistence.py           # Was db/ + data/state.py merged
│   ├── alarm_service.py         # High-level alarm operations
│   ├── bdt_service.py           # Was bdt/ subpackage (now a service)
│   ├── sync_service.py          # Was data/sync.py
│   └── search_service.py        # Filter + search orchestration
│
├── adapters/                    # NEW: Python ↔ QML boundary
│   ├── __init__.py
│   ├── viewmodels/
│   │   ├── base.py              # BaseViewModel(QObject) with property helpers
│   │   ├── search_vm.py
│   │   ├── alarm_table_vm.py    # QAbstractTableModel backed by filtered DataFrame
│   │   ├── bdt_validation_vm.py
│   │   ├── bdt_detail_vm.py
│   │   └── left_panel_vm.py
│   ├── models/
│   │   ├── alarm_row_model.py   # QAbstractTableModel subclass
│   │   └── filter_options.py    # ListModel for filter dropdowns
│   └── workers/
│       ├── loader_worker.py     # QThread for file loading
│       ├── export_worker.py     # QThread for Excel export
│       ├── backup_time_worker.py
│       └── bdt_validation_worker.py
│
├── qml/                         # NEW: pure declarative UI
│   ├── Main.qml                 # Top-level window, layout
│   ├── theme/
│   │   ├── Theme.qml            # Singleton: Catppuccin Mocha palette
│   │   └── Material.qml         # Material 3 style overrides
│   ├── components/
│   │   ├── PrimaryButton.qml
│   │   ├── TextField.qml
│   │   ├── ComboBox.qml
│   │   ├── DataTable.qml        # Reusable virtualized table
│   │   ├── StatsStrip.qml       # Top stats bar
│   │   ├── FileBrowser.qml
│   │   └── ...
│   ├── pages/
│   │   ├── SearchPage.qml       # Search panel as a QML page
│   │   ├── BDTValidationPage.qml
│   │   ├── BDTDetailPage.qml
│   │   └── LeftPanelPage.qml
│   └── dialogs/
│       ├── ColumnFilterDialog.qml
│       ├── DailyReviewDialog.qml
│       ├── AlarmIdConfigDialog.qml
│       └── BackupTimeDialog.qml
│
├── db/                          # GONE — merged into services/persistence.py
│
├── bdt/                         # GONE — moved into services/bdt_service.py
│
├── constants.py                 # UNCHANGED
├── tests/                       # Greatly expanded (see Section 9)
│   ├── unit/
│   │   ├── core/                # 100% coverage required
│   │   ├── data/
│   │   ├── services/
│   │   └── adapters/            # ViewModel logic only (not QML rendering)
│   ├── integration/
│   │   ├── test_load_to_search.py
│   │   ├── test_backup_time_e2e.py
│   │   └── test_bdt_validation_e2e.py
│   └── ui/
│       └── test_qml_smoke.py    # Boots the QML engine, asserts no errors
└── pyproject.toml
```

### 4.3 QML ↔ Python Boundary (Decision: ViewModel-per-Panel)

Each QML page binds to exactly one Python ViewModel. ViewModels:

- inherit from `BaseViewModel(QObject)`
- expose data as `Property` (with notify signals)
- expose actions as `Slot` or `Q_INVOKABLE`
- never touch pandas DataFrames in their public API; they hand off to
  `services/` for the heavy lifting
- are unit-testable without a running QML engine (pure Python with QObject)

The QML side is purely declarative. It binds to properties, calls slots,
and reacts to signals. No business logic in QML.

### 4.4 Alarm Data Model (Decision: QAbstractTableModel + pandas backend)

`AlarmTableModel(QAbstractTableModel)`:

- holds a reference to a `pandas.DataFrame` (the filtered view)
- implements `rowCount()`, `columnCount()`, `data()` over the DataFrame
- emits `modelReset` when the filter changes (cheap because we filter
  in pandas and just swap the reference)
- pairs with a QML `TableView` that virtualizes rows (Qt 6.5+)

This replaces v1's "pre-stringified 2D Python list" pattern. v1's pattern
re-renders the whole list on filter change; the v2 pattern keeps
virtualization and pandas power. Cost: ~1 day of careful DataFrame →
QVariant marshaling work. Gain: smooth scrolling on 1M+ rows.

### 4.5 Persistence (Decision: Consolidate db/ + state.py)

`services/persistence.py` is a single facade that owns:

- the SQLAlchemy engine (from v1's `db/engine.py`)
- the 14 ORM models (from v1's `db/models.py`)
- the 7 repositories (from v1's `db/repos/`)
- session caching (from v1's `data/state.py`)
- Parquet DataFrame caching (from v1's `data/state.py`)

Public API is split into focused sub-facades exposed to QML:

- `Persistence.alarms` → alarm repository
- `Persistence.bdt` → BDT repository
- `Persistence.blobs` → blob repository
- `Persistence.files` → file repository
- `Persistence.state` → state key-value store

No raw SQL outside this module. No direct imports of SQLAlchemy anywhere
else in the codebase. This is the rule that replaces v1's
"db/ never imports from ui/" rule.

### 4.6 Async / Threading

| v1 pattern                                                                                 | v2 pattern                                          |
| ------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| `QThread` subclasses in `ui/threads.py`                                                    | `QRunnable` + `QThreadPool` (Qt6 idiom)             |
| Per-thread QObject worker                                                                  | Same worker, different lifecycle                    |
| Blocking `data()` calls during load                                                        | Worker emits progress signal to ViewModel           |
| `LoaderThread`, `ExportThread`, `BackupTimeThread`, `RestoreThread`, `BDTValidationThread` | One generic `Worker(QRunnable)` with task dataclass |

All workers live in `adapters/workers/`. They call into `services/`, not
into `core/` directly. Services expose synchronous APIs; workers wrap them.

### 4.7 Theme

Catppuccin Mocha, ported to QML as a singleton (`Theme.qml`). All colors,
spacing, font sizes, and motion timings come from the theme. No hardcoded
color literals anywhere in `qml/`. A theme swap (e.g. to a light theme)
becomes a one-file change.

## 5. Component Inventory

### 5.1 New components

| Component                | Purpose                                     | File                                       |
| ------------------------ | ------------------------------------------- | ------------------------------------------ |
| `App(QObject)`           | Root QML engine host, theme bootstrap       | `app/engine.py`                            |
| `BaseViewModel`          | Property/signal/slot helpers                | `adapters/viewmodels/base.py`              |
| `AlarmTableModel`        | QAbstractTableModel over filtered DataFrame | `adapters/models/alarm_row_model.py`       |
| `SearchViewModel`        | Drives the search panel page                | `adapters/viewmodels/search_vm.py`         |
| `BDTValidationViewModel` | Drives BDT validation page                  | `adapters/viewmodels/bdt_validation_vm.py` |
| `BDTDetailViewModel`     | Drives BDT detail page                      | `adapters/viewmodels/bdt_detail_vm.py`     |
| `LeftPanelViewModel`     | Drives directory browser                    | `adapters/viewmodels/left_panel_vm.py`     |
| `Worker(QRunnable)`      | Generic async task runner                   | `adapters/workers/worker.py`               |
| `Persistence`            | Unified DB + state facade                   | `services/persistence.py`                  |
| `AlarmService`           | Load, filter, export orchestration          | `services/alarm_service.py`                |
| `BDTService`             | BDT parse + validate orchestration          | `services/bdt_service.py`                  |
| `SearchService`          | Filter + search orchestration               | `services/search_service.py`               |

### 5.2 Components deleted

| v1 file                 | v2 fate                                          |
| ----------------------- | ------------------------------------------------ |
| `ui/viewer.py`          | Replaced by QML `Main.qml` + ViewModels          |
| `ui/model.py`           | Replaced by `adapters/models/alarm_row_model.py` |
| `ui/threads.py`         | Replaced by `adapters/workers/`                  |
| `ui/dialogs.py`         | Replaced by QML dialogs                          |
| `ui/panels/*.py`        | Replaced by QML pages                            |
| `db/` (entire package)  | Merged into `services/persistence.py`            |
| `bdt/` (entire package) | Merged into `services/bdt_service.py`            |
| `data/state.py`         | Merged into `services/persistence.py`            |
| `data/sync.py`          | Moved to `services/sync_service.py`              |
| `styles.py`             | Replaced by `qml/theme/Theme.qml`                |

### 5.3 Components preserved verbatim

- `core/*` (filters, backup_time, duration, classify) — unchanged
- `data/loaders.py` — unchanged
- `data/site_report.py` — unchanged
- `constants.py` — unchanged
- `__init__.py` and all existing tests in `tests/core/`, `tests/data/`,
  `tests/db/` — preserved, expanded

## 6. Data Flow

```
File on disk
  → LoaderWorker (QRunnable)
    → AlarmService.load_files()
      → core/loader (v1's data/loaders.py)
      → persistence.write_cache_parquet()
    → emit progress + done signals
  → SearchViewModel on_done()
    → SearchService.apply_filters()
      → core/filters.compute_date_mask()
    → emit dataframeChanged signal
  → AlarmTableModel.on_dataframeChanged()
    → beginResetModel(); swap _df; endResetModel()
  → QML TableView re-binds to model
    → virtualized rendering
```

The flow is identical to v1 conceptually (file → DataFrame → filtered
DataFrame → model → view). The difference is that every transition is
now a typed message between named objects with clear ownership, instead
of v1's tendency to mutate `self._full_df` from multiple call sites.

## 7. Error Handling

- **All services raise typed exceptions**, never return None for failure.
  Exceptions: `AlarmLoadError`, `FilterError`, `PersistenceError`,
  `BDTParseError`, `BDTValidationError`, `ExportError`.
- **Workers catch exceptions** and emit an `errorOccurred` signal carrying
  the exception type, message, and original traceback.
- **ViewModels translate errors** into user-facing state:
  `self._state = ErrorState(message, recoverable=True/False)`. QML binds
  to this and shows a snackbar / dialog.
- **No silent failures.** Every error path has a log line at WARNING
  minimum, plus a user-visible message.
- **QML errors are logged** via `QtCore.qInstallMessageHandler` to a
  structured JSON log file.

## 8. Migration Strategy

### 8.1 Branch layout

- `main` keeps receiving v1.x hotfixes and small features
- `v2` is the long-lived release branch (created at `ce401c4`)
- Sub-projects branch off `v2`:
  - `v2/ui-foundation` → QML bootstrap, theme, Main.qml shell
  - `v2/viewmodels` → BaseViewModel + all 4 panel VMs
  - `v2/alarm-model` → AlarmTableModel + virtualization
  - `v2/persistence` → services/persistence.py + repos
  - `v2/services` → AlarmService, BDTService, SearchService
  - `v2/workers` → Worker + all task types
  - `v2/qml-pages` → QML pages and dialogs
  - `v2/cutover` → remove v1 UI, package, ship

Each sub-project gets its own spec under `docs/superpowers/specs/` and
its own implementation plan. They merge into `v2` in dependency order
(Section 10).

### 8.2 v1 stays runnable

Until `v2/cutover` merges, the v1 app must keep running on `v2`. We
achieve this by:

- adding new code in `app/`, `services/`, `adapters/`, `qml/`
- not touching `main.py` until cutover
- v1 entry point (`main.py`) keeps importing from `ui/`
- the new entry point (`app/engine.py`) is opt-in via a flag

Once `v2/cutover` is ready, we:

- rewrite `main.py` to boot via `app/engine.py`
- delete `ui/`, `db/`, `bdt/`, `data/state.py`, `data/sync.py`,
  `styles.py`
- keep `core/`, `data/loaders.py`, `data/site_report.py`,
  `constants.py`

## 9. Testing

### 9.1 Coverage targets

| Layer                  | Target                                             | Tool                             |
| ---------------------- | -------------------------------------------------- | -------------------------------- |
| `core/`                | 100% lines + branches                              | `pytest --cov`                   |
| `data/`                | 100% lines + branches                              | `pytest --cov`                   |
| `services/`            | 100% lines                                         | `pytest --cov`                   |
| `adapters/viewmodels/` | 100% lines (logic only)                            | `pytest --cov`                   |
| `adapters/models/`     | 90% lines                                          | `pytest --cov`                   |
| `adapters/workers/`    | 90% lines                                          | `pytest --cov`                   |
| `qml/`                 | Smoke tests only (engine boots, root window loads) | `pytest-qt` + QML signal capture |

### 9.2 Test types

- **Unit tests** for every pure function in `core/`, `services/`,
  `adapters/viewmodels/`
- **Integration tests** that exercise a full feature path
  (load → filter → export, parse BDT → validate → export)
- **QML smoke tests** that boot the engine, load each page, and
  assert no QML errors and no Python exceptions
- **Round-trip tests** that load v1's persisted state into v2 and
  assert identical behavior on a fixed-input fixture
- **Performance benchmarks** for the `_search()` and `load_files()`
  paths, gated by a `BENCH=1` env var

## 10. Build & Ship Order

Each step is a separate sub-project with its own spec and plan.
Dependency order:

1. `v2/persistence` — services/persistence.py + 14 models + 7 repos + tests
2. `v2/services` — AlarmService, BDTService, SearchService, SyncService
3. `v2/viewmodels` — BaseViewModel + 4 panel ViewModels + tests
4. `v2/alarm-model` — AlarmTableModel with QAbstractTableModel + pandas
5. `v2/workers` — Worker + 4 task types + tests
6. `v2/ui-foundation` — main.py rewrite, app/engine.py, qml/theme/, Main.qml
7. `v2/qml-pages` — search, BDT validation, BDT detail, left panel pages
8. `v2/qml-dialogs` — column filter, daily review, alarm id config, backup time
9. `v2/cutover` — delete ui/, db/, bdt/, styles.py, data/state.py, data/sync.py
10. `v2/windows` — regenerate PyInstaller spec, build .exe, test
11. `v2/macos` — generate .app bundle, notarize, test

Steps 1-9 ship as a single release once all 9 are merged. Steps 10-11
produce the actual artifacts.

## 11. Open Questions for Implementation Phase

These are NOT blocking the design, but each sub-project will need to
resolve them:

- Q1. Should the new QML theme support light mode? (Catppuccin Latte)
  If yes, define the toggle UX in the `ui-foundation` sub-project.
- Q2. Should we adopt Qt 6.7's new `qt_add_qml_module` (CMake) build
  system, or stick with `QML_IMPORT_PATH` and Python-side resource
  registration? Recommend the latter for v2 to keep pyproject simple.
- Q3. Do we need a `--legacy` flag to boot the v1 PyQt5 UI from the v2
  binary, for emergency fallback? Recommend yes, gated on the v1
  modules still being importable.
- Q4. SQLite remains the default. When do we promote Postgres? (Answer:
  not in v2; ship SQLite only. Postgres is a v2.1 problem.)

## 12. Success Criteria for "v2 Done"

- [ ] All 11 sub-projects merged into `v2`
- [ ] `v1 PyQt5 UI` is deleted from the tree
- [ ] `pytest` passes with coverage targets met
- [ ] `mypy --strict` is clean on `services/` and `adapters/`
- [ ] Round-trip test passes (v1 cache → v2 → identical output)
- [ ] QML smoke tests pass for all 4 pages + 4 dialogs
- [ ] Windows .exe builds and boots; macOS .app builds and boots
- [ ] User runs the app, sees the new UI, and signs off
- [ ] `v2` merges to `main` and the release is tagged
