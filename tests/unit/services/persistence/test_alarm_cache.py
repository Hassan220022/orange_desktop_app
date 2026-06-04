"""Tests for the DuckDB-backed alarm cache (consolidated from v1 data/state.py)."""

from unittest.mock import patch

import pandas as pd
import pytest

from services.persistence import alarm_cache


@pytest.fixture
def temp_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(alarm_cache, "STATE_DIR", tmp_path)
    return tmp_path


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
