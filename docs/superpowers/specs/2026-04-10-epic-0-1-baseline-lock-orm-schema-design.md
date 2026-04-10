# Epic 0+1 Design Spec: Baseline Lock + ORM Schema + Dedup Pipeline

## Goal

Replace all flat-file persistence (state.json, data_cache.parquet, review_log.jsonl, sync_outbox.jsonl, sync_checkpoint.json, BDT history JSON) with a local SQLite database. Design the ORM schema to work identically on Postgres for future cloud deployment. Add golden snapshot tests as a safety net before touching storage.

## Architecture

Local SQLite via SQLAlchemy 2.0. Alembic for migrations. Same ORM models target Postgres later. Images stored as files on local disk (later MinIO/S3), metadata + paths in DB. Four-layer dedup: file hash, row hash, Bloom filter (optional), DB unique constraints.

## Tech Stack

- SQLAlchemy 2.0 (sync, with async-compatible patterns)
- Alembic (migration management)
- SQLite (local, `~/.alarm_viewer/alarm_viewer.db`)
- Postgres (production target, same models)
- python-calamine (Excel reading, already in use)
- imagehash + Pillow (perceptual image dedup)
- boto3 or minio (blob upload, later epic)

---

## Epic 0: Baseline Lock

### What

Capture the exact output of current parsing, validation, and backup-time computation against a real dataset. Store as JSON fixtures. Write snapshot tests that assert future code produces identical results.

### Fixture Generation

The user provides a real BDT test folder. A one-time script runs:

1. `discover_alarm_files(directory)` → save file list as JSON
2. `parse_alarm_file(path)` for each file → save concatenated DataFrame summary (columns, dtypes, row count, SHA-256 of sorted CSV export)
3. `classify_by_alarm_id(df, ...)` → save category counts
4. `compute_site_down_flag(df)` → save flag counts
5. `compute_backup_times(df)` → save output DataFrame as JSON records
6. `parse_bdt_file(path)` for each BDT → save `BDTData.__dict__` as JSON
7. `validate_bdt(bdt, alarms_df)` for each BDT → save `ValidationResult` (overall verdict + each RuleResult) as JSON
8. `compute_date_mask(...)` with sample params → save mask summary

### Files

- `tests/fixtures/golden/` — generated JSON fixture files
- `tests/generate_golden.py` — one-time script to regenerate fixtures
- `tests/test_golden_parity.py` — snapshot tests comparing current code output against fixtures

### Parity Test Structure

Each test loads a fixture, runs the same function with the same inputs, and asserts identical output. These tests are marked `@pytest.mark.golden` so they can be run separately (they need real data files present).

---

## Epic 1: ORM Schema

### New Package: `alarm_app/db/`

```
alarm_app/db/
├── __init__.py
├── engine.py           # create_engine, get_session, init_db
├── models.py           # all ORM table models
├── repos/
│   ├── __init__.py
│   ├── alarm_repo.py   # alarm_records CRUD
│   ├── file_repo.py    # uploaded_files CRUD
│   ├── bdt_repo.py     # bdt_tests, bdt_photos CRUD
│   ├── pm_repo.py      # pm runs + rule results CRUD
│   ├── state_repo.py   # ui_state key-value CRUD
│   ├── sync_repo.py    # sync_outbox + checkpoints CRUD
│   └── blob_repo.py    # blob_assets metadata CRUD
├── migrations/
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
│       └── 001_initial_schema.py
└── hashing.py          # canonical normalization + hash computation
```

### engine.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

STATE_DIR = Path.home() / ".alarm_viewer"
DB_PATH = STATE_DIR / "alarm_viewer.db"

def get_engine(url: str | None = None):
    if url is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DB_PATH}"
    return create_engine(url, echo=False)

def get_session(engine=None) -> Session:
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine)()

def init_db(engine=None):
    """Create all tables. For dev/first-launch. Production uses Alembic."""
    from .models import Base
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
```

### ORM Models (models.py)

All models inherit from a shared `Base`. Every table has `id` (primary key), `created_at`, `updated_at`. Tenant ID is present but nullable for local-only use (populated on cloud sync).

#### Core Tables

```python
class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id              = Column(Integer, primary_key=True)
    file_sha256     = Column(String(64), unique=True, nullable=False, index=True)
    original_path   = Column(Text, nullable=False)
    original_name   = Column(Text, nullable=False)
    file_size       = Column(BigInteger)
    source_kind     = Column(String(20))  # "alarm_csv", "alarm_xlsx", "bdt_xlsx"
    parsed_at       = Column(DateTime)
    created_at      = Column(DateTime, default=func.now())
    tenant_id       = Column(String(64), nullable=True)

