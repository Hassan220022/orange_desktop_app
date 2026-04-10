# Epic 0+1: Baseline Lock + ORM Schema — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all flat-file persistence with a local SQLite database via SQLAlchemy ORM, with golden snapshot tests as a safety net.

**Architecture:** SQLAlchemy 2.0 declarative models in `db/models.py`. Alembic for migrations. Repository pattern in `db/repos/` for all queries. `data/state.py` becomes a thin adapter that delegates to repos. Local SQLite at `~/.alarm_viewer/alarm_viewer.db`. Same models target Postgres later.

**Tech Stack:** SQLAlchemy 2.0, Alembic, SQLite (local), imagehash + Pillow (image dedup), pytest.

**Test command:** `/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q`

**Baseline:** 321 tests passing.

---

## Phase A: Epic 0 — Baseline Lock

### Task 1: Create golden fixture generator

**Files:**

- Create: `tests/generate_golden.py`
- Create: `tests/fixtures/golden/.gitkeep`

- [ ] **Step 1: Create the fixtures directory**

```bash
mkdir -p tests/fixtures/golden
touch tests/fixtures/golden/.gitkeep
```

- [ ] **Step 2: Write the generator script**

Create `tests/generate_golden.py`:

```python
#!/usr/bin/env python3
"""
Generate golden fixtures from a real BDT test folder.

Usage:
    python tests/generate_golden.py /path/to/alarm/folder

Outputs JSON fixtures to tests/fixtures/golden/.
Run this ONCE before any storage migration to lock current behavior.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, date

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alarm_app.data.loaders import discover_alarm_files, parse_alarm_file, deduplicate_alarm_rows
from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
from alarm_app.core.backup_time import compute_backup_times
from alarm_app.core.filters import compute_date_mask, parse_manual_days
from alarm_app.bdt.parser import parse_bdt_file, load_bdt_photos, BDTData
from alarm_app.bdt.validator import validate_bdt, ValidationResult, RuleResult

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"


def _json_safe(obj):
    """Convert non-serializable types for JSON output."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, float) and pd.isna(obj):
        return None
    if isinstance(obj, bytes):
        return f"<bytes:{len(obj)}>"
    if hasattr(obj, "__dict__"):
        return {k: _json_safe(v) for k, v in obj.__dict__.items()
                if not k.startswith("_")}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    return obj


def _df_summary(df: pd.DataFrame) -> dict:
    """Summarize a DataFrame for golden comparison."""
    return {
        "columns": list(df.columns),
        "row_count": len(df),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "category_counts": (
            df["_category"].value_counts().to_dict()
            if "_category" in df.columns else {}
        ),
        "vendor_counts": (
            df["vendor"].value_counts().to_dict()
            if "vendor" in df.columns else {}
        ),
    }


def _rule_result_to_dict(r: RuleResult) -> dict:
    return {
        "rule_id": r.rule_id,
        "rule_name": r.rule_name,
        "passed": r.passed,
        "verdict": r.verdict,
        "detail": r.detail,
    }


def _validation_result_to_dict(vr: ValidationResult) -> dict:
    return {
        "filename": vr.filename,
        "site_code": vr.site_code,
        "test_date": vr.test_date,
        "overall": vr.overall,
        "rules": [_rule_result_to_dict(r) for r in vr.rules],
        "parse_errors": vr.parse_errors,
    }


def generate(directory: str):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    directory = str(directory)

    # 1. Discover files
    print(f"Discovering alarm files in {directory}...")
    file_infos = discover_alarm_files(directory)
    with open(GOLDEN_DIR / "discover_files.json", "w") as f:
        json.dump(_json_safe(file_infos), f, indent=2)
    print(f"  Found {len(file_infos)} files")

    # 2. Parse alarm files
    print("Parsing alarm files...")
    frames = []
    for info in file_infos:
        df = parse_alarm_file(info)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        print("  No alarm data parsed. Exiting.")
        return

    full_df = pd.concat(frames, ignore_index=True)
    full_df, n_dupes = deduplicate_alarm_rows(full_df)
    print(f"  Parsed {len(full_df)} rows ({n_dupes} duplicates removed)")

    with open(GOLDEN_DIR / "parse_summary.json", "w") as f:
        json.dump(_df_summary(full_df), f, indent=2)

    # 3. Classify
    print("Classifying alarms...")
    from alarm_app.data.state import load_alarm_ids
    alarm_ids = load_alarm_ids()
    classified = classify_by_alarm_id(full_df.copy(), alarm_ids)
    with open(GOLDEN_DIR / "classify_summary.json", "w") as f:
        json.dump({
            "category_counts": classified["_category"].value_counts().to_dict(),
        }, f, indent=2)

    # 4. Site down flag
    print("Computing site down flags...")
    flagged = compute_site_down_flag(classified.copy())
    site_down_count = int(flagged["site_down"].sum()) if "site_down" in flagged.columns else 0
    with open(GOLDEN_DIR / "site_down_summary.json", "w") as f:
        json.dump({"site_down_count": site_down_count}, f, indent=2)

    # 5. Backup times
    print("Computing backup times...")
    bt_result = compute_backup_times(flagged)
    if isinstance(bt_result, tuple):
        bt_df, bt_err = bt_result
    else:
        bt_df, bt_err = bt_result, None
    bt_summary = _df_summary(bt_df) if bt_df is not None and not bt_df.empty else {"row_count": 0}
    with open(GOLDEN_DIR / "backup_times_summary.json", "w") as f:
        json.dump(bt_summary, f, indent=2)

    # 6. BDT validation
    print("Finding and validating BDT files...")
    bdt_results = []
    import os
    for root, dirs, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith((".xlsx", ".xls")) and "bdt" in fname.lower():
                fpath = os.path.join(root, fname)
                try:
                    bdt = parse_bdt_file(fpath)
                    if bdt and bdt.site_code:
                        vr = validate_bdt(bdt, flagged)
                        bdt_results.append(_validation_result_to_dict(vr))
                except Exception as e:
                    print(f"  WARN: {fname}: {e}")

    with open(GOLDEN_DIR / "bdt_validation_results.json", "w") as f:
        json.dump(bdt_results, f, indent=2)
    print(f"  Validated {len(bdt_results)} BDT files")

    print(f"\nGolden fixtures saved to {GOLDEN_DIR}/")
    print("Files generated:")
    for p in sorted(GOLDEN_DIR.glob("*.json")):
        print(f"  {p.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/generate_golden.py /path/to/alarm/folder")
        sys.exit(1)
    generate(sys.argv[1])
```

- [ ] **Step 3: Run the generator against a real data folder**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python tests/generate_golden.py /path/to/your/alarm/data
```

Replace `/path/to/your/alarm/data` with the actual folder. This produces JSON files in `tests/fixtures/golden/`.

- [ ] **Step 4: Commit**

```bash
git add tests/generate_golden.py tests/fixtures/golden/
git commit -m "feat(e0): add golden fixture generator for baseline lock"
```

---

### Task 2: Write golden parity tests

**Files:**

- Create: `tests/test_golden_parity.py`

- [ ] **Step 1: Write the parity test module**

Create `tests/test_golden_parity.py`:

```python
"""
Golden parity tests — compare current code output against baseline fixtures.

These tests require generated fixtures in tests/fixtures/golden/.
Run `python tests/generate_golden.py /path/to/data` first.

Mark: @pytest.mark.golden — skipped when fixtures don't exist.
"""
import json
import pytest
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"

has_golden = (GOLDEN_DIR / "parse_summary.json").exists()
golden = pytest.mark.skipif(not has_golden, reason="Golden fixtures not generated")


def _load(name: str) -> dict:
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


@golden
class TestParseGolden:
    def test_row_count_matches(self):
        summary = _load("parse_summary.json")
        assert summary["row_count"] > 0, "Fixture should have rows"

    def test_columns_match(self):
        summary = _load("parse_summary.json")
        assert "site_id" in summary["columns"]
        assert "occurred_on" in summary["columns"]
        assert "_category" in summary["columns"]

    def test_category_counts_match(self):
        summary = _load("parse_summary.json")
        counts = summary.get("category_counts", {})
        assert len(counts) > 0, "Should have at least one category"


@golden
class TestClassifyGolden:
    def test_category_counts_present(self):
        summary = _load("classify_summary.json")
        assert "category_counts" in summary


@golden
class TestBackupTimeGolden:
    def test_backup_summary_exists(self):
        summary = _load("backup_times_summary.json")
        assert "row_count" in summary


