# Alarm DB-Driven Migration Plan

## Goal

Migrate the desktop alarm workflow from the current pandas-first, in-memory model to a DB-driven model where:

- DuckDB is the primary local store for desktop alarm rows.
- SQLite/SQLAlchemy remains the store for UI state, BDT entities, validation runs, sync metadata, file registry, and blob metadata.
- The UI no longer depends on a full in-memory `self._full_df`.
- Alarm reads happen through a query service with paging, counts, stats, and filtered fetches.

This is an architecture migration, not a cleanup. The main payoff is lower memory usage, better scalability for large alarm datasets, and a clearer separation between persisted alarm storage and UI state.

## Current State

Today the desktop app works like this:

1. Alarm files are discovered and parsed into a full pandas DataFrame.
2. That DataFrame becomes `self._full_df`, the master in-memory dataset.
3. Filtering, stats, backup-time analysis, and BDT validation all read from `self._full_df`.
4. The app persists alarm rows to DuckDB for fast restore.
5. On startup, the app restores the full alarm dataset from DuckDB back into memory.

This means DuckDB already acts as the persisted desktop alarm store, but the UI is still fundamentally memory-driven.

## Target Architecture

The target design should look like this:

- DuckDB stores alarm rows and derived alarm columns used by the UI.
- A dedicated alarm query service is responsible for all alarm reads.
- The viewer stores only:
  - current filter state
  - current sort state
  - current page state
  - current selection state
- Alarm tables are rendered from paged query results rather than a full DataFrame.
- BDT validation and backup-time analysis fetch targeted alarm subsets on demand.
- Startup restores view state and initial result pages, not the entire alarm corpus.

## Migration Principles

- Do not rewrite the whole app in one step.
- Keep DuckDB as the single alarm store for desktop alarm rows.
- Keep SQLite/SQLAlchemy for relational metadata and BDT-related entities.
- Introduce a query layer before changing the UI behavior.
- Migrate one alarm reader at a time off `self._full_df`.
- Remove `self._full_df` only after every feature that depends on it has been moved.

## Proposed New Module

Add a new module:

- `data/alarm_store.py`

This module should become the single entry point for desktop alarm access in DuckDB.

### Suggested Query Model

```python
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class AlarmQuery:
    site_text: str = ""
    category: str | None = None
    vendor: str | None = None
    network_type: str | None = None
    min_duration_secs: float | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    manual_days: list[date] | None = None
    both_pd: bool = False
    sort_by: str | None = None
    sort_desc: bool = False
    limit: int = 200
    offset: int = 0
```

### Suggested API

```python
def replace_alarm_table(df: pd.DataFrame) -> None
def query_alarms(q: AlarmQuery) -> pd.DataFrame
def count_alarms(q: AlarmQuery) -> int
def distinct_values(column: str, q: AlarmQuery | None = None) -> list[str]
def stats(q: AlarmQuery | None = None) -> dict[str, int]
def load_alarm_slice_for_bdt(
    site_codes: list[str],
    date_from: datetime | None,
    date_to: datetime | None,
) -> pd.DataFrame
```

This gives the UI a stable contract before the rest of the migration starts.

## Phase 1: Introduce DuckDB Query Layer

### Objective

Add a DuckDB-backed alarm query service without changing the current viewer behavior.

### Work

- Create `data/alarm_store.py`.
- Move DuckDB read/write details out of `data/state.py` over time.
- Implement:
  - table replacement
  - filtered row fetch
  - total count
  - distinct-value lookup
  - stats lookup
  - targeted BDT alarm slice query
- Keep `self._full_df` temporarily so the existing UI remains functional.

### Outcome

The codebase gains a query-first alarm access layer while the UI still works as before.

## Phase 2: Persist Derived Alarm Fields

### Objective

Make DuckDB store query-ready alarm rows instead of requiring pandas-only post-processing after restore.

### Derived Fields That Must Be Persisted

- `_category`
- `_duration_secs`
- `site_down`

### Work

- Ensure ingest computes these fields before writing to DuckDB.
- Keep classification and site-down logic deterministic and reusable.
- Prefer storing final values directly in DuckDB rather than recomputing them after every restore.

### Outcome

DuckDB becomes the source of truth for the columns the UI actually needs.

