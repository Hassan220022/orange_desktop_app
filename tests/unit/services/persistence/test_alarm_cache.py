"""Tests for the DuckDB-backed alarm cache (consolidated from v1 data/state.py)."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from services.persistence import alarm_cache


@pytest.fixture
def temp_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fake_store_factory():
    """Build a fake alarm-store module that records calls and lets tests inject failures."""

    def _build(replace=None, load=None):
        class FakeStore:
            def set_alarm_db_file(self, _path):
                pass

        fake = FakeStore()
        fake.replace_alarm_table = staticmethod(
            replace or (lambda _df: None)
        )
        fake.load_all_alarms = staticmethod(
            load or (lambda: pd.DataFrame())
        )
        return fake

    return _build


def test_has_alarm_cache_false_when_empty(temp_state_dir):
    assert alarm_cache.has_alarm_cache() is False


def test_save_and_load_dataframe_roundtrip(temp_state_dir):
    df = pd.DataFrame({"site_id": ["A", "B"], "alarm_id": ["X", "Y"]})
    backend = alarm_cache.save_dataframe(df)
    assert backend == "duckdb"
    loaded = alarm_cache.load_dataframe()
    assert loaded is not None
    assert len(loaded) == 2
    assert set(loaded["site_id"]) == {"A", "B"}


def test_load_dataframe_returns_none_when_empty(temp_state_dir):
    assert alarm_cache.load_dataframe() is None


def test_clear_cache_removes_files(temp_state_dir):
    df = pd.DataFrame({"site_id": ["A"], "alarm_id": ["X"]})
    alarm_cache.save_dataframe(df)
    assert alarm_cache.has_alarm_cache() is True
    alarm_cache.clear_cache()
    assert not alarm_cache.has_alarm_cache()


def test_save_dataframe_raises_alarm_cache_error_when_backend_fails(temp_state_dir):
    """If the DuckDB backend raises, the cache layer wraps it in AlarmCacheError."""
    from services.persistence.exceptions import AlarmCacheError

    df = pd.DataFrame({"site_id": ["A"], "alarm_id": ["X"]})

    def boom_replace(_df):
        raise RuntimeError("duckdb is unhappy")

    fake_store = type("FakeStore", (), {
        "set_alarm_db_file": staticmethod(lambda p: None),
        "replace_alarm_table": staticmethod(boom_replace),
    })()

    with patch.object(alarm_cache, "_alarm_store_module", return_value=fake_store):
        with pytest.raises(AlarmCacheError):
            alarm_cache.save_dataframe(df)


def test_alarm_store_module_falls_back_to_alarm_app_data_package(monkeypatch):
    """If the top-level `data` package is missing, the import falls back to `alarm_app.data`."""
    import builtins
    import importlib
    import sys

    # Drop the cached `data` top-level package so the fallback branch is taken.
    monkeypatch.delitem(sys.modules, "data", raising=False)
    real_import = builtins.__import__

    def _hooked(name, *args, **kwargs):
        if name == "data" or name.startswith("data."):
            raise ImportError(f"blocked: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _hooked)
    importlib.reload(alarm_cache)
    try:
        store = alarm_cache._alarm_store_module()
        assert store is not None
    finally:
        importlib.reload(alarm_cache)
        monkeypatch.setattr(builtins, "__import__", real_import)


def test_save_dataframe_swallows_oserror_on_fallback_unlink(temp_state_dir, fake_store_factory, monkeypatch):
    """If the fallback unlink raises OSError, the cache layer still returns 'duckdb'."""
    df = pd.DataFrame({"site_id": ["A"], "alarm_id": ["X"]})

    primary_calls = []

    def replace(_df):
        primary_calls.append(_df)

    def set_alarm_db_file(path):
        primary_calls.append(path)

    fake = type("FakeStore", (), {
        "set_alarm_db_file": staticmethod(set_alarm_db_file),
        "replace_alarm_table": staticmethod(replace),
    })()

    fallback_path = alarm_cache._alarm_db_fallback_file()
    monkeypatch.setattr(
        "pathlib.Path.unlink",
        lambda self, *a, **kw: (_ for _ in ()).throw(OSError("denied")) if self == fallback_path else None,
    )

    with patch.object(alarm_cache, "_alarm_store_module", return_value=fake):
        backend = alarm_cache.save_dataframe(df)

    assert backend == "duckdb"
    assert primary_calls  # save path was exercised at least once


def test_load_dataframe_skips_unreadable_candidate_and_returns_next(temp_state_dir, fake_store_factory):
    """If the first candidate raises, load_dataframe tries the next one."""
    import time

    primary = alarm_cache._alarm_db_file()
    fallback = alarm_cache._alarm_db_fallback_file()
    primary.write_text("placeholder")
    fallback.write_text("placeholder")
    # Make the primary the newer file so it is tried first
    time.sleep(0.01)
    primary.touch()

    call_log = []

    def set_alarm_db_file(path):
        call_log.append(path)

    def load_all_alarms():
        path_seen = call_log[-1]
        if path_seen == primary:
            raise RuntimeError("primary corrupt")
        return pd.DataFrame({"site_id": ["Z"]})

    fake = type("FakeStore", (), {
        "set_alarm_db_file": staticmethod(set_alarm_db_file),
        "load_all_alarms": staticmethod(load_all_alarms),
    })()

    with patch.object(alarm_cache, "_alarm_store_module", return_value=fake):
        result = alarm_cache.load_dataframe()

    assert result is not None
    assert list(result["site_id"]) == ["Z"]
    # Both candidates were probed (order-agnostic)
    assert {primary, fallback}.issubset(set(call_log))


def test_clear_cache_swallows_oserror(tmp_path, monkeypatch):
    """clear_cache must not raise even when unlink() errors out (e.g. permission denied)."""
    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)
    monkeypatch.setattr(
        "pathlib.Path.unlink",
        lambda self, *a, **kw: (_ for _ in ()).throw(OSError("locked")) if self.name == "alarms.duckdb" else None,
    )
    alarm_cache.clear_cache()  # should silently pass


# ── clear_all_caches ──────────────────────────────────────────
# Wipes BOTH the DuckDB alarm cache AND the SQLite derived tables
# (alarm_records, bdt_tests, bdt_photos, blob_assets, pm_validation_runs,
# pm_rule_results, bdt_summary_catalog) plus the per-site BDT history JSON
# files. See "Clear cached data" feature — user request:
# "do you know that clearing cache mean clean database as well".


@pytest.fixture
def clear_all_caches_home(tmp_path, monkeypatch):
    """Per-test HOME for clear_all_caches tests.

    The persistence engine's ``STATE_DIR`` is a module-level reference in
    ``services.persistence.engine`` that the engine singleton binds at
    first use, so monkeypatching only ``alarm_cache.STATE_DIR`` is not
    enough.  This fixture rebinds STATE_DIR on every module that holds a
    reference and resets the engine singleton so each test gets a fresh
    SQLite file.
    """
    from services.persistence import engine as engine_mod

    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)
    monkeypatch.setattr(engine_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(engine_mod, "_app_engine", None)
    monkeypatch.setattr(engine_mod, "_app_session_factory", None)
    return tmp_path


def _seed_clearable_tables(session, *, salt: str = "") -> None:
    """Populate every clearable table with at least one row so we can
    assert they get wiped. ``salt`` is used to prefix the file_sha256 /
    row_hash / blob sha256 so multiple tests can run in the same
    process without hitting the UNIQUE constraints."""
    from datetime import date as _date
    import hashlib

    from services.persistence.models import (
        AlarmRecord, BDTTest, BDTPhoto, BlobAsset,
        PMRuleCatalog, PMRuleResult, PMValidationRun, UploadedFile,
    )

    def _h(prefix: str, length: int = 64) -> str:
        return hashlib.sha256(f"{prefix}{salt}".encode()).hexdigest()[:length]

    # uploaded_files is PRESERVED but is referenced by FK — need a row.
    uf = UploadedFile(
        file_sha256=_h("uf"),
        original_path=f"/tmp/{salt}.xlsx",
        original_name=f"{salt}.xlsx",
        file_size=10,
        source_kind="huawei_alarm",
    )
    session.add(uf)
    session.flush()
    session.add(AlarmRecord(row_hash=_h("ar"), file_id=uf.id))
    session.add(BDTTest(site_code=f"0167DE{salt[:3]}", test_date=_date(2026, 4, 1), file_id=uf.id))
    session.flush()
    bdt = session.query(BDTTest).first()
    session.add(BDTPhoto(bdt_test_id=bdt.id, slot_index=0))
    session.add(BlobAsset(sha256=_h("blob"), file_size=100, local_path="/tmp/x"))
    session.add(PMValidationRun(
        bdt_test_id=bdt.id, overall_verdict="PASS",
        alarm_input_sha256=_h("pm"), validator_code_ref="y",
    ))
    session.flush()
    vr = session.query(PMValidationRun).first()
    rule = session.query(PMRuleCatalog).first()
    if rule is not None:
        session.add(PMRuleResult(validation_run_id=vr.id, rule_id=rule.id, verdict="OK"))
    session.commit()


def _count_clearable_rows(session) -> dict[str, int]:
    from services.persistence.models import (
        AlarmRecord, BDTTest, BDTPhoto, BlobAsset,
        PMRuleResult, PMValidationRun, UploadedFile, PMRuleCatalog,
        BDTSummaryCatalog,
    )

    return {
        "alarm_records": session.query(AlarmRecord).count(),
        "bdt_tests": session.query(BDTTest).count(),
        "bdt_photos": session.query(BDTPhoto).count(),
        "blob_assets": session.query(BlobAsset).count(),
        "pm_validation_runs": session.query(PMValidationRun).count(),
        "pm_rule_results": session.query(PMRuleResult).count(),
        "bdt_summary_catalog": session.query(BDTSummaryCatalog).count(),
        "uploaded_files": session.query(UploadedFile).count(),
        "pm_rule_catalog": session.query(PMRuleCatalog).count(),
    }


def _seed_bdt_summary_catalog(session, *, salt: str = "") -> None:
    from datetime import date as _date
    import hashlib

    from services.persistence.models import BDTSummaryCatalog

    digest = hashlib.sha256(f"summary{salt}".encode()).hexdigest()
    session.add(BDTSummaryCatalog(
        site_id=f"0167DE{salt[:3]}",
        reporting_period=f"2026-W{salt or '00'}",
        week="W01",
        test_date=_date(2026, 4, 1),
        test_year=2026,
        content_hash=digest,
        original_headers_json="{}",
        raw_data_json="{}",
    ))
    session.commit()


def _seed_bdt_history_files(history_dir: Path) -> list[Path]:
    site_dir = history_dir / "0167DE"
    site_dir.mkdir(parents=True)
    files = [
        site_dir / "2026-01-11.json",
        site_dir / "2026-04-15.json",
        history_dir / "_pm_runs" / "abc.jsonl",
    ]
    files[-1].parent.mkdir(parents=True)
    for file_path in files:
        file_path.write_text("{}")
    return files


def test_clear_alarm_caches_removes_only_alarm_targets(clear_all_caches_home, monkeypatch):
    from bdt import history as bdt_history
    from services.persistence.engine import init_db

    init_db(alarm_cache._get_app_engine_for_test(), include_alarm_records=True)
    session = alarm_cache._get_shared_session_for_test()
    _seed_clearable_tables(session, salt="alarmonly")
    _seed_bdt_summary_catalog(session, salt="alarmonly")
    before = _count_clearable_rows(session)
    session.close()

    alarm_cache._alarm_db_file().write_text("primary")
    alarm_cache._alarm_db_fallback_file().write_text("fallback")
    history_dir = clear_all_caches_home / "bdt_history"
    history_files = _seed_bdt_history_files(history_dir)
    monkeypatch.setattr(bdt_history, "HISTORY_DIR", history_dir)

    summary = alarm_cache.clear_alarm_caches()

    assert summary == {"alarm_duckdb_files": 2, "alarm_records": 1}
    assert not alarm_cache._alarm_db_file().exists()
    assert not alarm_cache._alarm_db_fallback_file().exists()
    assert all(path.exists() for path in history_files)

    session = alarm_cache._get_shared_session_for_test()
    after = _count_clearable_rows(session)
    session.close()

    assert after["alarm_records"] == 0
    for key in (
        "bdt_tests", "bdt_photos", "blob_assets", "pm_validation_runs",
        "pm_rule_results", "bdt_summary_catalog", "uploaded_files", "pm_rule_catalog",
    ):
        assert after[key] == before[key], key


def test_clear_bdt_caches_removes_only_bdt_targets(clear_all_caches_home, monkeypatch):
    from bdt import history as bdt_history
    from services.persistence.engine import init_db

    init_db(alarm_cache._get_app_engine_for_test(), include_alarm_records=True)
    session = alarm_cache._get_shared_session_for_test()
    _seed_clearable_tables(session, salt="bdtonly")
    _seed_bdt_summary_catalog(session, salt="bdtonly")
    before = _count_clearable_rows(session)
    session.close()

    alarm_cache._alarm_db_file().write_text("primary")
    alarm_cache._alarm_db_fallback_file().write_text("fallback")
    history_dir = clear_all_caches_home / "bdt_history"
    _seed_bdt_history_files(history_dir)
    monkeypatch.setattr(bdt_history, "HISTORY_DIR", history_dir)

    summary = alarm_cache.clear_bdt_caches()

    assert summary["bdt_history_files"] == 3
    assert summary["bdt_tests"] == 1
    assert summary["bdt_photos"] == 1
    assert summary["blob_assets"] == 1
    assert summary["pm_validation_runs"] == 1
    assert summary["pm_rule_results"] == 1
    assert summary["bdt_summary_catalog"] == 1
    assert alarm_cache._alarm_db_file().exists()
    assert alarm_cache._alarm_db_fallback_file().exists()
    assert all(not path.is_file() for path in history_dir.rglob("*"))

    session = alarm_cache._get_shared_session_for_test()
    after = _count_clearable_rows(session)
    session.close()

    assert after["alarm_records"] == before["alarm_records"]
    assert after["uploaded_files"] == before["uploaded_files"]
    assert after["pm_rule_catalog"] == before["pm_rule_catalog"]
    for key in (
        "bdt_tests", "bdt_photos", "blob_assets", "pm_validation_runs",
        "pm_rule_results", "bdt_summary_catalog",
    ):
        assert after[key] == 0, key


def test_clear_all_caches_returns_expected_keys(tmp_path, monkeypatch):
    """clear_all_caches returns a summary dict with one entry per target
    (DuckDB files, BDT history files, and each SQLite table)."""
    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)

    summary = alarm_cache.clear_all_caches()

    expected = {
        "alarm_duckdb_files",
        "bdt_history_files",
        "alarm_records",
        "bdt_tests",
        "bdt_photos",
        "blob_assets",
        "pm_validation_runs",
        "pm_rule_results",
        "bdt_summary_catalog",
    }
    assert set(summary.keys()) == expected
    for k, v in summary.items():
        assert v >= 0, f"clear_all_caches: {k} failed (value={v})"


def test_clear_all_caches_removes_duckdb_files(tmp_path, monkeypatch):
    """The DuckDB alarm cache files (primary + fallback) are removed."""
    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)

    df = pd.DataFrame({"site_id": ["A"], "alarm_id": ["X"]})
    alarm_cache.save_dataframe(df)
    assert alarm_cache.has_alarm_cache() is True

    summary = alarm_cache.clear_all_caches()
    assert summary["alarm_duckdb_files"] >= 1
    assert alarm_cache.has_alarm_cache() is False


def test_clear_all_caches_wipes_clearable_tables(clear_all_caches_home):
    """Every clearable SQLite table is wiped; preserved tables keep their rows."""
    from services.persistence.engine import init_db
    from services.persistence.models import (
        AlarmRecord, BDTTest, BDTPhoto, BlobAsset,
        PMRuleResult, PMValidationRun, UploadedFile, PMRuleCatalog,
    )

    init_db(alarm_cache._get_app_engine_for_test(), include_alarm_records=True)
    session = alarm_cache._get_shared_session_for_test()
    _seed_clearable_tables(session, salt="wipe")
    session.close()

    # Sanity: rows exist
    session = alarm_cache._get_shared_session_for_test()
    assert session.query(AlarmRecord).count() == 1
    assert session.query(BDTTest).count() == 1
    assert session.query(BDTPhoto).count() == 1
    assert session.query(BlobAsset).count() == 1
    assert session.query(PMValidationRun).count() == 1
    assert session.query(PMRuleResult).count() == 1
    # Preserved tables have rows from the seed
    uploaded_before = session.query(UploadedFile).count()
    rules_before = session.query(PMRuleCatalog).count()
    assert uploaded_before >= 1
    assert rules_before >= 1
    session.close()

    summary = alarm_cache.clear_all_caches()

    session = alarm_cache._get_shared_session_for_test()
    assert session.query(AlarmRecord).count() == 0
    assert session.query(BDTTest).count() == 0
    assert session.query(BDTPhoto).count() == 0
    assert session.query(BlobAsset).count() == 0
    assert session.query(PMValidationRun).count() == 0
    assert session.query(PMRuleResult).count() == 0
    # Preserved: dedup index + rule defs untouched
    assert session.query(UploadedFile).count() == uploaded_before
    assert session.query(PMRuleCatalog).count() == rules_before
    session.close()

    assert summary["alarm_records"] == 1
    assert summary["bdt_tests"] == 1
    assert summary["bdt_photos"] == 1
    assert summary["blob_assets"] == 1
    assert summary["pm_validation_runs"] == 1
    assert summary["pm_rule_results"] == 1


def test_clear_all_caches_respects_fk_order(clear_all_caches_home):
    """clear_all_caches handles FK constraints: bdt_photos and pm_validation_runs
    are children of bdt_tests and must be removed BEFORE bdt_tests, otherwise
    SQLite (PRAGMA foreign_keys=ON) raises IntegrityError."""
    from services.persistence.engine import init_db
    from services.persistence.models import BDTTest, BDTPhoto, PMValidationRun, UploadedFile

    init_db(alarm_cache._get_app_engine_for_test(), include_alarm_records=True)
    session = alarm_cache._get_shared_session_for_test()
    _seed_clearable_tables(session, salt="fkorder")
    session.close()

    # If FK order is wrong, this raises IntegrityError
    summary = alarm_cache.clear_all_caches()

    assert summary["bdt_tests"] == 1
    assert summary["bdt_photos"] == 1
    assert summary["pm_validation_runs"] == 1
    # No errors recorded (value of -1 is the error marker)
    for k, v in summary.items():
        assert v != -1, f"{k} raised during clear_all_caches"


def test_clear_all_caches_removes_bdt_history_files(tmp_path, monkeypatch):
    """Per-site BDT history JSON files are removed."""
    from bdt import history as bdt_history
    history_dir = tmp_path / "bdt_history"
    history_dir.mkdir()
    site_dir = history_dir / "0167DE"
    site_dir.mkdir()
    (site_dir / "2026-01-11.json").write_text("{}")
    (site_dir / "2026-04-15.json").write_text("{}")
    (history_dir / "_pm_runs").mkdir()
    (history_dir / "_pm_runs" / "abc.jsonl").write_text("{}")

    monkeypatch.setattr(bdt_history, "HISTORY_DIR", history_dir)

    summary = alarm_cache.clear_all_caches()
    assert summary["bdt_history_files"] == 3
    # Directory still exists, but is empty
    assert history_dir.exists()
    remaining = list(history_dir.rglob("*"))
    # Only the empty subdirs remain (no files)
    assert all(not p.is_file() for p in remaining)


def test_clear_all_caches_handles_missing_bdt_history_dir(tmp_path, monkeypatch):
    """If the BDT history dir does not exist (clean install), the call still
    succeeds and reports 0 files removed."""
    from bdt import history as bdt_history
    history_dir = tmp_path / "no_such_dir"
    monkeypatch.setattr(bdt_history, "HISTORY_DIR", history_dir)

    summary = alarm_cache.clear_all_caches()
    assert summary["bdt_history_files"] == 0


def test_clear_all_caches_survives_individual_table_failure(clear_all_caches_home, monkeypatch):
    """If one table's DELETE raises (e.g. transient DB error), the other
    tables are still cleared and the failure is recorded as -1 in the
    summary so the caller can surface it to the user."""
    from services.persistence import engine as engine_mod
    from services.persistence.engine import init_db
    from services.persistence.models import BDTTest

    init_db(alarm_cache._get_app_engine_for_test(), include_alarm_records=True)
    session = alarm_cache._get_shared_session_for_test()
    _seed_clearable_tables(session, salt="flaky")
    session.close()

    # Wrap session.query() so that querying the BDTTest model raises an
    # exception. The other models still work normally.
    from sqlalchemy.exc import OperationalError

    boom = OperationalError("simulated", {}, Exception("simulated DB failure"))
    real_get_shared_session = engine_mod.get_shared_session

    def flaky_query_session():
        s = real_get_shared_session()
        real_query = s.query

        def flaky_query(*args, **kwargs):
            if args and args[0] is BDTTest:
                raise boom
            return real_query(*args, **kwargs)

        s.query = flaky_query
        return s

    # Patch at the source — the clear function does `from .engine import
    # get_shared_session` inside the function body, so we patch the
    # attribute on the engine module itself.
    monkeypatch.setattr(engine_mod, "get_shared_session", flaky_query_session)

    summary = alarm_cache.clear_all_caches()
    # The simulated failure on bdt_tests is recorded as -1
    assert summary["bdt_tests"] == -1
    # The other tables cleared successfully
    assert summary["alarm_records"] == 1
    # The DuckDB and BDT history entries are still reported
    assert "alarm_duckdb_files" in summary
    assert "bdt_history_files" in summary

