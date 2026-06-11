"""Tests for all 9 repository modules — exercises the public APIs end-to-end.

Each test uses a fresh in-memory-ish SQLite engine (via tmp_path STATE_DIR)
so the suite is hermetic.
"""


import pandas as pd
import pytest
from sqlalchemy.orm import Session

from services.persistence import engine as engine_module
from services.persistence.models import Base
from services.persistence.repos import (
    alarm_repo,
    bdt_repo,
    blob_repo,
    catalog_repo,
    file_repo,
    pm_repo,
    state_repo,
    sync_repo,
)


@pytest.fixture
def engine_and_session(tmp_path, monkeypatch):
    """Create a fresh SQLite engine, create all tables, yield a session."""
    monkeypatch.setattr(engine_module, "STATE_DIR", tmp_path)
    eng = engine_module.create_engine()
    Base.metadata.create_all(eng)
    session = Session(bind=eng)
    try:
        yield eng, session
    finally:
        session.close()
        eng.dispose()


# ── alarm_repo ────────────────────────────────────────────────

def test_alarm_bulk_upsert_and_load_as_df(engine_and_session):
    _, session = engine_and_session
    df = pd.DataFrame({
        "site_id": ["S1", "S2", "S3"],
        "alarm_id": ["A1", "A2", "A3"],
        "alarm_name": ["Power Down", "Power Down", "Cell Down"],
        "occurred_on": pd.to_datetime(["2025-01-15 10:00", "2025-01-15 11:00", "2025-01-15 12:00"]),
        "cleared_on": pd.to_datetime(["2025-01-15 10:30", "2025-01-15 11:30", "2025-01-15 13:00"]),
        "duration": ["00:30:00", "00:30:00", "01:00:00"],
        "duration_secs": [1800.0, 1800.0, 3600.0],
        "category": ["power", "power", "down"],
        "vendor": ["huawei", "huawei", "nokia"],
        "network_type": ["4G", "4G", "5G"],
        "severity": ["critical", "critical", "major"],
        "fm_office": ["FM1", "FM1", "FM2"],
        "alarm_source": ["BSC", "BSC", "RNC"],
        "alarm_category": ["Power", "Power", "Transmission"],
        "clearance_status": ["auto", "auto", "manual"],
        "additional_info": ["", "", ""],
        "site_down": [False, False, True],
    })
    alarm_repo.bulk_upsert_alarms(session, df)
    session.commit()
    loaded = alarm_repo.load_alarms_as_df(session)
    assert len(loaded) == 3
    assert set(loaded["site_id"]) == {"S1", "S2", "S3"}


def test_alarm_count(engine_and_session):
    _, session = engine_and_session
    assert alarm_repo.count_alarms(session) == 0
    df = pd.DataFrame({
        "site_id": ["S1", "S2"],
        "alarm_id": ["A1", "A2"],
        "alarm_name": ["P", "P"],
        "occurred_on": pd.to_datetime(["2025-01-15 10:00", "2025-01-15 11:00"]),
        "duration": ["00:30:00", "00:30:00"],
        "duration_secs": [1800.0, 1800.0],
    })
    alarm_repo.bulk_upsert_alarms(session, df)
    session.commit()
    assert alarm_repo.count_alarms(session) == 2


# ── state_repo ────────────────────────────────────────────────

def test_state_set_get_load(engine_and_session):
    _, session = engine_and_session
    state_repo.set_value(session, "theme", "dark")
    state_repo.set_value(session, "last_dir", "/Users/me/data")
    session.commit()
    assert state_repo.get_value(session, "theme") == "dark"
    assert state_repo.get_value(session, "missing", "default") == "default"
    state_dict = state_repo.load_state(session)
    assert state_dict["theme"] == "dark"
    assert state_dict["last_dir"] == "/Users/me/data"