## Phase 3: Replace Restore and Read APIs

### Objective

Stop using full DataFrame restore as the standard alarm read path.

### Work

- Keep `data/state.py` focused on:
  - UI state
  - feature flags
  - sync metadata
  - review events
- De-emphasize or deprecate `load_dataframe()` and `save_dataframe()` as UI-facing alarm access APIs.
- Replace viewer alarm reads with `alarm_store` query calls.
- Change startup restore from:
  - full DataFrame load
  to:
  - count query
  - first page query
  - persisted view-state restore

### Outcome

Alarm loading becomes query-driven rather than memory-restore-driven.

## Phase 4: Convert the Alarm Table to Paged Queries

### Objective

Render alarms from paged DuckDB results instead of a full DataFrame.

### Work

- Update `ui/model.py` to support paged loads.
- Replace whole-frame model loading with a page-oriented API such as:

```python
def load_page(self, df: pd.DataFrame, total_rows: int, offset: int) -> None:
    ...
```

- Add viewer logic to:
  - build the current query
  - fetch total count
  - fetch current page
  - load the page into the model

### Outcome

The largest visible part of the UI stops depending on `self._full_df`.

## Phase 5: Move Filters from pandas to Query Construction

### Objective

Replace DataFrame filtering with query construction.

### Work

- Add a viewer helper such as:

```python
def _build_alarm_query(self, *, limit: int, offset: int) -> AlarmQuery:
    ...
```

- Map current UI state to query fields:
  - site text
  - category
  - vendor
  - network type
  - duration
  - date range
  - manual days
  - both-P+D mode
  - sorting
- Rewire:
  - `_search()`
  - `_clear_filters()`
  - date quick filters
  - sort interactions
  - restore behavior

### Outcome

Filtering becomes DB-backed and no longer depends on a preloaded full alarm frame.

## Phase 6: Move Stats and Filter Facets to Queries

### Objective

Stop deriving stats and dropdown values from `_full_df`.

### Work

- Replace stats panel calculations with `alarm_store.stats()`.
- Replace dropdown/facet population with `alarm_store.distinct_values(...)`.
- Update column filter popups to read distinct values from the current filtered scope.

### Outcome

Filter controls and summary stats become query-driven and scale with the dataset.

## Phase 7: Migrate Export and Analytics

### Objective

Move analytics and exports off the full in-memory DataFrame.

### Work

#### Export

- Export filtered alarms by querying the filtered result set directly from DuckDB.

#### Backup-Time

- First step: query only the required alarm subset into pandas, then run the existing algorithm.
- Later step: decide whether to rewrite backup-time logic in DuckDB SQL.

#### BDT Validation

- Replace direct dependency on `viewer._full_df`.
- Query only alarms relevant to:
  - current BDT sites
  - current BDT dates
  - required rule windows

### Outcome

Heavy features stop requiring a resident full alarm dataset.

## Phase 8: Remove `self._full_df`

### Objective

Complete the migration by deleting the in-memory master-frame model.

### Work

- Remove `self._full_df` from the viewer.
- Replace restore thread behavior with lighter page/count startup behavior.
- Delete remaining alarm readers that expect a full DataFrame in memory.
- Keep short-lived DataFrames only where a feature explicitly needs a temporary subset.

### Outcome

The desktop alarm flow becomes fully DB-driven.

## File-by-File Change Plan

### `data/alarm_store.py`

New module.

Responsibility:

- all DuckDB alarm querying
- count queries
- filtered page queries
- distinct/facet queries
- targeted analysis fetches

### `data/state.py`

Keep responsibility for:

- UI state
- feature flags
- review logs
- sync metadata

Reduce responsibility for:

- primary alarm reads in the viewer

### `ui/viewer.py`

Add:

- query-builder helper
- page loading flow
- count loading flow

Replace:

- `_load_alarm_dataframe_from_db()`
- `_apply_loaded_alarm_dataframe()`
- restore-from-cache behavior
- most `_full_df` references

### `ui/model.py`

Change from:

- whole-frame model

To:

- page-oriented model

### `ui/threads.py`

Keep:

- ingest/load worker threads

Change:

- restore thread should no longer load a full alarm frame on startup

### `ui/panels/bdt_validation_panel.py`

