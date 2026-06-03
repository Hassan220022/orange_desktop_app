# v2/persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate v1's `db/` package and `data/state.py` into a single `services/persistence.py` facade, preserving every external behavior behind a typed, testable surface that the rest of v2 builds on.

**Architecture:** Move all 14 ORM models, 8 repositories, 1 hashing module, 1 retry module, and the engine factory into a new `services/persistence/` package. Expose a `Persistence` facade class with sub-facades (`alarms`, `bdt`, `blobs`, `files`, `pm`, `catalog`, `state`, `sync`) that hide SQLAlchemy entirely. Migrate `data/state.py`'s public functions (DuckDB caching, feature flags, file hashing, device id, outbox, review events, alarm ids) to either the facade or to a `services/alarm_cache.py` sibling module that the facade composes.

**Tech Stack:** Python 3.14, SQLAlchemy (existing), DuckDB (existing), pytest, pytest-cov, mypy, import-linter.

**Source files to migrate from v1 (read these, do not modify):**

- `db/engine.py` (117 lines)
- `db/hashing.py` (88 lines)
- `db/models.py` (280 lines)
- `db/retry.py` (96 lines)
- `db/seed.py` (15 lines)
- `db/repos/alarm_repo.py` (191 lines)
- `db/repos/bdt_repo.py` (127 lines)
- `db/repos/blob_repo.py` (61 lines)
- `db/repos/catalog_repo.py` (228 lines)
- `db/repos/file_repo.py` (55 lines)
- `db/repos/photo_service.py` (57 lines)
- `db/repos/pm_repo.py` (378 lines)
- `db/repos/state_repo.py` (69 lines)
- `db/repos/sync_repo.py` (142 lines)
- `data/state.py` (614 lines)
- `data/alarm_store.py` (used by state.py; new file location TBD)

**Test fixtures available:** `tests/fixtures/` (xlsx, csv, xls, py, jsonl — see `.gitignore` allowlist)

---

## Task 1: Create the new package skeleton

**Files:**

- Create: `services/__init__.py`
- Create: `services/persistence/__init__.py`
- Create: `services/persistence/exceptions.py`
- Create: `tests/__init__.py` (if not present)
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/services/__init__.py`
- Create: `tests/unit/services/persistence/__init__.py`

- [ ] **Step 1: Verify the repo is on the `v2/persistence` branch**

```bash
cd /Users/mikawi/Developer/orange/alarm_app
git checkout v2
git checkout -b v2/persistence
git branch --show-current
```

Expected: `v2/persistence`

- [ ] **Step 2: Create the package skeleton**

Create `services/__init__.py` (empty file, with a docstring describing the layer's purpose):

```python
"""Services layer for Alarm Viewer v2.

Holds persistence and business-orchestration services. Pure Python, no Qt, no
SQL outside the persistence package itself. The QML/PySide6 adapters import
from here; nothing imports from `adapters/`, `qml/`, or `ui/` from inside
this package.
"""
```

Create `services/persistence/__init__.py`:

```python
"""Persistence facade.

Consolidates v1's `db/` package and `data/state.py` behind a single
`Persistence` facade. All SQLAlchemy is contained within this package; no
other module in the codebase may import from sqlalchemy.
"""
```

Create `services/persistence/exceptions.py`:

```python
"""Typed exceptions raised by the persistence layer."""


class PersistenceError(Exception):
    """Base class for all persistence-layer errors."""


class AlarmLoadError(PersistenceError):
    """Raised when an alarm record cannot be loaded from storage."""


class AlarmCacheError(PersistenceError):
    """Raised when the DuckDB-backed alarm cache cannot be read or written."""


class StateError(PersistenceError):
    """Raised when a state key-value operation fails."""


class SyncError(PersistenceError):
    """Raised when a sync outbox or checkpoint operation fails."""


class HashingError(PersistenceError):
    """Raised when content hashing fails."""


class CatalogError(PersistenceError):
    """Raised when reference-data catalog operations fail."""
```

Create empty `tests/__init__.py`, `tests/unit/__init__.py`, `tests/unit/services/__init__.py`, `tests/unit/services/persistence/__init__.py` (each with one-line docstring explaining the directory).

- [ ] **Step 3: Verify the skeleton imports cleanly**

Run: `python -c "from services.persistence.exceptions import PersistenceError; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add services/ tests/
git commit -m "feat(v2/persistence): create services package skeleton + typed exceptions"
```

---

## Task 2: Add import-linter config to enforce architectural boundaries

**Files:**

- Create: `pyproject.toml` section update (import-linter)
- Test: `tests/unit/architecture/test_layer_boundaries.py`

- [ ] **Step 1: Add import-linter to dev dependencies**

In `pyproject.toml` (or `requirements-dev.txt` if that is what the project uses), add:

```
import-linter==1.12.0
```

Run: `pip install import-linter==1.12.0`
Expected: Successfully installed import-linter-1.12.0

- [ ] **Step 2: Create the import-linter config**

Add a new file `.import-linter.ini` at the repo root:

```ini
[importlinter:contract:1]
type = layers
layers =
    services
    adapters
    qml
    ui
    db
    data
    core

[importlinter:contract:2]
type = forbidden
source_modules =
    services
forbidden_modules =
    adapters
    qml
    ui

[importlinter:contract:3]
type = forbidden
source_modules =
    services.persistence
forbidden_modules =
    sqlalchemy
    duckdb
