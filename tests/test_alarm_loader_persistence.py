from pathlib import Path

import pandas as pd
import pytest

from alarm_app.ui import threads


def test_alarm_cache_save_survives_sqlite_file_index_failure(monkeypatch, tmp_path):
    source_file = tmp_path / "alarm.csv"
    source_file.write_text("x", encoding="utf-8")

    saved = {"called": False, "rows": 0}

    def _save_dataframe(df):
        saved["called"] = True
        saved["rows"] = len(df)

    class _DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(threads.state, "save_dataframe", _save_dataframe)
    monkeypatch.setattr(threads, "_db_create_engine", lambda: object())
    monkeypatch.setattr(threads, "_db_init_db", lambda engine, include_alarm_records=False: None)
    monkeypatch.setattr(threads, "_db_get_session_factory", lambda engine: (lambda: _DummySession()))
    monkeypatch.setattr(threads, "compute_file_sha256", lambda fp: "sha")

    def _raise_register(*args, **kwargs):
        raise RuntimeError("sqlite locked")

    monkeypatch.setattr(threads, "_register_file", _raise_register)

    df = pd.DataFrame({"site_id": ["A001"], "alarm_name": ["Power"]})
    msg = threads._persist_alarm_cache_and_file_index(
        df,
        [(0, {"path": str(source_file), "filename": source_file.name})],
        set(),
    )

    assert saved == {"called": True, "rows": 1}
    assert "cached 1 alarm row(s) in DuckDB" in msg


def test_alarm_cache_message_reports_duckdb_failure(monkeypatch):
    monkeypatch.setattr(
        threads.state,
        "save_dataframe",
        lambda df: (_ for _ in ()).throw(RuntimeError("duckdb failed")),
    )
    monkeypatch.setattr(threads, "_db_create_engine", lambda: object())
    monkeypatch.setattr(threads, "_db_init_db", lambda engine, include_alarm_records=False: None)
    monkeypatch.setattr(threads, "_db_get_session_factory", lambda engine: (lambda: type("S", (), {"commit": lambda self: None, "close": lambda self: None})()))

    msg = threads._persist_alarm_cache_and_file_index(
        pd.DataFrame({"site_id": ["A001"]}),
        [],
        set(),
    )

    assert "warning: local alarm cache save failed" in msg


def test_alarm_cache_message_reports_pickle_backend(monkeypatch):
    monkeypatch.setattr(threads.state, "save_dataframe", lambda _df: "pickle")
    monkeypatch.setattr(threads, "_db_create_engine", lambda: object())
    monkeypatch.setattr(threads, "_db_init_db", lambda engine, include_alarm_records=False: None)
    monkeypatch.setattr(threads, "_db_get_session_factory", lambda engine: (lambda: type("S", (), {"commit": lambda self: None, "close": lambda self: None})()))

    msg = threads._persist_alarm_cache_and_file_index(
        pd.DataFrame({"site_id": ["A001"]}),
        [],
        set(),
    )

    assert "cached 1 alarm row(s) in local pickle cache" in msg