def test_state_save_state_and_load_state(engine_and_session):
    _, session = engine_and_session
    state_repo.save_state(session, {"foo": 1, "bar": [1, 2, 3]})
    session.commit()
    loaded = state_repo.load_state(session)
    assert loaded == {"foo": 1, "bar": [1, 2, 3]}


# ── file_repo ─────────────────────────────────────────────────

def test_file_register_and_get(engine_and_session):
    _, session = engine_and_session
    assert file_repo.file_exists(session, "abc123") is False
    file_repo.register_file(
        session,
        file_sha256="abc123",
        original_path="/tmp/foo.csv",
        original_name="foo.csv",
        file_size=1024,
        source_kind="huawei",
    )
    session.commit()
    assert file_repo.file_exists(session, "abc123") is True
    f = file_repo.get_file_by_hash(session, "abc123")
    assert f is not None
    assert f.original_name == "foo.csv"


# ── blob_repo ─────────────────────────────────────────────────

def test_blob_store_and_retrieve(engine_and_session):
    _, session = engine_and_session
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    blob = blob_repo.store_blob(session, image_bytes, mime_type="image/png")
    session.commit()
    assert blob.sha256 is not None
    found = blob_repo.get_blob_by_sha256(session, blob.sha256)
    assert found is not None
    assert blob_repo.blob_exists(session, blob.sha256) is True


# ── pm_repo ───────────────────────────────────────────────────

def test_pm_rule_catalog_seed(engine_and_session):
    _, session = engine_and_session
    rules = pm_repo.get_or_create_rule_catalog(session)
    session.commit()
    assert isinstance(rules, dict)
    assert len(rules) > 0
    # Idempotent
    rules2 = pm_repo.get_or_create_rule_catalog(session)
    assert rules == rules2


# ── sync_repo ─────────────────────────────────────────────────

def test_sync_outbox_roundtrip(engine_and_session):
    _, session = engine_and_session
    sync_repo.append_outbox_event(
        session,
        entity_type="alarm",
        entity_local_id="42",
        op="upsert",
        entity_hash="deadbeef",
        payload={"a": 1},
        origin_device_id="dev-1",
        event_id="evt-1",
    )
    session.commit()
    pending = sync_repo.load_pending_outbox(session)
    assert len(pending) == 1
    assert pending[0]["event_id"] == "evt-1"

    marked = sync_repo.mark_outbox_synced(session, ["evt-1"])
    session.commit()
    assert marked == 1
    assert len(sync_repo.load_pending_outbox(session)) == 0


def test_sync_checkpoint_save_and_load(engine_and_session):
    _, session = engine_and_session
    sync_repo.save_sync_checkpoint(session, "cursor-abc")
    session.commit()
    loaded = sync_repo.load_sync_checkpoint(session)
    assert loaded is not None
    assert loaded["cursor"] == "cursor-abc"


# ── bdt_repo ──────────────────────────────────────────────────

def test_bdt_save_and_load_previous(engine_and_session):
    from datetime import date
    _, session = engine_and_session
    bdt_dict = {
        "site_code": "SITE001",
        "test_date": date(2025, 1, 15),
        "battery_brand": "Acme",
        "battery_ah": 100.0,
        "num_batteries": 4,
        "num_strings": 2,
        "start_voltage": 54.0,
        "end_voltage": 49.5,
    }
    bdt = bdt_repo.save_bdt_test(session, bdt_dict)
    session.commit()
    assert bdt.id is not None
    assert bdt.content_hash is not None
    # load_previous_test returns the most recent BDT BEFORE a given date
    from datetime import date
    prev = bdt_repo.load_previous_test(session, "SITE001", before_date=date(2025, 1, 16))
    assert prev is not None
    assert prev.id == bdt.id


# ── catalog_repo (DB-only part) ───────────────────────────────

def test_site_metadata_query_missing_returns_none(engine_and_session):
    _, session = engine_and_session
    result = catalog_repo.query_site_metadata(session, "DOES_NOT_EXIST")
    assert result is None