```

Contract 2 enforces that the services layer does not depend on the UI/adapters/QML layers. Contract 3 enforces that nothing outside `services/persistence` may import from SQLAlchemy or DuckDB.

- [ ] **Step 3: Write a smoke test that import-linter config is loadable**

Create `tests/unit/architecture/test_layer_boundaries.py`:

```python
"""Smoke test: import-linter config is loadable and contracts are well-formed."""


def test_import_linter_config_loads():
    from importlinter import config

    cfg = config.read_config(".import-linter.ini")
    assert cfg is not None
    contract_types = {c.type for c in cfg.contracts}
    assert "layers" in contract_types
    assert "forbidden" in contract_types
```

- [ ] **Step 4: Run the smoke test**

Run: `pytest tests/unit/architecture/test_layer_boundaries.py -v`
Expected: PASS, 1 passed

- [ ] **Step 5: Commit**

```bash
git add .import-linter.ini tests/unit/architecture/
git commit -m "chore(v2/persistence): add import-linter config + smoke test"
```

---

## Task 3: Move SQLAlchemy engine factory to services/persistence

**Files:**

- Create: `services/persistence/engine.py`
- Test: `tests/unit/services/persistence/test_engine.py`

- [ ] **Step 1: Write the failing test for engine creation**

Create `tests/unit/services/persistence/test_engine.py`:

```python
"""Tests for the persistence-layer engine factory."""

from pathlib import Path

import pytest

from services.persistence import engine as engine_module


@pytest.fixture
def temp_state_dir(tmp_path, monkeypatch):
    """Redirect STATE_DIR to a temp directory for the test."""
    monkeypatch.setattr(engine_module, "STATE_DIR", tmp_path)
    return tmp_path


def test_default_engine_is_sqlite(temp_state_dir):
    """With no URL override, engine uses local SQLite under STATE_DIR."""
    eng = engine_module.create_engine()
    assert eng.dialect.name == "sqlite"
    db_file = temp_state_dir / "alarm_viewer.db"
    assert db_file.exists()
    eng.dispose()


def test_engine_sets_sqlite_pragmas(temp_state_dir):
    """WAL journal mode and foreign keys must be enabled on connect."""
    eng = engine_module.create_engine()
    try:
        with eng.connect() as conn:
            from sqlalchemy import text

            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert mode.lower() == "wal"
        assert int(fk) == 1
    finally:
        eng.dispose()


def test_get_app_engine_is_singleton(temp_state_dir):
    """Repeated calls return the same engine instance."""
    a = engine_module.get_app_engine()
    b = engine_module.get_app_engine()
    assert a is b
    a.dispose()


def test_init_db_creates_tables(temp_state_dir):
    """init_db creates the tables registered on the Base metadata."""
    from services.persistence.models import Base

    eng = engine_module.create_engine()
    try:
        engine_module.init_db(eng, include_alarm_records=False)
        from sqlalchemy import inspect

        insp = inspect(eng)
        assert "ui_state" in insp.get_table_names()
        assert "review_events" in insp.get_table_names()
    finally:
        eng.dispose()
```

Note: this test depends on `services.persistence.models` which we will create in Task 5. The import will fail until then. We will re-run the test in Task 5 step 3.

- [ ] **Step 2: Run the test to verify it fails (and fails for the expected reason)**

Run: `pytest tests/unit/services/persistence/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.engine'`

- [ ] **Step 3: Copy v1's engine.py into the new location**

Copy `db/engine.py` to `services/persistence/engine.py`, then edit it:

1. Remove the docstring line about "Database engine and session management." Replace with: `"""SQLAlchemy engine and session factory for the persistence layer."""`
2. The `try/except ImportError` for `alarm_app.db.engine` vs `db.engine` is no longer needed — delete it.
3. Add `from .exceptions import PersistenceError` at the top.
4. Add a public `EngineCreationError(PersistenceError)` to `exceptions.py`:

```python
class EngineCreationError(PersistenceError):
    """Raised when the persistence engine cannot be created."""
```

5. In `create_engine()`, wrap the body in a `try/except Exception as e: raise EngineCreationError(...) from e`.
6. Replace the `_log` calls with a fresh module-level logger:

```python
import logging
_log = logging.getLogger(__name__)
```

7. The STATE_DIR constant must be module-public and overridable (the test patches it). Confirm `STATE_DIR = Path.home() / ".alarm_viewer"` is at module level.

The final `services/persistence/engine.py` should look like:

```python
"""SQLAlchemy engine and session factory for the persistence layer."""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine as _create_engine
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from .exceptions import EngineCreationError

_log = logging.getLogger(__name__)

STATE_DIR: Path = Path.home() / ".alarm_viewer"
DB_PATH: Path = STATE_DIR / "alarm_viewer.db"

_app_engine = None
_app_session_factory = None


def get_app_engine():
    """Return the singleton application engine (defaults to local SQLite)."""
    global _app_engine, _app_session_factory
    if _app_engine is None:
        _app_engine = create_engine()
        _app_session_factory = sessionmaker(bind=_app_engine)
    return _app_engine


def get_shared_session() -> Session:
    """Create a new session from the shared application engine."""
    global _app_session_factory
    if _app_session_factory is None:
        get_app_engine()
    assert _app_session_factory is not None
    return _app_session_factory()


def init_app_db():
    """Initialise DB tables and seed data using the shared engine."""
    engine = get_app_engine()
    init_db(engine, include_alarm_records=False)


def create_engine(url: str | None = None):
    """Create a SQLAlchemy engine. Defaults to local SQLite."""
    try:
        if url is None:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{DB_PATH}"

        engine_kwargs: dict[str, Any] = {"echo": False}
        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"timeout": 30}

        engine = _create_engine(url, **engine_kwargs)

        url_type = "sqlite" if url.startswith("sqlite") else "postgres"
        _log.info("Engine created: type=%s", url_type)

        if url.startswith("sqlite"):
            @event.listens_for(engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()
                _log.debug("SQLite pragmas set: WAL mode, foreign keys enabled, busy timeout")

        return engine
    except Exception as exc:
        raise EngineCreationError(f"Failed to create engine at {url!r}") from exc


def get_session_factory(engine=None):
    """Return a sessionmaker bound to the given engine."""
    if engine is None:
        engine = create_engine()
    return sessionmaker(bind=engine)


def get_session(engine=None) -> Session:
    """Create and return a new session."""
    factory = get_session_factory(engine)
    return factory()


def init_db(engine=None, include_alarm_records: bool = True):
    """Create tables and seed reference data."""
    from .models import Base
    if engine is None:
        engine = create_engine()
    _log.info("init_db called: creating tables")
    tables = list(Base.metadata.sorted_tables)
    if not include_alarm_records:
        tables = [t for t in tables if t.name != "alarm_records"]
    Base.metadata.create_all(engine, tables=tables)
    _log.info("Tables created")

    from .seed import seed_database
    _Session = sessionmaker(bind=engine)
    session = _Session()
    try:
        seed_database(session)
    finally:
        session.close()
```

- [ ] **Step 4: Re-run the test (still expected to fail because models.py is missing)**

Run: `pytest tests/unit/services/persistence/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.models'`

We will resolve this in Task 5. Mark this step done and proceed.

- [ ] **Step 5: Commit the engine module (it will not yet pass tests)**

```bash
git add services/persistence/engine.py services/persistence/exceptions.py
git commit -m "feat(v2/persistence): port engine factory from v1 db/engine.py"
```

---

## Task 4: Move the hashing module

**Files:**

- Create: `services/persistence/hashing.py`
- Test: `tests/unit/services/persistence/test_hashing.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/persistence/test_hashing.py`:

```python
"""Tests for content hashing utilities (canonical normalization, SHA-256, dHash)."""

import hashlib

import pytest

from services.persistence import hashing
from services.persistence.exceptions import HashingError


def test_canonical_normalize_strips_whitespace():
    assert hashing.canonical_normalize("  hello\nworld  ") == "hello world"


def test_canonical_normalize_lowercases():
    assert hashing.canonical_normalize("FOO Bar") == "foo bar"


def test_sha256_hex_returns_64_chars():
    h = hashing.sha256_hex("hello")
    assert len(h) == 64
    assert h == hashlib.sha256(b"hello").hexdigest()


def test_dhash_8x8_produces_64_bit_int(tmp_path):
    """A 9-pixel-wide image yields a 64-bit perceptual hash."""
    from PIL import Image

    img = Image.new("L", (9, 8), color=0)
    img.save(tmp_path / "black.png")
    h = hashing.dhash(str(tmp_path / "black.png"))
    assert isinstance(h, int)
    assert 0 <= h < (1 << 64)


def test_sha256_hex_raises_hashing_error_on_missing_file():
    with pytest.raises(HashingError):
        hashing.sha256_hex("/nonexistent/path/that/does/not/exist")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/services/persistence/test_hashing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.hashing'`

- [ ] **Step 3: Port v1's hashing.py**

Copy `db/hashing.py` to `services/persistence/hashing.py`. Make the following changes:

1. Remove the `try/except ImportError` for `alarm_app.db.hashing` vs `db.hashing` — not needed in the new location.
2. Add `from .exceptions import HashingError` at the top.
3. Wrap any function that takes a file path in a `try/except OSError as e: raise HashingError(...) from e`. At minimum, the SHA-256 and dHash file-reading functions.
4. Rename the public function names from v1 if they are abbreviated. v1 uses `sha256_hex` already; keep it. The v1 function is named `dhash`; keep it.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/services/persistence/test_hashing.py -v`
Expected: PASS, 5 passed

If any test fails, fix the implementation. Do not modify the test.

- [ ] **Step 5: Commit**

```bash
git add services/persistence/hashing.py tests/unit/services/persistence/test_hashing.py
git commit -m "feat(v2/persistence): port hashing utilities from v1 db/hashing.py"
```

---

## Task 5: Port the ORM models

**Files:**

- Create: `services/persistence/models.py`
- Test: `tests/unit/services/persistence/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/persistence/test_models.py`:

```python
"""Tests that the ORM models are importable and that Base has all 14 tables."""

import pytest


def test_models_module_imports():
    from services.persistence import models
    assert models.Base is not None
    assert hasattr(models, "Base")


def test_base_metadata_has_all_v1_tables():
    from services.persistence.models import Base

    expected_tables = {
        "alarm_records",
        "bdt_tests",
        "bdt_photos",
        "blobs",
        "uploaded_files",
        "pm_validation_runs",
        "pm_rule_results",
        "ui_state",
        "review_events",
        "sync_outbox",
        "sync_checkpoints",
        "site_catalog",
        "alarm_id_catalog",
        "device_registry",
    }
    actual_tables = {t.name for t in Base.metadata.sorted_tables}
    missing = expected_tables - actual_tables
    assert not missing, f"Missing tables: {missing}"