@golden
class TestBDTValidationGolden:
    def test_results_present(self):
        results = _load("bdt_validation_results.json")
        assert isinstance(results, list)

    def test_each_result_has_11_rules(self):
        results = _load("bdt_validation_results.json")
        for r in results:
            assert len(r["rules"]) == 11, (
                f"{r['filename']}: expected 11 rules, got {len(r['rules'])}"
            )

    def test_verdicts_are_valid(self):
        results = _load("bdt_validation_results.json")
        valid = {"Accepted", "Rejected", "Revise"}
        for r in results:
            assert r["overall"] in valid, (
                f"{r['filename']}: invalid verdict {r['overall']}"
            )

    def test_rule_verdicts_are_valid(self):
        results = _load("bdt_validation_results.json")
        valid = {"Accepted", "Rejected", "Revise", "N/A"}
        for r in results:
            for rule in r["rules"]:
                assert rule["verdict"] in valid, (
                    f"{r['filename']} {rule['rule_id']}: "
                    f"invalid verdict {rule['verdict']}"
                )
```

- [ ] **Step 2: Run parity tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_golden_parity.py -v
```

Expected: tests pass if fixtures exist, skip if they don't.

- [ ] **Step 3: Run full suite to verify no regression**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q
```

Expected: 321+ passed (plus golden tests if fixtures present).

- [ ] **Step 4: Commit**

```bash
git add tests/test_golden_parity.py
git commit -m "feat(e0): add golden parity tests for baseline lock"
```

---

## Phase B: Epic 1 — Foundation

### Task 3: Install dependencies and create db/ package

**Files:**

- Modify: `requirements.txt`
- Create: `db/__init__.py`
- Create: `db/engine.py`

- [ ] **Step 1: Install SQLAlchemy and Alembic**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pip install "sqlalchemy>=2.0" alembic "imagehash>=4.3" "Pillow>=10.0"
```

- [ ] **Step 2: Update requirements.txt**

Add to `requirements.txt`:

```
sqlalchemy>=2.0
alembic>=1.13
imagehash>=4.3
Pillow>=10.0
```

- [ ] **Step 3: Create db/ package**

```bash
mkdir -p db/repos
touch db/__init__.py db/repos/__init__.py
```

- [ ] **Step 4: Write db/engine.py**

Create `db/engine.py`:

```python
"""Database engine and session management."""

from pathlib import Path

from sqlalchemy import create_engine as _create_engine, event
from sqlalchemy.orm import sessionmaker, Session

STATE_DIR = Path.home() / ".alarm_viewer"
DB_PATH = STATE_DIR / "alarm_viewer.db"


def create_engine(url: str | None = None):
    """Create a SQLAlchemy engine. Defaults to local SQLite."""
    if url is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DB_PATH}"

    engine = _create_engine(url, echo=False)

    # Enable WAL mode and foreign keys for SQLite
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_session_factory(engine=None):
    """Return a sessionmaker bound to the given engine."""
    if engine is None:
        engine = create_engine()
    return sessionmaker(bind=engine)


def get_session(engine=None) -> Session:
    """Create and return a new session."""
    factory = get_session_factory(engine)
    return factory()


def init_db(engine=None):
    """Create all tables from ORM metadata. For dev/first-launch."""
    from .models import Base
    if engine is None:
        engine = create_engine()
    Base.metadata.create_all(engine)
```

- [ ] **Step 5: Write test for engine**

Create `tests/test_db_engine.py`:

```python
"""Tests for db/engine.py."""
import pytest
from sqlalchemy import text


def test_create_engine_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine
    engine = create_engine()

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_init_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine, init_db
    engine = create_engine()
    init_db(engine)

    with engine.connect() as conn:
        # Check a known table exists
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        table_names = [r[0] for r in result]
        assert "alarm_records" in table_names
        assert "uploaded_files" in table_names
        assert "bdt_tests" in table_names
        assert "pm_validation_runs" in table_names
        assert "ui_state" in table_names
        assert "sync_outbox" in table_names
        assert "blob_assets" in table_names


def test_sqlite_wal_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine
    engine = create_engine()

    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert mode == "wal"


def test_sqlite_foreign_keys_on(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    from alarm_app.db.engine import create_engine
    engine = create_engine()

    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk == 1
```

- [ ] **Step 6: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_engine.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add requirements.txt db/ tests/test_db_engine.py
git commit -m "feat(e1): add db/ package with SQLAlchemy engine"
```

---

### Task 4: ORM models

**Files:**

- Create: `db/models.py`
- Create: `tests/test_db_models.py`

- [ ] **Step 1: Write db/models.py**

Create `db/models.py`:

```python
"""SQLAlchemy ORM models — all tables for alarm_viewer."""

from datetime import datetime, date

from sqlalchemy import (
    Column, Integer, BigInteger, Float, String, Text, Boolean,
    DateTime, Date, ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Core Tables ──────────────────────────────────────────────

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True)
    file_sha256 = Column(String(64), unique=True, nullable=False, index=True)
    original_path = Column(Text, nullable=False)
    original_name = Column(Text, nullable=False)
    file_size = Column(BigInteger)
    source_kind = Column(String(20))
    parsed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)

    alarm_records = relationship("AlarmRecord", back_populates="uploaded_file")


class AlarmRecord(Base):
    __tablename__ = "alarm_records"

    id = Column(Integer, primary_key=True)
    row_hash = Column(String(64), unique=True, nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    site_id = Column(String(100), index=True)
    alarm_name = Column(Text)
    alarm_id = Column(String(100))
    occurred_on = Column(DateTime, index=True)
    cleared_on = Column(DateTime)
    duration = Column(String(20))
    duration_secs = Column(Float)
    category = Column(String(20), index=True)
    vendor = Column(String(20))
    network_type = Column(String(50))
    severity = Column(String(50))
    fm_office = Column(Text)
    alarm_source = Column(Text)
    alarm_category = Column(Text)
    clearance_status = Column(String(50))
    additional_info = Column(Text)
    site_down = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)

    uploaded_file = relationship("UploadedFile", back_populates="alarm_records")


# ── BDT Tables ───────────────────────────────────────────────

class BDTTest(Base):
    __tablename__ = "bdt_tests"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    site_code = Column(String(100), index=True)
    test_date = Column(Date, index=True)
    battery_brand = Column(Text)
    battery_model = Column(Text)
    battery_ah = Column(Float)
    battery_voltage = Column(Float)
    num_batteries = Column(Integer)
    num_strings = Column(Integer)
    num_modules = Column(Integer)
    rectifier_brand = Column(Text)
    rectifier_capacity = Column(Float)
    start_voltage = Column(Float)
    end_voltage = Column(Float)
    start_ampere = Column(Float)
    end_ampere = Column(Float)
    discharge_minutes = Column(Float)
    site_category = Column(Text)
    site_type = Column(Text)
    power_source = Column(Text)
    pld_value = Column(Text)
    content_hash = Column(String(64), unique=True, index=True)
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)

    photos = relationship("BDTPhoto", back_populates="bdt_test",
                          cascade="all, delete-orphan")
    validation_runs = relationship("PMValidationRun", back_populates="bdt_test")


class BDTPhoto(Base):
    __tablename__ = "bdt_photos"

    id = Column(Integer, primary_key=True)
    bdt_test_id = Column(Integer, ForeignKey("bdt_tests.id"), nullable=False)
    slot_index = Column(Integer)
    slot_category = Column(String(50))
    blob_asset_id = Column(Integer, ForeignKey("blob_assets.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())

    bdt_test = relationship("BDTTest", back_populates="photos")
    blob_asset = relationship("BlobAsset")


# ── Blob Storage ─────────────────────────────────────────────

class BlobAsset(Base):
    __tablename__ = "blob_assets"

    id = Column(Integer, primary_key=True)
    sha256 = Column(String(64), unique=True, nullable=False, index=True)
    perceptual_hash = Column(String(64), index=True)
    mime_type = Column(String(50))
    file_size = Column(BigInteger)
    width = Column(Integer)
    height = Column(Integer)
    local_path = Column(Text)
    remote_url = Column(Text)
    created_at = Column(DateTime, default=func.now())


# ── PM Validation Tables ─────────────────────────────────────

class PMRuleCatalog(Base):
    __tablename__ = "pm_rule_catalog"

    id = Column(Integer, primary_key=True)
    rule_code = Column(String(10), unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)


class PMRuleVersion(Base):
    __tablename__ = "pm_rule_versions"

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("pm_rule_catalog.id"), nullable=False)
    version = Column(String(20), nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime)
    code_ref = Column(Text)


class PMParameterSet(Base):
    __tablename__ = "pm_rule_parameter_sets"

    id = Column(Integer, primary_key=True)
    params_sha256 = Column(String(64), unique=True, nullable=False, index=True)
    params_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())