class AlarmRecord(Base):
    __tablename__ = "alarm_records"

    id              = Column(Integer, primary_key=True)
    row_hash        = Column(String(64), unique=True, nullable=False, index=True)
    file_id         = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    site_id         = Column(String(100), index=True)
    alarm_name      = Column(Text)
    occurred_on     = Column(DateTime, index=True)
    cleared_on      = Column(DateTime)
    duration        = Column(String(20))     # "HH:MM:SS"
    duration_secs   = Column(Float)
    category        = Column(String(20))     # Power, Down, Door, Unknown
    vendor          = Column(String(20))     # Huawei, Nokia
    severity        = Column(String(50))
    fm_office       = Column(Text)
    additional_info = Column(Text)
    site_down       = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=func.now())
    tenant_id       = Column(String(64), nullable=True)
```

#### BDT Tables

```python
class BDTTest(Base):
    __tablename__ = "bdt_tests"

    id                  = Column(Integer, primary_key=True)
    file_id             = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    site_code           = Column(String(100), index=True)
    test_date           = Column(Date, index=True)
    battery_brand       = Column(Text)
    battery_model       = Column(Text)
    battery_capacity_ah = Column(Float)
    num_batteries       = Column(Integer)
    num_strings         = Column(Integer)
    num_modules_per_string = Column(Integer)
    rectifier_model     = Column(Text)
    rectifier_capacity  = Column(Float)
    start_voltage       = Column(Float)
    end_voltage         = Column(Float)
    start_ampere        = Column(Float)
    end_ampere          = Column(Float)
    test_duration_min   = Column(Float)
    site_category       = Column(Text)
    site_type           = Column(Text)
    power_source        = Column(Text)
    content_hash        = Column(String(64), unique=True, index=True)
    created_at          = Column(DateTime, default=func.now())
    tenant_id           = Column(String(64), nullable=True)

    photos = relationship("BDTPhoto", back_populates="bdt_test")
    validation_runs = relationship("PMValidationRun", back_populates="bdt_test")

class BDTPhoto(Base):
    __tablename__ = "bdt_photos"

    id              = Column(Integer, primary_key=True)
    bdt_test_id     = Column(Integer, ForeignKey("bdt_tests.id"), nullable=False)
    slot_index      = Column(Integer)
    slot_category   = Column(String(50))   # Rectifier, Battery, Module, etc.
    blob_asset_id   = Column(Integer, ForeignKey("blob_assets.id"), nullable=True)
    created_at      = Column(DateTime, default=func.now())

    bdt_test = relationship("BDTTest", back_populates="photos")
    blob_asset = relationship("BlobAsset")
```

#### Blob Storage

```python
class BlobAsset(Base):
    __tablename__ = "blob_assets"

    id              = Column(Integer, primary_key=True)
    sha256          = Column(String(64), unique=True, nullable=False, index=True)
    perceptual_hash = Column(String(64), index=True)   # dHash for near-duplicate
    mime_type       = Column(String(50))
    file_size       = Column(BigInteger)
    width           = Column(Integer)
    height          = Column(Integer)
    local_path      = Column(Text)          # local file path
    remote_url      = Column(Text)          # S3/MinIO URL, null until synced
    created_at      = Column(DateTime, default=func.now())
```

#### PM Validation Tables

```python
class PMRuleCatalog(Base):
    __tablename__ = "pm_rule_catalog"

    id          = Column(Integer, primary_key=True)
    rule_code   = Column(String(10), unique=True, nullable=False)  # R1..R11
    name        = Column(Text, nullable=False)
    description = Column(Text)

class PMRuleVersion(Base):
    __tablename__ = "pm_rule_versions"

    id              = Column(Integer, primary_key=True)
    rule_id         = Column(Integer, ForeignKey("pm_rule_catalog.id"), nullable=False)
    version         = Column(String(20), nullable=False)
    valid_from      = Column(DateTime, nullable=False)
    valid_to        = Column(DateTime)
    code_ref        = Column(Text)  # git commit or function path