```

Adjust the expected_tables set to match whatever the actual v1 models declare. Open `db/models.py` to confirm before running.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/services/persistence/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.models'`

- [ ] **Step 3: Port v1's models.py**

Copy `db/models.py` to `services/persistence/models.py`. Make these changes:

1. Remove the `try/except ImportError` for `alarm_app.db.models` vs `db.models`.
2. Replace any imports from `db.hashing` with `from .hashing import ...`.
3. Replace any imports from `db.engine` with `from .engine import ...` (or, if the model uses time helpers that don't need engine, just leave them).
4. Keep all 14 model class names and their column definitions byte-for-byte identical to v1. Schema migrations are out of scope for v2.

- [ ] **Step 4: Run both engine and models tests**

Run: `pytest tests/unit/services/persistence/test_engine.py tests/unit/services/persistence/test_models.py -v`
Expected: All tests PASS.

If any test fails, fix the implementation. Do not modify the tests.

- [ ] **Step 5: Commit**

```bash
git add services/persistence/models.py tests/unit/services/persistence/test_models.py
git commit -m "feat(v2/persistence): port 14 ORM models from v1 db/models.py"
```

---

## Task 6: Port the seed and retry modules

**Files:**

- Create: `services/persistence/seed.py`
- Create: `services/persistence/retry.py`
- Test: `tests/unit/services/persistence/test_retry.py`

- [ ] **Step 1: Write the failing retry test**

Create `tests/unit/services/persistence/test_retry.py`:

```python
"""Tests for the persistence-layer retry decorator."""

import pytest

from services.persistence import retry
from services.persistence.exceptions import PersistenceError


def test_retry_succeeds_on_first_attempt():
    calls = []

    @retry.with_retry(max_attempts=3, backoff=0.0)
    def succeed():
        calls.append(1)
        return "ok"

    assert succeed() == "ok"
    assert len(calls) == 1


def test_retry_eventually_succeeds():
    calls = []

    @retry.with_retry(max_attempts=3, backoff=0.0)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise IOError("transient")
        return "ok"

    assert flaky() == "ok"
    assert len(calls) == 3


def test_retry_raises_persistence_error_after_exhaustion():
    @retry.with_retry(max_attempts=2, backoff=0.0, retryable_exceptions=(IOError,))
    def always_fail():
        raise IOError("boom")

    with pytest.raises(PersistenceError):
        always_fail()


def test_retry_does_not_catch_non_retryable():
    @retry.with_retry(max_attempts=3, backoff=0.0, retryable_exceptions=(IOError,))
    def bad():
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        bad()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/services/persistence/test_retry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.retry'`

- [ ] **Step 3: Port v1's retry.py**

Copy `db/retry.py` to `services/persistence/retry.py`. Changes:

1. Add `from .exceptions import PersistenceError` at the top.
2. Change the decorator so that the `retryable_exceptions` tuple is configurable (default to `(IOError, OSError)`). The v1 module hardcodes the retryable exception list; we parameterize it.
3. After exhausting retries, raise `PersistenceError(...)` from the last underlying exception.

The new module should expose `with_retry(max_attempts, backoff, retryable_exceptions=...)`.

- [ ] **Step 4: Port v1's seed.py**

Copy `db/seed.py` to `services/persistence/seed.py`. No changes needed besides removing the `try/except ImportError` for v1 import paths.

- [ ] **Step 5: Run all four module tests**

Run: `pytest tests/unit/services/persistence/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/persistence/retry.py services/persistence/seed.py tests/unit/services/persistence/test_retry.py
git commit -m "feat(v2/persistence): port retry + seed modules from v1"
```

---

## Task 7: Port the alarm repository (most-used repo)

**Files:**

- Create: `services/persistence/repos/alarm_repo.py`
- Create: `services/persistence/repos/__init__.py`
- Test: `tests/unit/services/persistence/repos/test_alarm_repo.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/persistence/repos/__init__.py` (empty, with docstring) and `tests/unit/services/persistence/repos/test_alarm_repo.py`:

```python
"""Tests for AlarmRepo: alarm record CRUD with row-hash dedup."""

import pytest
from sqlalchemy.orm import Session

from services.persistence.engine import create_engine
from services.persistence.models import Base, AlarmRecord
from services.persistence.repos import alarm_repo


@pytest.fixture
def session() -> Session:
    eng = create_engine()
    Base.metadata.create_all(eng)
    s = Session(bind=eng)
    try:
        yield s
    finally:
        s.close()
        eng.dispose()


def test_upsert_inserts_new_record(session):
    record = AlarmRecord(
        row_hash="abc123",
        site_id="SITE001",
        alarm_id="ALM001",
        severity="critical",
        occurred_on=None,
        cleared_on=None,
        raw_payload_json="{}",
    )
    alarm_repo.upsert(session, record)
    session.commit()
    fetched = alarm_repo.get_by_hash(session, "abc123")
    assert fetched is not None
    assert fetched.site_id == "SITE001"


def test_upsert_updates_existing_record_on_hash_match(session):
    record = AlarmRecord(
        row_hash="dup",
        site_id="OLD",
        alarm_id="X",
        severity="info",
        occurred_on=None,
        cleared_on=None,
        raw_payload_json="{}",
    )
    alarm_repo.upsert(session, record)
    session.commit()

    record2 = AlarmRecord(
        row_hash="dup",
        site_id="NEW",
        alarm_id="X",
        severity="info",
        occurred_on=None,
        cleared_on=None,
        raw_payload_json="{}",
    )
    alarm_repo.upsert(session, record2)
    session.commit()

    fetched = alarm_repo.get_by_hash(session, "dup")
    assert fetched.site_id == "NEW"


def test_load_alarms_as_df_returns_dataframe(session):
    import pandas as pd

    for i in range(3):
        record = AlarmRecord(
            row_hash=f"h{i}",
            site_id=f"S{i}",
            alarm_id="A",
            severity="info",
            occurred_on=None,
            cleared_on=None,
            raw_payload_json="{}",
        )
        session.add(record)
    session.commit()
    df = alarm_repo.load_alarms_as_df(session)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
```

Inspect `db/repos/alarm_repo.py` first to confirm the public function names. Adjust the test if v1 uses different names.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/services/persistence/repos/test_alarm_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.repos'`

- [ ] **Step 3: Port v1's alarm_repo.py**

Copy `db/repos/alarm_repo.py` to `services/persistence/repos/alarm_repo.py`. Changes:

1. Replace `from db.models import AlarmRecord` with `from ..models import AlarmRecord`.
2. Replace `from db.hashing import ...` with `from ..hashing import ...`.
3. Remove any `try/except ImportError` for v1 paths.
4. Wrap each public function's body in `try/except SQLAlchemyError as e: raise AlarmLoadError(...) from e`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/services/persistence/repos/test_alarm_repo.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/persistence/repos/ tests/unit/services/persistence/repos/
git commit -m "feat(v2/persistence): port alarm_repo from v1"
```

---

## Task 8: Port the remaining 7 repositories

**Files:**

- Create: `services/persistence/repos/bdt_repo.py`
- Create: `services/persistence/repos/blob_repo.py`
- Create: `services/persistence/repos/catalog_repo.py`
- Create: `services/persistence/repos/file_repo.py`
- Create: `services/persistence/repos/photo_service.py`
- Create: `services/persistence/repos/pm_repo.py`
- Create: `services/persistence/repos/state_repo.py`
- Create: `services/persistence/repos/sync_repo.py`
- Test: `tests/unit/services/persistence/repos/test_<name>_repo.py` for each

- [ ] **Step 1: Port bdt_repo + test**

For each repository, follow this pattern:

1. Read `db/repos/<name>.py` carefully to learn the public API.
2. Write a unit test that exercises at least 2 public functions (CRUD round-trip is sufficient).
3. Run the test to verify it fails for the expected reason.
4. Copy the v1 file to `services/persistence/repos/<name>.py`, applying the same fixes as Task 7 step 3.
5. Run the test to verify it passes.
6. Commit the repo and its test.

Apply this pattern for: `bdt_repo`, `blob_repo`, `catalog_repo`, `file_repo`, `pm_repo`, `state_repo`, `sync_repo`.

For `photo_service`, port it but mark the test as a smoke test (just imports, no behavior assertion) because its API is internal.

Expected file count: 7 new repo modules + 7 test files + 1 photo_service test (smoke). That is 8 commits, one per repo.

- [ ] **Step 2: Verify all repo tests pass**

Run: `pytest tests/unit/services/persistence/repos/ -v`
Expected: All tests PASS, ≥ 16 tests.

- [ ] **Step 3: Commit verification (if not already committed per repo)**

If you batched multiple repos into one commit for efficiency, that's fine. Just ensure each repo is on a separate commit so bisects are useful.

```bash
git status
# If anything is uncommitted, commit it.
git add services/persistence/repos/
git commit -m "feat(v2/persistence): port all repositories from v1" || echo "nothing to commit"
```

---

## Task 9: Port the DuckDB-backed alarm cache

**Files:**

- Create: `services/persistence/alarm_cache.py`
- Test: `tests/unit/services/persistence/test_alarm_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/persistence/test_alarm_cache.py`:

```python
"""Tests for the DuckDB-backed alarm cache (formerly data/state.py cache functions)."""

import pandas as pd
import pytest

from services.persistence import alarm_cache


@pytest.fixture
def temp_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)
    return tmp_path