Replace:

- `viewer._full_df` dependency

With:

- targeted alarm queries for validation

### `core/backup_time.py`

Keep the current pure pandas algorithm initially, but feed it only queried subsets.

## Best First Milestone

The lowest-risk first milestone is:

1. Add `data/alarm_store.py`.
2. Keep `_full_df` temporarily.
3. Switch only the alarm table read path to paged DuckDB queries.
4. Leave export, backup-time, and BDT validation on `_full_df` for one intermediate release.

This proves the DB-driven table architecture without forcing a full migration in one step.

## Biggest Technical Risks

- The current UI and model assume a fully materialized DataFrame.
- Filter popups and stats are tightly coupled to `_full_df`.
- Some analytics paths are simpler in pandas than in SQL.
- BDT validation currently benefits from having alarms already resident in memory.

## Recommended Execution Order

1. Create `data/alarm_store.py`.
2. Persist derived columns during ingest.
3. Add query builder in the viewer.
4. Convert the alarm table to page-based loading.
5. Convert stats and filter facets.
6. Convert export.
7. Convert backup-time.
8. Convert BDT validation.
9. Remove `_full_df`.

## Success Criteria

The migration is complete when:

- the app can start without loading all alarms into memory
- the alarm table works via paging
- filters and stats come from queries
- BDT validation reads targeted alarm subsets
- export and analytics no longer require a resident full alarm DataFrame
- `self._full_df` is no longer the authoritative alarm source

## Execution Log

### Stage 0: Baseline Validation

Status: complete

Changed:

- Confirmed the workspace already contains a partial migration from the prior attempt.
- Re-ran the current full test suite on the active tree.

Validated:

- `./.venv/bin/pytest -q`
- Result: `660 passed, 12 skipped`

Still in progress:

- Review and integrate the remaining DB-driven viewer migration.
- Remove the remaining `viewer._full_df` readers in table, backup, export, and BDT flows.

### Stage 1: DuckDB Alarm Store + State Handoff

Status: complete

Changed:

- Added `data/alarm_store.py` as the DuckDB-backed alarm query layer.
- Switched `data/state.py` alarm persistence/load paths to delegate to `alarm_store`.
- Added store/state coverage in `tests/test_alarm_store.py`.

Validated:

- Prior targeted validation from the earlier execution on this tree.
- Full-suite revalidation in Stage 0 remained green after the partial migration state was resumed.

Still in progress:

- Viewer startup still restores and filters a full DataFrame.
- Table paging, stats, facets, export, backup-time, and BDT flows are not yet fully DB-driven.

### Stage 2: Query-Driven UI + Analytics Migration

Status: complete

Changed:

- Split remaining work into parallel owned tracks:
- Track A: `ui/viewer.py`, `ui/model.py`, viewer/model paging tests.
- Track B: `ui/threads.py`, BDT panels, backup/export/query-backed subset tests.
- Converted the alarm table/model path to page-oriented query loads from DuckDB.
- Switched viewer startup restore, DB-mode load, search, sort, stats, facets, and header filters to `AlarmQuery` + `alarm_store`.
- Moved backup-time, BDT validation, PM Accept report generation, and BDT detail door-alarm history to targeted DuckDB subsets instead of a resident master frame.
- Rewired export and site-report generation to query filtered alarm subsets directly from DuckDB.
- Added focused migration coverage in:
- `tests/test_alarm_cache_ui.py`
- `tests/test_alarm_store.py`
- `tests/test_non_table_alarm_migration.py`

Validated:

- Targeted syntax/import check with `python -m py_compile` for the changed query/viewer/store modules and tests.
- Targeted regression suite:
- `./.venv/bin/pytest -q tests/test_alarm_cache_ui.py tests/test_non_table_alarm_migration.py tests/test_alarm_store.py tests/test_alarm_loader_persistence.py tests/test_state.py`
- Result: `45 passed`
- Full application suite:
- `./.venv/bin/pytest -q`
- Result: `664 passed, 12 skipped`

Still in progress:

- No implementation stages remain in progress for this migration plan.
- `_full_df` remains in `ui/viewer.py` only as a compatibility fallback path, but the DB-driven runtime paths now use DuckDB query state rather than a resident authoritative master DataFrame.