class PMParameterSet(Base):
    __tablename__ = "pm_rule_parameter_sets"

    id              = Column(Integer, primary_key=True)
    params_sha256   = Column(String(64), unique=True, nullable=False, index=True)
    params_json     = Column(Text, nullable=False)
    created_at      = Column(DateTime, default=func.now())

class PMValidationRun(Base):
    __tablename__ = "pm_validation_runs"

    id                  = Column(Integer, primary_key=True)
    bdt_test_id         = Column(Integer, ForeignKey("bdt_tests.id"), nullable=False)
    parameter_set_id    = Column(Integer, ForeignKey("pm_rule_parameter_sets.id"), nullable=True)
    alarm_input_sha256  = Column(String(64), nullable=False)
    validator_code_ref  = Column(Text)
    overall_verdict     = Column(String(20))   # Accepted, Rejected, Revise
    run_at              = Column(DateTime, default=func.now())
    created_at          = Column(DateTime, default=func.now())
    tenant_id           = Column(String(64), nullable=True)

    # Idempotency constraint
    __table_args__ = (
        UniqueConstraint(
            "bdt_test_id", "parameter_set_id",
            "alarm_input_sha256", "validator_code_ref",
            name="uq_pm_run_idempotency"
        ),
    )

    bdt_test = relationship("BDTTest", back_populates="validation_runs")
    rule_results = relationship("PMRuleResult", back_populates="validation_run")

class PMRuleResult(Base):
    __tablename__ = "pm_rule_results"

    id                  = Column(Integer, primary_key=True)
    validation_run_id   = Column(Integer, ForeignKey("pm_validation_runs.id"), nullable=False)
    rule_id             = Column(Integer, ForeignKey("pm_rule_catalog.id"), nullable=False)
    verdict             = Column(String(20))    # Accepted, Rejected, Revise, N/A
    evidence_json       = Column(Text)
    created_at          = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("validation_run_id", "rule_id", name="uq_rule_per_run"),
    )

    validation_run = relationship("PMValidationRun", back_populates="rule_results")
```

#### State + Sync Tables

```python
class UIState(Base):
    __tablename__ = "ui_state"

    key         = Column(String(100), primary_key=True)
    value_json  = Column(Text, nullable=False)
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())

class ReviewEvent(Base):
    __tablename__ = "review_events"

    id          = Column(Integer, primary_key=True)
    event_type  = Column(String(50))
    site_code   = Column(String(100))
    test_date   = Column(Date)
    reviewer    = Column(Text)
    payload_json = Column(Text)
    created_at  = Column(DateTime, default=func.now())

class SyncOutboxEvent(Base):
    __tablename__ = "sync_outbox"

    id              = Column(Integer, primary_key=True)
    event_id        = Column(String(64), unique=True, nullable=False, index=True)
    origin_device_id = Column(String(64))
    entity_type     = Column(String(50))
    entity_local_id = Column(String(64))
    op              = Column(String(20))    # upsert, delete
    entity_hash     = Column(String(64))
    payload_json    = Column(Text)
    status          = Column(String(20), default="pending", index=True)
    created_at      = Column(DateTime, default=func.now())
    synced_at       = Column(DateTime)

class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    id          = Column(Integer, primary_key=True)
    cursor      = Column(Text)
    batch_key   = Column(String(64))
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())
```

### Dedup Pipeline (hashing.py)

Four layers as described in the research:

```python
# Layer 1: File-level SHA-256
def compute_file_sha256(path: str) -> str

# Layer 2: Row-level composite hash
def compute_row_hash(row: dict, key_columns: list[str]) -> str
    # normalize: strip, lower, ISO dates, fixed-precision floats
    # then SHA-256 of pipe-delimited canonical string

# Layer 3: Image hashing
def compute_image_sha256(image_bytes: bytes) -> str
def compute_perceptual_hash(image_path: str) -> str  # dHash via imagehash