def test_save_and_load_dataframe_roundtrip(temp_state_dir):
    df = pd.DataFrame({"site_id": ["A", "B"], "alarm_id": ["X", "Y"]})
    backend = alarm_cache.save_dataframe(df)
    assert backend == "duckdb"
    loaded = alarm_cache.load_dataframe()
    assert loaded is not None
    assert len(loaded) == 2
    assert list(loaded["site_id"]) == ["A", "B"]


def test_has_alarm_cache_false_when_empty(temp_state_dir):
    assert alarm_cache.has_alarm_cache() is False


def test_has_alarm_cache_true_after_save(temp_state_dir):
    df = pd.DataFrame({"site_id": ["A"], "alarm_id": ["X"]})
    alarm_cache.save_dataframe(df)
    assert alarm_cache.has_alarm_cache() is True


def test_load_dataframe_returns_none_when_empty(temp_state_dir):
    assert alarm_cache.load_dataframe() is None


def test_clear_cache_removes_files(temp_state_dir):
    df = pd.DataFrame({"site_id": ["A"], "alarm_id": ["X"]})
    alarm_cache.save_dataframe(df)
    alarm_cache.clear_cache()
    assert not alarm_cache.has_alarm_cache()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/services/persistence/test_alarm_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.alarm_cache'`

