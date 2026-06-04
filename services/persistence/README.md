# services/persistence

Single facade for all persistence operations in Alarm Viewer v2.

## Architecture

```
adapters/  qml/  ui/   ← no direct SQL or SQLAlchemy
│
▼
services/              ← orchestration, business logic
│
▼
services/persistence/  ← only place that imports from sqlalchemy or duckdb
├── engine.py          singleton SQLAlchemy engine
├── models.py          14 ORM models
├── hashing.py         canonical normalization, SHA-256, dHash
├── retry.py           retry decorator
├── seed.py            reference data
├── alarm_cache.py     DuckDB-backed DataFrame cache
├── facade.py          Persistence singleton + 9 sub-facades
├── exceptions.py      typed exception hierarchy
└── repos/             7 repository modules
    ├── alarm_repo.py
    ├── bdt_repo.py
    ├── blob_repo.py
    ├── catalog_repo.py
    ├── file_repo.py
    ├── pm_repo.py
    ├── state_repo.py
    └── sync_repo.py
```

## Public API

```python
from services.persistence import Persistence

p = Persistence.instance()
p.alarms.upsert(session, df)        # bulk insert with row_hash dedup
p.alarms.get_by_hash(session, h)    # single row lookup
p.alarms.load_alarms_as_df(session) # SELECT * from alarm_records
p.state.set(session, "key", value)  # UI state key-value
p.state.get(session, "key")
p.state.delete(session, "key")
p.state.load_all(session)
p.cache.save_dataframe(df)          # fast DuckDB restore
p.cache.load_dataframe() -> pd.DataFrame | None
p.cache.has_dataframe() -> bool
p.cache.clear()
p.sync.append_outbox(session, ...)  # sync outbox events
p.sync.load_pending(session)
p.sync.mark_synced(session, ids)
```

All other modules (`ui`, `qml`, `adapters`, `services`, `core`) should never
import from `sqlalchemy` or `duckdb` directly. The import-linter contract at
`.importlinter` enforces this.

## Rules

1. **Only this package may import from `sqlalchemy` or `duckdb`.** Enforced
   by import-linter (`lint-imports`).
2. **Repositories raise typed exceptions** (`AlarmLoadError`, `StateError`,
   `SyncError`, `HashingError`, `CatalogError`, `EngineCreationError`,
   `AlarmCacheError`), never return `None` on failure.
3. **All public functions are pure** with respect to module state — they
   take a `Session` argument rather than creating one internally. This makes
   the repos trivial to test and to compose inside larger transactions.
4. **The facade is a singleton.** Call `Persistence.instance()` to get it.
   Use `Persistence.reset_instance()` only in tests; never reset it in
   production code paths.
5. **All paths in `alarm_cache.py` are derived from `STATE_DIR` lazily**,
   so tests can monkeypatch `STATE_DIR` without also patching
   `ALARM_DB_FILE`.

## Testing

The package's own test suite is in `tests/unit/services/persistence/`.

```bash
pytest tests/unit/services/persistence/ -v
```

Coverage of the new modules in this package — `alarm_cache.py` and
`facade.py` — is at 99% and 100% respectively. The remaining modules
(`engine`, `hashing`, `models`, `repos/*`) inherit coverage from the
upstream v1 tests and will be pushed to 100% as part of the v2/cutover
work.
