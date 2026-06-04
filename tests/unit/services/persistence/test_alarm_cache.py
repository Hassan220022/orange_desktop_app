"""Tests for the DuckDB-backed alarm cache (consolidated from v1 data/state.py)."""

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