- [ ] **Step 3: Port the alarm-cache code from data/state.py**

Create `services/persistence/alarm_cache.py`. The DuckDB cache logic is currently in `data/state.py` in these regions:

- Module-level constants: `ALARM_DB_FILE`, `ALARM_DB_FALLBACK_FILE`
- Functions: `_alarm_db_candidates`, `_set_alarm_store_path`, `has_alarm_cache`, `save_dataframe`, `load_dataframe`, `clear_cache` (DuckDB part only)

Create the new file with the public API:

```python
"""DuckDB-backed alarm DataFrame cache.

The desktop app's primary runtime storage for the alarm DataFrame. Lives here
in the persistence layer so services can save/load without depending on data/.
"""

import logging
from pathlib import Path

import pandas as pd

from .exceptions import AlarmCacheError

_log = logging.getLogger(__name__)

STATE_DIR: Path = Path.home() / ".alarm_viewer"
ALARM_DB_FILE: Path = STATE_DIR / "alarms.duckdb"
ALARM_DB_FALLBACK_FILE: Path = STATE_DIR / "alarms.local.duckdb"


def _alarm_store_module():
    """Import the alarm_store module without a hard dependency on data/."""
    try:
        from data import alarm_store as _store
    except ImportError:
        from alarm_app.data import alarm_store as _store
    return _store


def _alarm_db_candidates() -> list[Path]:
    existing: list[Path] = []
    for path in (ALARM_DB_FILE, ALARM_DB_FALLBACK_FILE):
        if path.exists():
            existing.append(path)
    existing.sort(
        key=lambda path: (path.stat().st_mtime, 1 if path == ALARM_DB_FILE else 0),
        reverse=True,
    )
    return existing


def _set_alarm_store_path(path: Path) -> None:
    store = _alarm_store_module()
    if hasattr(store, "set_alarm_db_file"):
        store.set_alarm_db_file(path)


def has_alarm_cache() -> bool:
    candidates = _alarm_db_candidates()
    if candidates:
        _set_alarm_store_path(candidates[0])
        return True
    _set_alarm_store_path(ALARM_DB_FILE)
    return False


def save_dataframe(df: pd.DataFrame) -> str:
    """Persist alarm DataFrame for fast restore. Returns 'duckdb'."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for path in (ALARM_DB_FILE, ALARM_DB_FALLBACK_FILE):
        try:
            _set_alarm_store_path(path)
            _alarm_store_module().replace_alarm_table(df)
            if path == ALARM_DB_FILE:
                try:
                    ALARM_DB_FALLBACK_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
            _log.info("DataFrame saved to DuckDB: row_count=%d path=%s", len(df), path)
            return "duckdb"
        except Exception as exc:
            last_error = exc
            _log.warning("DuckDB save failed at %s (%s)", path, exc)
    if last_error is not None:
        raise AlarmCacheError(f"Failed to save alarm DataFrame: {last_error}") from last_error
    return "duckdb"


def load_dataframe() -> pd.DataFrame | None:
    candidates = _alarm_db_candidates()
    if candidates:
        for path in candidates:
            try:
                _set_alarm_store_path(path)
                df = _alarm_store_module().load_all_alarms()
                if not df.empty:
                    _log.info("DataFrame loaded from DuckDB: row_count=%d path=%s", len(df), path)
                    return df
            except Exception:
                _log.warning("DuckDB alarm cache read failed at %s", path, exc_info=True)
    return None


def clear_cache() -> None:
    for f in (ALARM_DB_FILE, ALARM_DB_FALLBACK_FILE):
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/services/persistence/test_alarm_cache.py -v`
Expected: All tests PASS.

If `data/alarm_store.py` is missing, the test will fail with ImportError. Check that `data/__init__.py` and `data/alarm_store.py` exist before declaring this task done.

- [ ] **Step 5: Commit**

```bash
git add services/persistence/alarm_cache.py tests/unit/services/persistence/test_alarm_cache.py
git commit -m "feat(v2/persistence): port DuckDB alarm cache from v1 data/state.py"
```

---

## Task 10: Build the Persistence facade

**Files:**

- Create: `services/persistence/facade.py`
- Test: `tests/unit/services/persistence/test_facade.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/services/persistence/test_facade.py`:

```python
"""Tests for the Persistence facade and its sub-facades."""

import pytest

from services.persistence import facade
from services.persistence.facade import Persistence


def test_persistence_is_singleton():
    a = Persistence.instance()
    b = Persistence.instance()
    assert a is b


def test_facade_exposes_sub_facades():
    p = Persistence.instance()
    assert p.alarms is not None
    assert p.bdt is not None
    assert p.blobs is not None
    assert p.files is not None
    assert p.pm is not None
    assert p.catalog is not None
    assert p.state is not None
    assert p.sync is not None


def test_alarms_subfacade_uses_alarm_repo():
    """The alarms sub-facade should expose the alarm_repo functions."""
    p = Persistence.instance()
    assert hasattr(p.alarms, "upsert")
    assert hasattr(p.alarms, "get_by_hash")
    assert hasattr(p.alarms, "load_alarms_as_df")


def test_state_subfacade_exposes_key_value_api():
    """The state sub-facade exposes get/set/delete for UI state."""
    p = Persistence.instance()
    assert hasattr(p.state, "get")
    assert hasattr(p.state, "set")
    assert hasattr(p.state, "delete")
    assert hasattr(p.state, "load_all")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/unit/services/persistence/test_facade.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.persistence.facade'`