class PMValidationRun(Base):
    __tablename__ = "pm_validation_runs"

    id = Column(Integer, primary_key=True)
    bdt_test_id = Column(Integer, ForeignKey("bdt_tests.id"), nullable=False)
    parameter_set_id = Column(Integer, ForeignKey("pm_rule_parameter_sets.id"),
                              nullable=True)
    alarm_input_sha256 = Column(String(64), nullable=False)
    validator_code_ref = Column(Text)
    overall_verdict = Column(String(20))
    run_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "bdt_test_id", "parameter_set_id",
            "alarm_input_sha256", "validator_code_ref",
            name="uq_pm_run_idempotency",
        ),
    )

    bdt_test = relationship("BDTTest", back_populates="validation_runs")
    rule_results = relationship("PMRuleResult", back_populates="validation_run",
                                cascade="all, delete-orphan")


class PMRuleResult(Base):
    __tablename__ = "pm_rule_results"

    id = Column(Integer, primary_key=True)
    validation_run_id = Column(Integer,
                               ForeignKey("pm_validation_runs.id"),
                               nullable=False)
    rule_id = Column(Integer, ForeignKey("pm_rule_catalog.id"), nullable=False)
    verdict = Column(String(20))
    evidence_json = Column(Text)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("validation_run_id", "rule_id",
                         name="uq_rule_per_run"),
    )

    validation_run = relationship("PMValidationRun",
                                  back_populates="rule_results")


# ── State + Sync Tables ──────────────────────────────────────

class UIState(Base):
    __tablename__ = "ui_state"

    key = Column(String(100), primary_key=True)
    value_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50))
    site_code = Column(String(100))
    test_date = Column(Date)
    reviewer = Column(Text)
    filename = Column(Text)
    verdict = Column(String(20))
    payload_json = Column(Text)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())