# All hash functions are deterministic and normalize inputs before hashing
```

Row hash key columns for alarm records:

```python
ALARM_HASH_COLS = [
    "site_id", "alarm_name", "occurred_on", "cleared_on",
    "category", "vendor", "severity"
]
```

### Migration of data/state.py

`data/state.py` function signatures stay the same. Internals switch from file I/O to `db/repos/` calls:

| Current function           | New implementation                                     |
| -------------------------- | ------------------------------------------------------ |
| `save_state(data)`         | serialize each key-value pair into `ui_state` table    |
| `load_state()`             | read all rows from `ui_state`, reconstruct dict        |
| `save_dataframe(df)`       | bulk insert into `alarm_records` (with row_hash dedup) |
| `load_dataframe()`         | SELECT \* from `alarm_records`, return as DataFrame    |
| `append_review_event(...)` | INSERT into `review_events`                            |
| `load_review_events()`     | SELECT from `review_events`                            |
| `append_outbox_event(...)` | INSERT into `sync_outbox`                              |
| `load_pending_outbox()`    | SELECT WHERE status='pending'                          |
| `mark_outbox_synced(...)`  | UPDATE status='synced'                                 |
| `compute_file_hashes(...)` | check `uploaded_files.file_sha256`                     |
| `clear_cache()`            | DELETE from `alarm_records` + `ui_state`               |

### BDT History Migration

`bdt/history.py` currently writes JSON files to `~/.alarm_viewer/bdt_history/`. This migrates to `bdt_tests` + `pm_validation_runs` + `pm_rule_results` tables.

| Current function                 | New implementation                                                                           |
| -------------------------------- | -------------------------------------------------------------------------------------------- |
| `save_test_record(bdt)`          | INSERT into `bdt_tests` (with content_hash dedup)                                            |
| `load_previous_test(site, date)` | SELECT from `bdt_tests` WHERE site_code AND test_date < date ORDER BY test_date DESC LIMIT 1 |
| `save_validation_run(...)`       | INSERT into `pm_validation_runs` + `pm_rule_results`                                         |
| `compare_tests(current, prev)`   | same logic, different data source                                                            |

### Image Extraction and Storage

BDT photos currently extracted by `bdt/parser.py` using openpyxl. The new pipeline:

1. Extract images from xlsx via `zipfile` (fast path, no full parse)
2. Compute SHA-256 of each image
3. Check `blob_assets.sha256` — skip if exists
4. Compute perceptual hash (dHash) for near-duplicate detection
5. Save image file to `~/.alarm_viewer/blobs/{sha256[:2]}/{sha256}` (local blob storage)
6. Later epic: upload to MinIO/S3, store `remote_url`
7. Insert metadata into `blob_assets` + link via `bdt_photos`

### First Launch / Migration

On first launch after upgrade:

1. `init_db()` creates all tables via Alembic
2. No migration of old data (user confirmed state files are wipeable)
3. Feature flags default to local-only (`sync_on=False`)

### Calamine Integration

Excel parsing stays on calamine (already the primary engine). The change: after parsing a DataFrame, rows get hashed and bulk-inserted into `alarm_records` via SQLAlchemy. The `_full_df` DataFrame in AlarmViewer is populated from a DB query instead of from Parquet.

```python
# Before (current):
df = pd.read_parquet(CACHE_FILE)

# After:
with get_session() as session:
    rows = session.query(AlarmRecord).all()
    df = pd.DataFrame([r.__dict__ for r in rows])
```

For large datasets, this uses `pd.read_sql()` for better performance:

```python
df = pd.read_sql("SELECT * FROM alarm_records", engine)
```

### Architectural Rules

- `db/` is a peer of `data/`, `core/`, `bdt/`, `ui/`
- `core/` never imports from `db/`
- `ui/` never imports from `db/` directly — goes through `data/state.py`
- `data/state.py` is the adapter between the app and the DB layer
- `db/repos/` contains all SQL queries — models.py is declarative only

### Dependencies Added

```
sqlalchemy>=2.0
alembic>=1.13
imagehash>=4.3
Pillow>=10.0
```

---

## What This Does NOT Cover (Later Epics)

- E2: Advanced dedup and Bloom filter (E1 uses DB unique constraints only)
- E3: MinIO/S3 blob upload (E1 stores locally)
- E4: PM rule versioning and parameter set registry
- E5: Cloud sync pipeline
- E6: Cloud-backed query service
- E7: Load testing and hardening

---

## Testing Strategy

1. All 321 existing tests pass (they don't touch the DB)
2. Golden parity tests (E0) pass — current behavior preserved
3. New unit tests for each repo (alarm_repo, file_repo, bdt_repo, etc.)
4. Integration test: parse file → insert to DB → query back → compare with direct parse
5. Migration test: init_db on empty SQLite, verify all tables created