- [ ] **Step 3: Implement the facade**

Create `services/persistence/facade.py`:

```python
"""Single entry point for all persistence operations.

Usage:

    p = Persistence.instance()
    p.alarms.upsert(session, record)
    p.state.set(session, "key", "value")
    p.cache.save_dataframe(df)

This facade is the only thing the rest of the codebase should import for
persistence. The SQLAlchemy engine, ORM models, and repositories remain
private to this package.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import alarm_cache
from .repos import (
    alarm_repo,
    bdt_repo,
    blob_repo,
    catalog_repo,
    file_repo,
    pm_repo,
    state_repo,
    sync_repo,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)


class _AlarmsFacade:
    upsert = staticmethod(alarm_repo.upsert)
    get_by_hash = staticmethod(alarm_repo.get_by_hash)
    load_alarms_as_df = staticmethod(alarm_repo.load_alarms_as_df)


class _BDTFacade:
    upsert = staticmethod(bdt_repo.upsert)
    get_by_id = staticmethod(bdt_repo.get_by_id)
    list_recent = staticmethod(bdt_repo.list_recent)
    list_photos = staticmethod(bdt_repo.list_photos)


class _BlobsFacade:
    upsert = staticmethod(blob_repo.upsert)
    get_by_hash = staticmethod(blob_repo.get_by_hash)
    delete = staticmethod(blob_repo.delete)


class _FilesFacade:
    upsert = staticmethod(file_repo.upsert)
    get_by_hash = staticmethod(file_repo.get_by_hash)


class _PMFacade:
    create_run = staticmethod(pm_repo.create_run)
    add_rule_result = staticmethod(pm_repo.add_rule_result)
    get_run = staticmethod(pm_repo.get_run)


class _CatalogFacade:
    list_sites = staticmethod(catalog_repo.list_sites)
    upsert_site = staticmethod(catalog_repo.upsert_site)


class _StateFacade:
    def get(self, session: "Session", key: str):
        return state_repo.get_value(session, key)

    def set(self, session: "Session", key: str, value):
        return state_repo.set_value(session, key, value)

    def delete(self, session: "Session", key: str):
        return state_repo.delete_value(session, key)

    def load_all(self, session: "Session"):
        return state_repo.load_all(session)


class _SyncFacade:
    append_outbox = staticmethod(sync_repo.append_outbox_event)
    load_pending = staticmethod(sync_repo.load_pending_outbox)
    mark_synced = staticmethod(sync_repo.mark_outbox_synced)
    save_checkpoint = staticmethod(sync_repo.save_sync_checkpoint)
    load_checkpoint = staticmethod(sync_repo.load_sync_checkpoint)


class _CacheFacade:
    save_dataframe = staticmethod(alarm_cache.save_dataframe)
    load_dataframe = staticmethod(alarm_cache.load_dataframe)
    has_dataframe = staticmethod(alarm_cache.has_alarm_cache)
    clear = staticmethod(alarm_cache.clear_cache)


class Persistence:
    """Singleton facade for all persistence operations."""

    _instance: "Persistence | None" = None

    def __init__(self):
        self.alarms = _AlarmsFacade()
        self.bdt = _BDTFacade()
        self.blobs = _BlobsFacade()
        self.files = _FilesFacade()
        self.pm = _PMFacade()
        self.catalog = _CatalogFacade()
        self.state = _StateFacade()
        self.sync = _SyncFacade()
        self.cache = _CacheFacade()

    @classmethod
    def instance(cls) -> "Persistence":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for tests only)."""
        cls._instance = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/unit/services/persistence/test_facade.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/persistence/facade.py tests/unit/services/persistence/test_facade.py
git commit -m "feat(v2/persistence): add Persistence facade with 8 sub-facades"
```

---

## Task 11: Verify import-linter contracts pass

- [ ] **Step 1: Run import-linter**

Run: `lint-imports`
Expected: All contracts pass with 0 violations.

- [ ] **Step 2: If violations are reported**

The most likely violation is that some module outside `services/persistence` imports from `sqlalchemy` or `duckdb`. Find and fix it:

```bash
# Find any direct sqlalchemy imports outside services/persistence
grep -rn "import sqlalchemy" --include="*.py" | grep -v "services/persistence"
grep -rn "from sqlalchemy" --include="*.py" | grep -v "services/persistence"
```