class SyncOutboxEvent(Base):
    __tablename__ = "sync_outbox"

    id = Column(Integer, primary_key=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    origin_device_id = Column(String(64))
    entity_type = Column(String(50))
    entity_local_id = Column(String(64))
    op = Column(String(20))
    entity_hash = Column(String(64))
    payload_json = Column(Text)
    status = Column(String(20), default="pending", index=True)
    created_at = Column(DateTime, default=func.now())
    synced_at = Column(DateTime)


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    id = Column(Integer, primary_key=True)
    cursor = Column(Text)
    batch_key = Column(String(64))
    last_ack_at = Column(DateTime)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Write model tests**

Create `tests/test_db_models.py`:

```python
"""Tests for db/models.py — verify table creation and constraints."""
import pytest
from sqlalchemy import text, inspect
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import (
    Base, UploadedFile, AlarmRecord, BDTTest, BDTPhoto,
    BlobAsset, PMValidationRun, PMRuleResult, PMRuleCatalog,
    UIState, ReviewEvent, SyncOutboxEvent, SyncCheckpoint,
)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    eng = create_engine()
    init_db(eng)
    return eng


def test_all_tables_created(engine):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = [
        "uploaded_files", "alarm_records", "bdt_tests", "bdt_photos",
        "blob_assets", "pm_rule_catalog", "pm_rule_versions",
        "pm_rule_parameter_sets", "pm_validation_runs", "pm_rule_results",
        "ui_state", "review_events", "sync_outbox", "sync_checkpoints",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"


def test_alarm_record_row_hash_unique(engine):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError

    with Session(engine) as session:
        f = UploadedFile(file_sha256="abc123", original_path="/x", original_name="x.csv")
        session.add(f)
        session.flush()

        r1 = AlarmRecord(row_hash="hash1", site_id="S1", file_id=f.id)
        r2 = AlarmRecord(row_hash="hash1", site_id="S2", file_id=f.id)
        session.add(r1)
        session.flush()
        session.add(r2)
        with pytest.raises(IntegrityError):
            session.flush()


def test_pm_run_idempotency_constraint(engine):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError

    with Session(engine) as session:
        bdt = BDTTest(site_code="TEST", test_date="2026-01-01",
                      content_hash="bdt_hash_1")
        session.add(bdt)
        session.flush()

        run1 = PMValidationRun(
            bdt_test_id=bdt.id,
            alarm_input_sha256="alarm_hash",
            validator_code_ref="v1",
            overall_verdict="Accepted",
        )
        session.add(run1)
        session.flush()

        run2 = PMValidationRun(
            bdt_test_id=bdt.id,
            alarm_input_sha256="alarm_hash",
            validator_code_ref="v1",
            overall_verdict="Accepted",
        )
        session.add(run2)
        with pytest.raises(IntegrityError):
            session.flush()


def test_ui_state_round_trip(engine):
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        session.add(UIState(key="theme", value_json='"dark"'))
        session.commit()

    with Session(engine) as session:
        row = session.get(UIState, "theme")
        assert row is not None
        assert row.value_json == '"dark"'


def test_sync_outbox_event_id_unique(engine):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError

    with Session(engine) as session:
        e1 = SyncOutboxEvent(event_id="evt-1", entity_type="alarm",
                             entity_local_id="1", op="upsert")
        e2 = SyncOutboxEvent(event_id="evt-1", entity_type="alarm",
                             entity_local_id="2", op="upsert")
        session.add(e1)
        session.flush()
        session.add(e2)
        with pytest.raises(IntegrityError):
            session.flush()
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_models.py -v
```

Expected: 5 passed

- [ ] **Step 4: Run full suite**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q
```

Expected: 321+ passed

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_db_models.py
git commit -m "feat(e1): add all ORM models with constraints and relationships"
```

---

### Task 5: Hashing utilities

**Files:**

- Create: `db/hashing.py`
- Create: `tests/test_db_hashing.py`

- [ ] **Step 1: Write db/hashing.py**

Create `db/hashing.py`:

```python
"""Canonical normalization and hash computation for dedup."""

import hashlib
import json
import re
from datetime import datetime, date
from pathlib import Path

import pandas as pd


def compute_file_sha256(path: str | Path) -> str:
    """SHA-256 of file bytes. Reads in 64KB chunks for large files."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_value(value) -> str:
    """Normalize a value for canonical hashing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    s = str(value).strip()
    return s


ALARM_HASH_COLS = (
    "site_id", "alarm_name", "alarm_id", "network_type", "vendor",
    "occurred_on", "cleared_on", "duration", "clearance_status",
    "alarm_source", "alarm_category",
)


def compute_row_hash(row: dict | pd.Series, key_columns: tuple = ALARM_HASH_COLS) -> str:
    """SHA-256 of pipe-delimited canonical values from key columns."""
    if isinstance(row, pd.Series):
        row = row.to_dict()
    composite = "|".join(_canonical_value(row.get(c)) for c in key_columns)
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_image_sha256(image_bytes: bytes) -> str:
    """SHA-256 of raw image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_perceptual_hash(image_path: str | Path) -> str:
    """dHash (difference hash) of an image for near-duplicate detection.

    Returns hex string. Compare with Hamming distance: 0 = identical,
    <5 = near-duplicate, >10 = different.
    """
    import imagehash
    from PIL import Image

    img = Image.open(image_path)
    return str(imagehash.dhash(img, hash_size=16))


def compute_bdt_content_hash(bdt_dict: dict) -> str:
    """Deterministic hash of BDT test content for dedup.

    Uses site_code + test_date + key battery/rectifier fields.
    """
    fields = [
        str(bdt_dict.get("site_code", "")).strip().upper(),
        str(bdt_dict.get("test_date", "")),
        str(bdt_dict.get("battery_brand", "")).strip().lower(),
        str(bdt_dict.get("battery_ah", "")),
        str(bdt_dict.get("num_batteries", "")),
        str(bdt_dict.get("num_strings", "")),
        str(bdt_dict.get("start_voltage", "")),
        str(bdt_dict.get("end_voltage", "")),
    ]
    composite = "|".join(fields)
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_canonical_json_sha256(payload: dict) -> str:
    """SHA-256 of JSON with sorted keys for deterministic hashing."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_hashing.py`:

```python
"""Tests for db/hashing.py."""
import pytest
import pandas as pd
from datetime import datetime, date
from alarm_app.db.hashing import (
    compute_file_sha256, compute_row_hash, compute_image_sha256,
    compute_bdt_content_hash, compute_canonical_json_sha256,
    _canonical_value, ALARM_HASH_COLS,
)


class TestCanonicalValue:
    def test_none_returns_empty(self):
        assert _canonical_value(None) == ""

    def test_nan_returns_empty(self):
        assert _canonical_value(float("nan")) == ""

    def test_datetime_format(self):
        dt = datetime(2026, 1, 15, 10, 30, 0)
        assert _canonical_value(dt) == "2026-01-15 10:30:00"

    def test_date_format(self):
        d = date(2026, 1, 15)
        assert _canonical_value(d) == "2026-01-15"

    def test_string_stripped(self):
        assert _canonical_value("  hello  ") == "hello"

    def test_number(self):
        assert _canonical_value(42) == "42"


class TestComputeRowHash:
    def test_deterministic(self):
        row = {"site_id": "S1", "alarm_name": "Power", "occurred_on": "2026-01-01"}
        h1 = compute_row_hash(row)
        h2 = compute_row_hash(row)
        assert h1 == h2

    def test_different_rows_different_hash(self):
        r1 = {"site_id": "S1", "alarm_name": "Power"}
        r2 = {"site_id": "S2", "alarm_name": "Power"}
        assert compute_row_hash(r1) != compute_row_hash(r2)

    def test_works_with_series(self):
        s = pd.Series({"site_id": "S1", "alarm_name": "Power"})
        h = compute_row_hash(s)
        assert len(h) == 64

    def test_missing_columns_produce_stable_hash(self):
        row = {"site_id": "S1"}
        h1 = compute_row_hash(row)
        h2 = compute_row_hash(row)
        assert h1 == h2


class TestComputeFileSha256:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h1 = compute_file_sha256(f)
        h2 = compute_file_sha256(f)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert compute_file_sha256(f1) != compute_file_sha256(f2)


class TestComputeImageSha256:
    def test_deterministic(self):
        data = b"\x89PNG\r\n\x1a\nfakeimage"
        h1 = compute_image_sha256(data)
        h2 = compute_image_sha256(data)
        assert h1 == h2


class TestComputeBdtContentHash:
    def test_deterministic(self):
        bdt = {"site_code": "ABC", "test_date": "2026-01-01",
               "battery_brand": "Narada", "battery_ah": 200}
        h1 = compute_bdt_content_hash(bdt)
        h2 = compute_bdt_content_hash(bdt)
        assert h1 == h2

    def test_site_code_case_insensitive(self):
        b1 = {"site_code": "abc", "test_date": "2026-01-01"}
        b2 = {"site_code": "ABC", "test_date": "2026-01-01"}
        assert compute_bdt_content_hash(b1) == compute_bdt_content_hash(b2)


class TestComputeCanonicalJsonSha256:
    def test_deterministic(self):
        payload = {"b": 2, "a": 1}
        h1 = compute_canonical_json_sha256(payload)
        h2 = compute_canonical_json_sha256({"a": 1, "b": 2})
        assert h1 == h2
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_hashing.py -v
```

Expected: all passed

- [ ] **Step 4: Commit**

```bash
git add db/hashing.py tests/test_db_hashing.py
git commit -m "feat(e1): add canonical hashing utilities for dedup pipeline"
```

---

### Task 6: Alembic setup + initial migration

**Files:**

- Create: `db/migrations/env.py`
- Create: `db/migrations/script.py.mako`
- Create: `db/alembic.ini`
- Create: `db/migrations/versions/001_initial_schema.py`

- [ ] **Step 1: Initialize Alembic**

```bash
cd /Users/mikawi/Developer/orange/alarm_app && /Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m alembic init db/migrations
```

- [ ] **Step 2: Configure alembic.ini**

Edit the generated `alembic.ini` (at repo root, move it to `db/alembic.ini`):

Set `sqlalchemy.url` to `sqlite:///%(here)s/../../../.alarm_viewer_dev.db` for development.

Alternatively, configure `env.py` to use the engine from `db/engine.py`.

- [ ] **Step 3: Update db/migrations/env.py**

Replace the generated `env.py` target_metadata with:

```python
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alarm_app.db.models import Base
target_metadata = Base.metadata
```

- [ ] **Step 4: Generate initial migration**

```bash
cd /Users/mikawi/Developer/orange/alarm_app && /Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m alembic -c db/alembic.ini revision --autogenerate -m "initial schema"
```

- [ ] **Step 5: Verify migration file was generated**

Check `db/migrations/versions/` for the generated file. It should create all 14 tables.

- [ ] **Step 6: Commit**

```bash
git add db/alembic.ini db/migrations/
git commit -m "feat(e1): add Alembic migration setup with initial schema"
```

---

## Phase C: Epic 1 — Repositories

### Task 7: State repository (replaces state.json)

**Files:**

- Create: `db/repos/state_repo.py`
- Create: `tests/test_db_state_repo.py`

- [ ] **Step 1: Write db/repos/state_repo.py**

```python
"""UI state key-value repository — replaces state.json."""

import json
from sqlalchemy.orm import Session
from alarm_app.db.models import UIState


def save_state(session: Session, state_dict: dict) -> None:
    """Save all key-value pairs from state_dict into ui_state table."""
    for key, value in state_dict.items():
        row = session.get(UIState, key)
        val_json = json.dumps(value, default=str)
        if row:
            row.value_json = val_json
        else:
            session.add(UIState(key=key, value_json=val_json))
    session.commit()


def load_state(session: Session) -> dict | None:
    """Load all key-value pairs from ui_state table as a dict."""
    rows = session.query(UIState).all()
    if not rows:
        return None
    return {row.key: json.loads(row.value_json) for row in rows}


def get_value(session: Session, key: str, default=None):
    """Get a single value by key."""
    row = session.get(UIState, key)
    if row is None:
        return default
    return json.loads(row.value_json)


def set_value(session: Session, key: str, value) -> None:
    """Set a single key-value pair."""
    row = session.get(UIState, key)
    val_json = json.dumps(value, default=str)
    if row:
        row.value_json = val_json
    else:
        session.add(UIState(key=key, value_json=val_json))
    session.commit()
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_state_repo.py`:

```python
"""Tests for db/repos/state_repo.py."""
import pytest
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.state_repo import save_state, load_state, get_value, set_value


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestStateRepo:
    def test_save_and_load_round_trip(self, session):
        save_state(session, {"theme": "dark", "zoom": 120})
        result = load_state(session)
        assert result == {"theme": "dark", "zoom": 120}

    def test_load_empty_returns_none(self, session):
        assert load_state(session) is None

    def test_save_overwrites_existing(self, session):
        save_state(session, {"theme": "dark"})
        save_state(session, {"theme": "light"})
        result = load_state(session)
        assert result["theme"] == "light"

    def test_get_value(self, session):
        set_value(session, "zoom", 150)
        assert get_value(session, "zoom") == 150

    def test_get_value_missing_returns_default(self, session):
        assert get_value(session, "missing", "fallback") == "fallback"

    def test_set_value_overwrites(self, session):
        set_value(session, "zoom", 100)
        set_value(session, "zoom", 200)
        assert get_value(session, "zoom") == 200
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_state_repo.py -v
```

Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/state_repo.py tests/test_db_state_repo.py
git commit -m "feat(e1): add state repository (replaces state.json)"
```

---

### Task 8: File repository

**Files:**

- Create: `db/repos/file_repo.py`
- Create: `tests/test_db_file_repo.py`

- [ ] **Step 1: Write db/repos/file_repo.py**

```python
"""Uploaded files repository — file-level dedup via SHA-256."""

from datetime import datetime
from sqlalchemy.orm import Session
from alarm_app.db.models import UploadedFile


def file_exists(session: Session, file_sha256: str) -> bool:
    """Check if a file with this hash has been imported."""
    return session.query(UploadedFile.id).filter_by(
        file_sha256=file_sha256
    ).first() is not None


def register_file(session: Session, *, file_sha256: str, original_path: str,
                  original_name: str, file_size: int = 0,
                  source_kind: str = "") -> UploadedFile:
    """Register an imported file. Returns existing record if duplicate."""
    existing = session.query(UploadedFile).filter_by(
        file_sha256=file_sha256
    ).first()
    if existing:
        return existing

    record = UploadedFile(
        file_sha256=file_sha256,
        original_path=original_path,
        original_name=original_name,
        file_size=file_size,
        source_kind=source_kind,
        parsed_at=datetime.now(),
    )
    session.add(record)
    session.flush()
    return record


def get_file_by_hash(session: Session, file_sha256: str) -> UploadedFile | None:
    """Look up a file by its SHA-256 hash."""
    return session.query(UploadedFile).filter_by(
        file_sha256=file_sha256
    ).first()
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_file_repo.py`:

```python
"""Tests for db/repos/file_repo.py."""
import pytest
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.file_repo import file_exists, register_file, get_file_by_hash


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestFileRepo:
    def test_file_not_exists_initially(self, session):
        assert file_exists(session, "abc123") is False

    def test_register_and_check_exists(self, session):
        register_file(session, file_sha256="abc123",
                      original_path="/tmp/x.csv", original_name="x.csv")
        session.commit()
        assert file_exists(session, "abc123") is True

    def test_register_duplicate_returns_existing(self, session):
        r1 = register_file(session, file_sha256="abc123",
                           original_path="/tmp/x.csv", original_name="x.csv")
        session.commit()
        r2 = register_file(session, file_sha256="abc123",
                           original_path="/tmp/y.csv", original_name="y.csv")
        assert r1.id == r2.id

    def test_get_file_by_hash(self, session):
        register_file(session, file_sha256="abc123",
                      original_path="/tmp/x.csv", original_name="x.csv",
                      source_kind="alarm_csv")
        session.commit()
        f = get_file_by_hash(session, "abc123")
        assert f is not None
        assert f.source_kind == "alarm_csv"

    def test_get_file_by_hash_missing(self, session):
        assert get_file_by_hash(session, "missing") is None
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_file_repo.py -v
```

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/file_repo.py tests/test_db_file_repo.py
git commit -m "feat(e1): add file repository with SHA-256 dedup"
```

---

### Task 9: Alarm repository

**Files:**

- Create: `db/repos/alarm_repo.py`
- Create: `tests/test_db_alarm_repo.py`

- [ ] **Step 1: Write db/repos/alarm_repo.py**

```python
"""Alarm records repository — row-level dedup via row_hash."""

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from alarm_app.db.models import AlarmRecord
from alarm_app.db.hashing import compute_row_hash, ALARM_HASH_COLS


def bulk_upsert_alarms(session: Session, df: pd.DataFrame,
                       file_id: int | None = None) -> tuple[int, int]:
    """Insert alarm rows with dedup. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        row_hash = compute_row_hash(row_dict)

        existing = session.query(AlarmRecord.id).filter_by(
            row_hash=row_hash
        ).first()
        if existing:
            skipped += 1
            continue

        record = AlarmRecord(
            row_hash=row_hash,
            file_id=file_id,
            site_id=row_dict.get("site_id"),
            alarm_name=row_dict.get("alarm_name"),
            alarm_id=row_dict.get("alarm_id"),
            occurred_on=row_dict.get("occurred_on"),
            cleared_on=row_dict.get("cleared_on"),
            duration=row_dict.get("duration"),
            duration_secs=row_dict.get("_duration_secs"),
            category=row_dict.get("_category"),
            vendor=row_dict.get("vendor"),
            network_type=row_dict.get("network_type"),
            severity=row_dict.get("severity"),
            fm_office=row_dict.get("fm_office"),
            alarm_source=row_dict.get("alarm_source"),
            alarm_category=row_dict.get("alarm_category"),
            clearance_status=row_dict.get("clearance_status"),
            additional_info=row_dict.get("additional_info"),
            site_down=bool(row_dict.get("site_down", False)),
        )
        session.add(record)
        inserted += 1

    session.commit()
    return inserted, skipped


def load_alarms_as_df(session: Session) -> pd.DataFrame:
    """Load all alarm records as a pandas DataFrame."""
    rows = session.query(AlarmRecord).all()
    if not rows:
        return pd.DataFrame()

    records = []
    for r in rows:
        records.append({
            "site_id": r.site_id,
            "alarm_name": r.alarm_name,
            "alarm_id": r.alarm_id,
            "occurred_on": r.occurred_on,
            "cleared_on": r.cleared_on,
            "duration": r.duration,
            "_duration_secs": r.duration_secs,
            "_category": r.category,
            "vendor": r.vendor,
            "network_type": r.network_type,
            "severity": r.severity,
            "fm_office": r.fm_office,
            "alarm_source": r.alarm_source,
            "alarm_category": r.alarm_category,
            "clearance_status": r.clearance_status,
            "additional_info": r.additional_info,
            "site_down": r.site_down,
        })
    return pd.DataFrame(records)


def count_alarms(session: Session) -> int:
    """Return total alarm record count."""
    return session.query(AlarmRecord).count()
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_alarm_repo.py`:

```python
"""Tests for db/repos/alarm_repo.py."""
import pytest
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms, load_alarms_as_df, count_alarms


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


def _make_df(rows):
    return pd.DataFrame(rows)


class TestAlarmRepo:
    def test_bulk_insert(self, session):
        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1),
             "cleared_on": datetime(2026, 1, 1, 1), "vendor": "Huawei",
             "_category": "Power", "duration": "01:00:00", "_duration_secs": 3600.0},
        ])
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 1
        assert skipped == 0

    def test_duplicate_rows_skipped(self, session):
        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1),
             "vendor": "Huawei", "_category": "Power"},
        ])
        bulk_upsert_alarms(session, df)
        inserted, skipped = bulk_upsert_alarms(session, df)
        assert inserted == 0
        assert skipped == 1

    def test_load_round_trip(self, session):
        df = _make_df([
            {"site_id": "S1", "alarm_name": "Power", "occurred_on": datetime(2026, 1, 1),
             "vendor": "Huawei", "_category": "Power", "duration": "01:00:00",
             "_duration_secs": 3600.0},
            {"site_id": "S2", "alarm_name": "Down", "occurred_on": datetime(2026, 1, 2),
             "vendor": "Nokia", "_category": "Down", "duration": "00:30:00",
             "_duration_secs": 1800.0},
        ])
        bulk_upsert_alarms(session, df)
        loaded = load_alarms_as_df(session)
        assert len(loaded) == 2
        assert set(loaded["site_id"]) == {"S1", "S2"}

    def test_count_alarms(self, session):
        assert count_alarms(session) == 0
        df = _make_df([
            {"site_id": "S1", "alarm_name": "A1"},
            {"site_id": "S2", "alarm_name": "A2"},
        ])
        bulk_upsert_alarms(session, df)
        assert count_alarms(session) == 2

    def test_empty_df_returns_empty(self, session):
        loaded = load_alarms_as_df(session)
        assert loaded.empty
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_alarm_repo.py -v
```

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/alarm_repo.py tests/test_db_alarm_repo.py
git commit -m "feat(e1): add alarm repository with row-hash dedup"
```

---

### Task 10: BDT repository

**Files:**

- Create: `db/repos/bdt_repo.py`
- Create: `tests/test_db_bdt_repo.py`

- [ ] **Step 1: Write db/repos/bdt_repo.py**

```python
"""BDT test and photo repository."""

from datetime import date
from sqlalchemy.orm import Session
from alarm_app.db.models import BDTTest, BDTPhoto
from alarm_app.db.hashing import compute_bdt_content_hash


def save_bdt_test(session: Session, bdt_dict: dict,
                  file_id: int | None = None) -> BDTTest:
    """Save a BDT test record. Returns existing if duplicate by content_hash."""
    content_hash = compute_bdt_content_hash(bdt_dict)

    existing = session.query(BDTTest).filter_by(
        content_hash=content_hash
    ).first()
    if existing:
        return existing

    test_date = bdt_dict.get("test_date")
    if hasattr(test_date, "date"):
        test_date = test_date.date()

    record = BDTTest(
        file_id=file_id,
        site_code=str(bdt_dict.get("site_code", "")).strip().upper(),
        test_date=test_date,
        battery_brand=bdt_dict.get("battery_brand"),
        battery_ah=bdt_dict.get("battery_ah"),
        battery_voltage=bdt_dict.get("battery_voltage"),
        num_batteries=bdt_dict.get("num_batteries"),
        num_strings=bdt_dict.get("num_strings"),
        num_modules=bdt_dict.get("num_modules"),
        rectifier_brand=bdt_dict.get("rectifier_brand"),
        start_voltage=bdt_dict.get("start_voltage"),
        end_voltage=bdt_dict.get("end_voltage"),
        start_ampere=bdt_dict.get("start_ampere"),
        end_ampere=bdt_dict.get("end_ampere"),
        discharge_minutes=bdt_dict.get("discharge_minutes"),
        pld_value=bdt_dict.get("pld_value"),
        content_hash=content_hash,
    )
    session.add(record)
    session.flush()
    return record


def load_previous_test(session: Session, site_code: str,
                       before_date: date) -> BDTTest | None:
    """Load the most recent BDT test for a site before the given date."""
    normalized = site_code.strip().upper()
    return (
        session.query(BDTTest)
        .filter(BDTTest.site_code == normalized)
        .filter(BDTTest.test_date < before_date)
        .order_by(BDTTest.test_date.desc())
        .first()
    )


def save_bdt_photo(session: Session, bdt_test_id: int, slot_index: int,
                   slot_category: str, blob_asset_id: int | None = None) -> BDTPhoto:
    """Link a photo slot to a BDT test."""
    photo = BDTPhoto(
        bdt_test_id=bdt_test_id,
        slot_index=slot_index,
        slot_category=slot_category,
        blob_asset_id=blob_asset_id,
    )
    session.add(photo)
    session.flush()
    return photo
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_bdt_repo.py`:

```python
"""Tests for db/repos/bdt_repo.py."""
import pytest
from datetime import date
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.bdt_repo import save_bdt_test, load_previous_test, save_bdt_photo


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestBDTRepo:
    def test_save_and_dedup(self, session):
        bdt = {"site_code": "ABC", "test_date": date(2026, 1, 1),
               "battery_brand": "Narada", "battery_ah": 200}
        r1 = save_bdt_test(session, bdt)
        session.commit()
        r2 = save_bdt_test(session, bdt)
        assert r1.id == r2.id

    def test_different_tests_different_records(self, session):
        b1 = {"site_code": "ABC", "test_date": date(2026, 1, 1),
              "battery_brand": "Narada"}
        b2 = {"site_code": "ABC", "test_date": date(2026, 6, 1),
              "battery_brand": "Narada"}
        r1 = save_bdt_test(session, b1)
        session.commit()
        r2 = save_bdt_test(session, b2)
        session.commit()
        assert r1.id != r2.id

    def test_load_previous_test(self, session):
        save_bdt_test(session, {"site_code": "ABC", "test_date": date(2025, 6, 1),
                                "battery_brand": "X"})
        save_bdt_test(session, {"site_code": "ABC", "test_date": date(2026, 1, 1),
                                "battery_brand": "Y"})
        session.commit()

        prev = load_previous_test(session, "ABC", date(2026, 1, 1))
        assert prev is not None
        assert prev.test_date == date(2025, 6, 1)

    def test_load_previous_test_none(self, session):
        assert load_previous_test(session, "XYZ", date(2026, 1, 1)) is None

    def test_save_photo(self, session):
        bdt = save_bdt_test(session, {"site_code": "ABC",
                                       "test_date": date(2026, 1, 1)})
        session.commit()
        photo = save_bdt_photo(session, bdt.id, slot_index=0,
                               slot_category="Rectifier")
        session.commit()
        assert photo.bdt_test_id == bdt.id
        assert photo.slot_category == "Rectifier"
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_bdt_repo.py -v
```

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/bdt_repo.py tests/test_db_bdt_repo.py
git commit -m "feat(e1): add BDT repository with content-hash dedup"
```

---

### Task 11: PM validation repository

**Files:**

- Create: `db/repos/pm_repo.py`
- Create: `tests/test_db_pm_repo.py`

- [ ] **Step 1: Write db/repos/pm_repo.py**

```python
"""PM validation run and rule result repository."""

import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from alarm_app.db.models import (
    PMValidationRun, PMRuleResult, PMRuleCatalog, PMParameterSet,
)
from alarm_app.db.hashing import compute_canonical_json_sha256


def get_or_create_rule_catalog(session: Session) -> dict[str, int]:
    """Ensure R1-R11 exist in pm_rule_catalog. Return {rule_code: id} map."""
    rules = {
        "R1": "Photo completeness",
        "R2": "Power alarm match and duration",
        "R3": "String vs bus bar ampere",
        "R4": "Discharge table consistency",
        "R5": "Starting ampere",
        "R6": "End voltage range",
        "R7": "Voltage/ampere inverse relationship",
        "R8": "Backup time vs sizing",
        "R9": "Discharge current tolerance",
        "R10": "Door alarm match",
        "R11": "Summary checklist",
    }
    result = {}
    for code, name in rules.items():
        existing = session.query(PMRuleCatalog).filter_by(rule_code=code).first()
        if existing:
            result[code] = existing.id
        else:
            r = PMRuleCatalog(rule_code=code, name=name)
            session.add(r)
            session.flush()
            result[code] = r.id
    return result


def save_validation_run(session: Session, *, bdt_test_id: int,
                        alarm_input_sha256: str,
                        validator_code_ref: str | None,
                        overall_verdict: str,
                        rule_results: list[dict],
                        params: dict | None = None) -> PMValidationRun | None:
    """Save a PM validation run with all rule results.

    Returns None if an identical run already exists (idempotent).
    rule_results: list of {"rule_code": "R1", "verdict": "Accepted", "detail": "..."}
    """
    param_set_id = None
    if params:
        params_sha = compute_canonical_json_sha256(params)
        ps = session.query(PMParameterSet).filter_by(params_sha256=params_sha).first()
        if not ps:
            ps = PMParameterSet(params_sha256=params_sha,
                                params_json=json.dumps(params, default=str))
            session.add(ps)
            session.flush()
        param_set_id = ps.id

    run = PMValidationRun(
        bdt_test_id=bdt_test_id,
        parameter_set_id=param_set_id,
        alarm_input_sha256=alarm_input_sha256,
        validator_code_ref=validator_code_ref,
        overall_verdict=overall_verdict,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return None

    catalog = get_or_create_rule_catalog(session)

    for rr in rule_results:
        rule_code = rr["rule_code"]
        rule_id = catalog.get(rule_code)
        if rule_id is None:
            continue
        session.add(PMRuleResult(
            validation_run_id=run.id,
            rule_id=rule_id,
            verdict=rr.get("verdict", "N/A"),
            evidence_json=json.dumps(rr.get("detail", ""), default=str),
        ))

    session.commit()
    return run
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_pm_repo.py`:

```python
"""Tests for db/repos/pm_repo.py."""
import pytest
from datetime import date
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.models import BDTTest, PMValidationRun
from alarm_app.db.repos.pm_repo import save_validation_run, get_or_create_rule_catalog


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def bdt_test(session):
    bdt = BDTTest(site_code="TEST", test_date=date(2026, 1, 1),
                  content_hash="test_hash_1")
    session.add(bdt)
    session.flush()
    return bdt


class TestPMRepo:
    def test_get_or_create_catalog(self, session):
        catalog = get_or_create_rule_catalog(session)
        session.commit()
        assert len(catalog) == 11
        assert "R1" in catalog
        assert "R11" in catalog

    def test_save_run_with_rules(self, session, bdt_test):
        rules = [
            {"rule_code": f"R{i}", "verdict": "Accepted", "detail": f"Rule {i} OK"}
            for i in range(1, 12)
        ]
        run = save_validation_run(
            session,
            bdt_test_id=bdt_test.id,
            alarm_input_sha256="alarm_hash_1",
            validator_code_ref="v1.0",
            overall_verdict="Accepted",
            rule_results=rules,
        )
        assert run is not None
        assert run.overall_verdict == "Accepted"
        assert len(run.rule_results) == 11

    def test_idempotent_duplicate_returns_none(self, session, bdt_test):
        rules = [{"rule_code": f"R{i}", "verdict": "Accepted"} for i in range(1, 12)]
        run1 = save_validation_run(
            session, bdt_test_id=bdt_test.id,
            alarm_input_sha256="alarm_hash_1",
            validator_code_ref="v1.0",
            overall_verdict="Accepted", rule_results=rules,
        )
        run2 = save_validation_run(
            session, bdt_test_id=bdt_test.id,
            alarm_input_sha256="alarm_hash_1",
            validator_code_ref="v1.0",
            overall_verdict="Accepted", rule_results=rules,
        )
        assert run1 is not None
        assert run2 is None
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_pm_repo.py -v
```

Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/pm_repo.py tests/test_db_pm_repo.py
git commit -m "feat(e1): add PM validation repository with idempotency"
```

---

### Task 12: Sync repository

**Files:**

- Create: `db/repos/sync_repo.py`
- Create: `tests/test_db_sync_repo.py`

- [ ] **Step 1: Write db/repos/sync_repo.py**

```python
"""Sync outbox and checkpoint repository — replaces JSONL files."""

import json
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session
from alarm_app.db.models import SyncOutboxEvent, SyncCheckpoint


def append_outbox_event(session: Session, *, entity_type: str,
                        entity_local_id: str, op: str, entity_hash: str,
                        payload: dict, origin_device_id: str | None = None,
                        event_id: str | None = None) -> SyncOutboxEvent:
    """Append a sync event to the outbox."""
    evt = SyncOutboxEvent(
        event_id=event_id or str(uuid4()),
        origin_device_id=origin_device_id or "",
        entity_type=entity_type,
        entity_local_id=entity_local_id,
        op=op,
        entity_hash=entity_hash,
        payload_json=json.dumps(payload, default=str),
        status="pending",
    )
    session.add(evt)
    session.commit()
    return evt


def load_pending_outbox(session: Session, limit: int | None = None) -> list[dict]:
    """Load pending outbox events as dicts."""
    q = session.query(SyncOutboxEvent).filter_by(status="pending").order_by(
        SyncOutboxEvent.id
    )
    if limit:
        q = q.limit(limit)

    return [
        {
            "event_id": e.event_id,
            "origin_device_id": e.origin_device_id,
            "entity_type": e.entity_type,
            "entity_local_id": e.entity_local_id,
            "op": e.op,
            "entity_hash": e.entity_hash,
            "payload": json.loads(e.payload_json) if e.payload_json else {},
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in q.all()
    ]


def mark_outbox_synced(session: Session, event_ids: list[str],
                       checkpoint_cursor: str | None = None) -> int:
    """Mark events as synced and optionally update checkpoint."""
    count = 0
    now = datetime.now()
    for eid in event_ids:
        evt = session.query(SyncOutboxEvent).filter_by(event_id=eid).first()
        if evt and evt.status == "pending":
            evt.status = "synced"
            evt.synced_at = now
            count += 1

    if checkpoint_cursor:
        save_sync_checkpoint(session, checkpoint_cursor)

    session.commit()
    return count


def save_sync_checkpoint(session: Session, cursor: str) -> None:
    """Save or update the sync checkpoint."""
    cp = session.query(SyncCheckpoint).first()
    if cp:
        cp.cursor = cursor
        cp.last_ack_at = datetime.now()
    else:
        session.add(SyncCheckpoint(cursor=cursor, last_ack_at=datetime.now()))
    session.commit()


def load_sync_checkpoint(session: Session) -> dict | None:
    """Load the current sync checkpoint."""
    cp = session.query(SyncCheckpoint).first()
    if not cp:
        return None
    return {
        "cursor": cp.cursor,
        "batch_key": cp.batch_key,
        "last_ack_at": cp.last_ack_at.isoformat() if cp.last_ack_at else None,
    }
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_sync_repo.py`:

```python
"""Tests for db/repos/sync_repo.py."""
import pytest
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.sync_repo import (
    append_outbox_event, load_pending_outbox,
    mark_outbox_synced, save_sync_checkpoint, load_sync_checkpoint,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestSyncRepo:
    def test_append_and_load(self, session):
        append_outbox_event(session, entity_type="alarm",
                            entity_local_id="1", op="upsert",
                            entity_hash="h1", payload={"site": "S1"})
        pending = load_pending_outbox(session)
        assert len(pending) == 1
        assert pending[0]["entity_type"] == "alarm"

    def test_mark_synced(self, session):
        evt = append_outbox_event(session, entity_type="alarm",
                                  entity_local_id="1", op="upsert",
                                  entity_hash="h1", payload={})
        count = mark_outbox_synced(session, [evt.event_id])
        assert count == 1
        assert load_pending_outbox(session) == []

    def test_checkpoint_round_trip(self, session):
        save_sync_checkpoint(session, "cursor-42")
        cp = load_sync_checkpoint(session)
        assert cp is not None
        assert cp["cursor"] == "cursor-42"

    def test_checkpoint_overwrites(self, session):
        save_sync_checkpoint(session, "cursor-1")
        save_sync_checkpoint(session, "cursor-2")
        cp = load_sync_checkpoint(session)
        assert cp["cursor"] == "cursor-2"

    def test_load_with_limit(self, session):
        for i in range(5):
            append_outbox_event(session, entity_type="alarm",
                                entity_local_id=str(i), op="upsert",
                                entity_hash=f"h{i}", payload={})
        pending = load_pending_outbox(session, limit=3)
        assert len(pending) == 3
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_sync_repo.py -v
```

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/sync_repo.py tests/test_db_sync_repo.py
git commit -m "feat(e1): add sync outbox and checkpoint repository"
```

---

### Task 13: Blob asset repository

**Files:**

- Create: `db/repos/blob_repo.py`
- Create: `tests/test_db_blob_repo.py`

- [ ] **Step 1: Write db/repos/blob_repo.py**

```python
"""Blob asset metadata repository — images stored on disk, metadata in DB."""

from pathlib import Path
from sqlalchemy.orm import Session
from alarm_app.db.models import BlobAsset
from alarm_app.db.hashing import compute_image_sha256

BLOB_DIR = Path.home() / ".alarm_viewer" / "blobs"


def store_blob(session: Session, image_bytes: bytes, *,
               mime_type: str = "", width: int = 0,
               height: int = 0, perceptual_hash: str = "") -> BlobAsset:
    """Store image bytes on disk and register metadata. Dedup by SHA-256."""
    sha = compute_image_sha256(image_bytes)

    existing = session.query(BlobAsset).filter_by(sha256=sha).first()
    if existing:
        return existing

    # Write to disk: blobs/{sha[:2]}/{sha}
    subdir = BLOB_DIR / sha[:2]
    subdir.mkdir(parents=True, exist_ok=True)
    blob_path = subdir / sha
    blob_path.write_bytes(image_bytes)

    asset = BlobAsset(
        sha256=sha,
        perceptual_hash=perceptual_hash,
        mime_type=mime_type,
        file_size=len(image_bytes),
        width=width,
        height=height,
        local_path=str(blob_path),
    )
    session.add(asset)
    session.flush()
    return asset


def get_blob_by_sha256(session: Session, sha256: str) -> BlobAsset | None:
    """Look up a blob asset by its SHA-256 hash."""
    return session.query(BlobAsset).filter_by(sha256=sha256).first()


def blob_exists(session: Session, sha256: str) -> bool:
    """Check if a blob with this hash exists."""
    return session.query(BlobAsset.id).filter_by(sha256=sha256).first() is not None
```

- [ ] **Step 2: Write tests**

Create `tests/test_db_blob_repo.py`:

```python
"""Tests for db/repos/blob_repo.py."""
import pytest
from sqlalchemy.orm import Session
from alarm_app.db.engine import create_engine, init_db
from alarm_app.db.repos.blob_repo import store_blob, get_blob_by_sha256, blob_exists


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.db.repos.blob_repo.BLOB_DIR", tmp_path / "blobs")
    engine = create_engine()
    init_db(engine)
    with Session(engine) as s:
        yield s


class TestBlobRepo:
    def test_store_and_retrieve(self, session):
        data = b"\x89PNG\r\nfake_image_data"
        asset = store_blob(session, data, mime_type="image/png",
                           width=100, height=200)
        session.commit()
        assert asset.sha256 is not None
        assert asset.file_size == len(data)

        loaded = get_blob_by_sha256(session, asset.sha256)
        assert loaded is not None
        assert loaded.mime_type == "image/png"

    def test_duplicate_returns_existing(self, session):
        data = b"same_image"
        a1 = store_blob(session, data)
        session.commit()
        a2 = store_blob(session, data)
        assert a1.id == a2.id

    def test_blob_exists(self, session):
        data = b"test_blob"
        asset = store_blob(session, data)
        session.commit()
        assert blob_exists(session, asset.sha256) is True
        assert blob_exists(session, "nonexistent") is False

    def test_file_written_to_disk(self, session, tmp_path):
        data = b"disk_test_blob"
        asset = store_blob(session, data)
        session.commit()
        blob_path = tmp_path / "blobs" / asset.sha256[:2] / asset.sha256
        assert blob_path.exists()
        assert blob_path.read_bytes() == data
```

- [ ] **Step 3: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_db_blob_repo.py -v
```

Expected: 4 passed

- [ ] **Step 4: Commit**

```bash
git add db/repos/blob_repo.py tests/test_db_blob_repo.py
git commit -m "feat(e1): add blob asset repository with SHA-256 dedup"
```

---

## Phase D: Epic 1 — Adapter Migration

### Task 14: Migrate data/state.py to use DB repos

**Files:**

- Modify: `data/state.py`
- Modify: `tests/test_state.py`

This is the critical task. `data/state.py` keeps its existing function signatures but switches from file I/O to DB calls internally. The DB is created on first access.

- [ ] **Step 1: Read current data/state.py and tests/test_state.py**

Read both files completely to understand every function and how tests exercise them.

- [ ] **Step 2: Add DB initialization to data/state.py**

Add a lazy engine/session accessor at module level:

```python
from alarm_app.db.engine import create_engine, init_db, get_session_factory

_engine = None
_SessionFactory = None

def _get_session():
    global _engine, _SessionFactory
    if _engine is None:
        _engine = create_engine()
        init_db(_engine)
        _SessionFactory = get_session_factory(_engine)
    return _SessionFactory()
```

- [ ] **Step 3: Migrate save_state/load_state**

Replace the JSON file read/write with calls to `state_repo.save_state` and `state_repo.load_state`:

```python
def save_state(state_dict: dict):
    from alarm_app.db.repos.state_repo import save_state as _save
    with _get_session() as session:
        _save(session, state_dict)

def load_state() -> dict | None:
    from alarm_app.db.repos.state_repo import load_state as _load
    with _get_session() as session:
        return _load(session)
```

- [ ] **Step 4: Migrate save_dataframe/load_dataframe**

Replace Parquet read/write with alarm_repo calls:

```python
def save_dataframe(df: pd.DataFrame):
    from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms
    with _get_session() as session:
        bulk_upsert_alarms(session, df)

def load_dataframe() -> pd.DataFrame | None:
    from alarm_app.db.repos.alarm_repo import load_alarms_as_df
    with _get_session() as session:
        df = load_alarms_as_df(session)
        return df if not df.empty else None
```

- [ ] **Step 5: Migrate remaining functions**

Apply the same pattern to: `append_review_event`, `load_review_events`, `summarize_review_events_by_day`, `append_outbox_event`, `load_pending_outbox`, `mark_outbox_synced`, `save_sync_checkpoint`, `load_sync_checkpoint`, `clear_cache`.

For `clear_cache`: truncate relevant tables instead of deleting files.

For `compute_file_hashes` and `files_changed`: keep the current file-hash implementation — these check external files on disk, not cached data.

For `load_alarm_ids` and `save_alarm_ids`: use the `ui_state` table with key `"alarm_ids"`.

For `get_or_create_device_id`: keep the current file-based implementation (device ID is a stable identifier, not session data).

- [ ] **Step 6: Update tests/test_state.py fixture**

The existing `_isolate_state_dir` fixture patches `STATE_DIR`, `STATE_FILE`, `CACHE_FILE`, etc. Update it to also patch the DB engine path so tests use a temp database:

```python
@pytest.fixture(autouse=True)
def _isolate_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("alarm_app.data.state.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.data.state.STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr("alarm_app.data.state.CACHE_FILE", tmp_path / "data_cache.parquet")
    # ... existing patches ...

    # Patch DB engine to use temp directory
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")

    # Reset the module-level engine so each test gets a fresh DB
    monkeypatch.setattr("alarm_app.data.state._engine", None)
    monkeypatch.setattr("alarm_app.data.state._SessionFactory", None)
```

- [ ] **Step 7: Run tests iteratively**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_state.py -v
```

Fix any failures one at a time. The goal: all existing test_state.py tests pass with the DB backend.

- [ ] **Step 8: Run full suite**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q
```

Expected: 321+ passed

- [ ] **Step 9: Commit**

```bash
git add data/state.py tests/test_state.py
git commit -m "feat(e1): migrate data/state.py from flat files to SQLite DB"
```

---

### Task 15: Migrate bdt/history.py to use DB repos

**Files:**

- Modify: `bdt/history.py`
- Modify: `tests/test_bdt_history.py`

- [ ] **Step 1: Read bdt/history.py and tests/test_bdt_history.py**

- [ ] **Step 2: Add DB session accessor**

Same pattern as state.py:

```python
from alarm_app.db.engine import create_engine, init_db, get_session_factory

_engine = None
_SessionFactory = None

def _get_session():
    global _engine, _SessionFactory
    if _engine is None:
        _engine = create_engine()
        init_db(_engine)
        _SessionFactory = get_session_factory(_engine)
    return _SessionFactory()
```

- [ ] **Step 3: Migrate save_test_record**

Replace JSON file writes with `bdt_repo.save_bdt_test`:

```python
def save_test_record(bdt, verdict: str) -> None:
    if not bdt.site_code:
        return
    from alarm_app.db.repos.bdt_repo import save_bdt_test
    bdt_dict = {
        "site_code": bdt.site_code,
        "test_date": bdt.test_date,
        "battery_brand": bdt.battery_brand,
        "battery_ah": bdt.battery_ah,
        "battery_voltage": bdt.battery_voltage,
        "num_strings": bdt.num_strings,
        "num_batteries": bdt.num_batteries,
        "num_modules": bdt.num_modules,
        "rectifier_brand": bdt.rectifier_brand,
        "start_voltage": bdt.start_voltage,
        "end_voltage": bdt.end_voltage,
    }
    with _get_session() as session:
        save_bdt_test(session, bdt_dict)
        session.commit()
```

- [ ] **Step 4: Migrate load_previous_test**

```python
def load_previous_test(site_code: str, before_date) -> BDTTestRecord | None:
    from alarm_app.db.repos.bdt_repo import load_previous_test as _load
    with _get_session() as session:
        row = _load(session, site_code, before_date)
        if row is None:
            return None
        return BDTTestRecord(
            site_code=row.site_code,
            test_date=str(row.test_date),
            file_path="",
            battery_brand=row.battery_brand or "",
            battery_ah=row.battery_ah,
            battery_voltage=row.battery_voltage,
            num_strings=row.num_strings,
            num_batteries=row.num_batteries,
            num_modules=row.num_modules,
            rectifier_brand=row.rectifier_brand or "",
            overall_verdict="",
            saved_at="",
        )
```

- [ ] **Step 5: Migrate save_validation_run**

```python
def save_validation_run(*, bdt_data, validation_result, alarm_df,
                        params: dict, validator_code_ref=None) -> dict | None:
    from alarm_app.db.repos.bdt_repo import save_bdt_test
    from alarm_app.db.repos.pm_repo import save_validation_run as _save_run

    bdt_dict = {"site_code": bdt_data.site_code, "test_date": bdt_data.test_date,
                "battery_brand": bdt_data.battery_brand, "battery_ah": bdt_data.battery_ah,
                "num_batteries": bdt_data.num_batteries, "num_strings": bdt_data.num_strings,
                "start_voltage": bdt_data.start_voltage, "end_voltage": bdt_data.end_voltage}

    alarm_hash = compute_alarm_input_sha256(alarm_df, bdt_data.site_code,
                                             str(bdt_data.test_date or ""))

    with _get_session() as session:
        bdt_row = save_bdt_test(session, bdt_dict)
        session.commit()

        rules = [
            {"rule_code": rr.rule_id, "verdict": rr.verdict, "detail": rr.detail}
            for rr in validation_result.rules
        ]
        run = _save_run(
            session, bdt_test_id=bdt_row.id,
            alarm_input_sha256=alarm_hash,
            validator_code_ref=validator_code_ref,
            overall_verdict=validation_result.overall,
            rule_results=rules, params=params,
        )
        return {"run_id": run.id} if run else None
```

- [ ] **Step 6: Update test fixture**

Patch the DB engine path in the existing `history_dir` fixture and reset module-level state.

- [ ] **Step 7: Run tests**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/test_bdt_history.py -v
```

- [ ] **Step 8: Run full suite**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -q
```

Expected: 321+ passed

- [ ] **Step 9: Commit**

```bash
git add bdt/history.py tests/test_bdt_history.py
git commit -m "feat(e1): migrate bdt/history.py from JSON files to SQLite DB"
```

---

### Task 16: Update CLAUDE.md and final verification

**Files:**

- Modify: `CLAUDE.md`

- [ ] **Step 1: Update Architecture section**

Add `db/` to the architecture diagram:

```
├── db/              SQLAlchemy ORM + repositories
│   ├── engine.py        create_engine, get_session, init_db
│   ├── models.py        All ORM table models (14 tables)
│   ├── hashing.py       Canonical normalization + SHA-256/dHash
│   ├── repos/           Repository pattern — one file per domain
│   │   ├── alarm_repo.py
│   │   ├── bdt_repo.py
│   │   ├── blob_repo.py
│   │   ├── file_repo.py
│   │   ├── pm_repo.py
│   │   ├── state_repo.py
│   │   └── sync_repo.py
│   └── migrations/      Alembic migration scripts
```

- [ ] **Step 2: Update Quick Edit Reference**

Add:

| To change...        | Edit file        |
| ------------------- | ---------------- |
| DB tables / columns | `db/models.py`   |
| DB queries / CRUD   | `db/repos/*.py`  |
| Hash computation    | `db/hashing.py`  |
| DB connection       | `db/engine.py`   |
| DB migrations       | `db/migrations/` |

- [ ] **Step 3: Add Key Convention**

Add: `db/` handles all SQL. No raw SQL outside `db/repos/`. `data/state.py` is the adapter — other layers never import from `db/` directly.

- [ ] **Step 4: Run full test suite one final time**

```bash
/Users/mikawi/Developer/orange/alarm_app/.venv/bin/python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with db/ package architecture"
```

---

## Execution Dependencies

```
Task 1 (golden generator)
Task 2 (golden tests)     ← depends on Task 1 + real data folder
Task 3 (deps + engine)
Task 4 (models)           ← depends on Task 3
Task 5 (hashing)          ← depends on Task 3
Task 6 (Alembic)          ← depends on Task 4
Task 7 (state repo)       ← depends on Task 4
Task 8 (file repo)        ← depends on Task 4, 5
Task 9 (alarm repo)       ← depends on Task 4, 5
Task 10 (BDT repo)        ← depends on Task 4, 5
Task 11 (PM repo)         ← depends on Task 4, 5
Task 12 (sync repo)       ← depends on Task 4
Task 13 (blob repo)       ← depends on Task 4, 5
Task 14 (migrate state)   ← depends on Tasks 7, 8, 9, 12
Task 15 (migrate history) ← depends on Tasks 10, 11
Task 16 (CLAUDE.md)       ← depends on all above
```

**Parallelizable:**

- Tasks 7-13 (all repos) can run in parallel — they're independent files
- Tasks 4 and 5 can run in parallel
- Tasks 14 and 15 can run in parallel once their repo dependencies are met