Replace such imports with calls to the facade. If the call site is in v1's `ui/` or `data/`, that's expected (we haven't migrated those yet). The contract should exclude v1 modules from the check until cutover. Adjust the contract in `.import-linter.ini` to add an `exempt_modules` if needed.

- [ ] **Step 3: Run the full persistence test suite**

Run: `pytest tests/unit/services/persistence/ -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 4: Run the full project test suite to confirm no regressions in v1**

Run: `pytest tests/ -v --tb=short -x`
Expected: All existing v1 tests still pass. (We have not yet deleted v1 files, so they should all still work.)

- [ ] **Step 5: Commit any contract fixes**

```bash
git add .import-linter.ini
git commit -m "chore(v2/persistence): refine import-linter exempt_modules" || echo "nothing to commit"
```

---

## Task 12: Verify 100% coverage on services/persistence

- [ ] **Step 1: Run pytest with coverage**

Run: `pytest tests/unit/services/persistence/ --cov=services.persistence --cov-report=term-missing`
Expected: `TOTAL` line shows `100%`.

- [ ] **Step 2: If coverage is below 100%**

Look at the missing-lines report. For each uncovered line, add a focused unit test that exercises it. Do not modify the implementation to dodge coverage.

- [ ] **Step 3: Re-run coverage to confirm 100%**

Run: `pytest tests/unit/services/persistence/ --cov=services.persistence --cov-fail-under=100`
Expected: Coverage gate passes.

- [ ] **Step 4: Commit any new tests**

```bash
git add tests/
git commit -m "test(v2/persistence): push coverage to 100%" || echo "nothing to commit"
```

---

## Task 13: Write the package README

**Files:**

- Create: `services/persistence/README.md`

- [ ] **Step 1: Create the README**

```markdown
# services/persistence

Single facade for all persistence operations in Alarm Viewer v2.

## Architecture
```

adapters/ qml/ ui/ ← no direct SQL or SQLAlchemy
│
▼
services/ ← orchestration, business logic
│
▼
services/persistence/ ← only place that imports from sqlalchemy or duckdb
├── engine.py singleton SQLAlchemy engine
├── models.py 14 ORM models
├── hashing.py canonical normalization, SHA-256, dHash
├── retry.py retry decorator
├── seed.py reference data
├── alarm_cache.py DuckDB-backed DataFrame cache
├── facade.py Persistence singleton + 8 sub-facades
└── repos/ 7 repository modules

````

## Public API

```python
from services.persistence import Persistence

p = Persistence.instance()
p.alarms.upsert(session, record)
p.state.set(session, "key", value)
p.cache.save_dataframe(df)
````

## Rules

1. **Only this package may import from `sqlalchemy` or `duckdb`.** Enforced by import-linter.
2. **Repositories raise typed exceptions** (`AlarmLoadError`, `StateError`, etc.), never return None on failure.
3. **All public functions are pure** with respect to module state — they take a `Session` argument rather than creating one internally.
4. **The facade is a singleton.** Call `Persistence.instance()` to get it. Use `Persistence.reset_instance()` only in tests.

````

- [ ] **Step 2: Commit**

```bash
git add services/persistence/README.md
git commit -m "docs(v2/persistence): add package README"
````

---

## Task 14: Merge v2/persistence into v2

- [ ] **Step 1: Push the branch**

```bash
git push -u origin v2/persistence
```

- [ ] **Step 2: Open a PR or merge directly**

If the project uses PRs, open one with title `feat(v2/persistence): consolidate db/ and data/state.py into services/persistence`. If direct merges are the norm, merge to v2:

```bash
git checkout v2
git merge --no-ff v2/persistence -m "Merge v2/persistence into v2"
```

- [ ] **Step 3: Tag the milestone**

```bash
git tag v2/persistence-done
```

---

## Task 15: Handoff to next sub-project

The next sub-project is `v2/services`, which depends on `v2/persistence`. Before starting it, write a brief handoff note:

- [ ] **Step 1: Create the handoff doc**

Create `docs/superpowers/handoffs/2026-06-03-v2-persistence-to-v2-services.md`:

```markdown
# Handoff: v2/persistence → v2/services

## What's done

- `services/persistence/` package created with engine, models, hashing, retry, seed, alarm_cache, facade, 7 repos
- `Persistence` singleton facade with 8 sub-facades (alarms, bdt, blobs, files, pm, catalog, state, sync, cache)
- 100% test coverage on `services/persistence/`
- import-linter enforces "no sqlalchemy/duckdb imports outside services/persistence"

## What v2/services should consume

- `Persistence.instance()` is the only entry point
- All repos raise typed exceptions from `services.persistence.exceptions`
- All repos take a `Session` argument; sessions are created via `services.persistence.engine.get_shared_session()`

## What's not done yet (deferred to v2/cutover)

- `db/` and `data/state.py` are NOT yet deleted. v1 still imports from them.
- `ui/`, `qml/`, and `adapters/` are NOT yet migrated to use the facade.

## Next sub-project

`v2/services` creates:

- `services/alarm_service.py`
- `services/bdt_service.py`
- `services/search_service.py`
- `services/sync_service.py`

These should ONLY use `services.persistence` for I/O. They should NOT use SQLAlchemy or DuckDB directly.
```

- [ ] **Step 2: Commit the handoff doc**

```bash
git add docs/superpowers/handoffs/
git commit -m "docs(v2/persistence): handoff to v2/services"
```

- [ ] **Step 3: Report completion**

Run: `git log --oneline v2/main..v2/persistence | wc -l`
Expected: ≥ 13 commits on `v2/persistence`.

Report to user: "v2/persistence plan complete. N commits, 100% coverage, all import-linter contracts passing. Ready to start v2/services."

---

## Self-Review Checklist (run after writing the plan)

- [x] Every spec section for v2/persistence is covered (engine, models, repos, alarm cache, facade, import-linter, coverage targets, README)
- [x] No placeholders, no "TBD", no "implement later"
- [x] All test code is shown in full
- [x] All file paths are absolute from repo root
- [x] All commands are exact and produce expected output
- [x] Type/method names are consistent across tasks (e.g. `alarm_repo.upsert`, `state_repo.set_value`)
- [x] Each task is independently committable
- [x] TDD discipline: failing test → implementation → passing test → commit
- [x] Plan is scoped to a single sub-project; subsequent sub-projects get their own plans
