"""Tests for DuckDB alarm store and state integration."""

from datetime import date, datetime

import pandas as pd
import pytest

import alarm_app.data.alarm_store as alarm_store
import alarm_app.data.state as state_mod


@pytest.fixture(autouse=True)
def _isolate_alarm_store_paths(tmp_path, monkeypatch):
    alarm_db = tmp_path / "alarms.duckdb"
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state_mod, "ALARM_DB_FILE", alarm_db)
    monkeypatch.setattr(state_mod, "ALARM_DB_FALLBACK_FILE", tmp_path / "alarms.local.duckdb")
    monkeypatch.setattr(state_mod, "ALARM_IDS_FILE", tmp_path / "alarm_ids.json")
    monkeypatch.setattr(state_mod, "DEVICE_ID_FILE", tmp_path / "device_id.txt")
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(state_mod, "_engine", None)
    monkeypatch.setattr(state_mod, "_SessionFactory", None)
    monkeypatch.setattr("alarm_app.db.engine._app_engine", None)
    monkeypatch.setattr("alarm_app.db.engine._app_session_factory", None)
    alarm_store.set_alarm_db_file(alarm_db)


def _seed_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "site_id": "A-01",
                "alarm_id": "100",
                "alarm_name": "AC Power Fail",
                "network_type": "RAN",
                "vendor": "Huawei",
                "occurred_on": datetime(2025, 1, 1, 10, 0, 0),
                "cleared_on": datetime(2025, 1, 1, 11, 0, 0),
                "duration": "",
                "clearance_status": "Active",
                "alarm_source": "A-01 / cell",
                "file_source": "power.csv",
            },
            {
                "site_id": "A-01",
                "alarm_id": "200",
                "alarm_name": "Site Down",
                "network_type": "RAN",
                "vendor": "Huawei",
                "occurred_on": datetime(2025, 1, 1, 10, 30, 0),
                "cleared_on": datetime(2025, 1, 1, 10, 35, 0),
                "duration": "00:05:00",
                "clearance_status": "Active",
                "alarm_source": "A-01 / transmission",
                "file_source": "down.csv",
            },
            {
                "site_id": "B02",
                "alarm_id": "100",
                "alarm_name": "AC Power Fail",
                "network_type": "CORE",
                "vendor": "Nokia",
                "occurred_on": datetime(2025, 1, 2, 9, 0, 0),
                "cleared_on": datetime(2025, 1, 2, 9, 20, 0),
                "duration": "00:20:00",
                "clearance_status": "Cleared",
                "alarm_source": "B02 / node",
                "file_source": "power_nokia.csv",
            },
            {
                "site_id": "C03",
                "alarm_id": "300",
                "alarm_name": "Door Open",
                "network_type": "RAN",
                "vendor": "Huawei",
                "occurred_on": datetime(2025, 1, 3, 8, 0, 0),
                "cleared_on": datetime(2025, 1, 3, 8, 5, 0),
                "duration": "00:05:00",
                "clearance_status": "Active",
                "alarm_source": "C03 / shelter door",
                "file_source": "door.csv",
            },
        ]
    )


def test_replace_alarm_table_persists_derived_fields(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["100"], "down": ["200"], "door": ["300"]},
    )
    alarm_store.replace_alarm_table(_seed_df())

    loaded = alarm_store.load_all_alarms()
    assert not loaded.empty
    assert {"_duration_secs", "alarm_category", "site_down_flag"}.issubset(loaded.columns)

    power = loaded[(loaded["site_id"] == "A-01") & (loaded["alarm_id"] == "100")].iloc[0]
    down = loaded[(loaded["site_id"] == "A-01") & (loaded["alarm_id"] == "200")].iloc[0]
    door = loaded[loaded["alarm_id"] == "300"].iloc[0]

    assert power["duration"] == "01:00:00"
    assert power["_duration_secs"] == pytest.approx(3600.0)
    assert power["alarm_category"] == "Power"
    assert down["alarm_category"] == "Down"
    assert door["alarm_category"] == "Door"
    assert power["site_down_flag"] == "Yes"
    assert down["site_down_flag"] == "Yes"
    assert door["site_down_flag"] == "No"


def test_replace_alarm_table_persists_temp_category(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["65036"], "down": [], "door": []},
    )
    df = pd.DataFrame(
        [
            {
                "site_id": "0810CA",
                "alarm_id": "65036",
                "alarm_name": "Shelter High Temperature",
                "network_type": "4G",
                "vendor": "HUAWEI",
                "occurred_on": datetime(2026, 2, 27, 23, 59, 3),
                "cleared_on": datetime(2026, 2, 28, 0, 1, 30),
                "duration": "00:02:27",
                "clearance_status": "Cleared",
                "alarm_source": "U_G_0810CA_TALBEYA-MAIN",
                "file_source": "HT-FEB-2026.xlsx",
                "alarm_category": "",
            }
        ]
    )

    alarm_store.replace_alarm_table(df)

    loaded = alarm_store.load_all_alarms()
    assert len(loaded) == 1
    assert loaded.iloc[0]["alarm_category"] == "Temp"


def test_stats_counts_temp_category(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["100"], "down": ["200"], "door": ["300"]},
    )
    df = pd.concat([
        _seed_df(),
        pd.DataFrame([
            {
                "site_id": "T04",
                "alarm_id": "65036",
                "alarm_name": "Shelter High Temperature",
                "network_type": "RAN",
                "vendor": "Huawei",
                "occurred_on": datetime(2025, 1, 4, 8, 0, 0),
                "cleared_on": datetime(2025, 1, 4, 8, 30, 0),
                "duration": "00:30:00",
                "clearance_status": "Cleared",
                "alarm_source": "T04 / shelter",
                "file_source": "temp.csv",
                "alarm_category": "Temp",
            }
        ]),
    ], ignore_index=True)
    alarm_store.replace_alarm_table(df)

    summary = alarm_store.stats()

    assert summary["temp"] == 1


def test_query_count_distinct_and_stats(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["100"], "down": ["200"], "door": ["300"]},
    )
    alarm_store.replace_alarm_table(_seed_df())

    query = alarm_store.AlarmQuery(
        site_text="A-01",
        category="Power",
        vendor="Huawei",
        network_type="RAN",
        min_duration_secs=1800,
        manual_days=[date(2025, 1, 1)],
        both_pd=True,
        site_scope_keys={"A01"},
        allowed_values={"clearance_status": {"Active"}},
    )
    rows = alarm_store.query_alarms(query)
    assert len(rows) == 1
    assert rows.iloc[0]["site_id"] == "A-01"
    assert alarm_store.count_alarms(query) == 1

    vendors = alarm_store.distinct_values("vendor")
    assert vendors == sorted(vendors)
    assert "Huawei" in vendors and "Nokia" in vendors

    summary = alarm_store.stats(query)
    assert summary["total"] == 1
    assert summary["power"] == 1
    assert summary["down"] == 0
    assert summary["sites"] == 1


def test_load_alarm_slice_for_bdt_uses_site_keys_and_dates(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["100"], "down": ["200"], "door": ["300"]},
    )
    alarm_store.replace_alarm_table(_seed_df())

    sliced = alarm_store.load_alarm_slice_for_bdt(
        site_codes=["a01"],
        date_from=datetime(2025, 1, 1),
        date_to=datetime(2025, 1, 1),
    )
    assert len(sliced) == 2
    assert set(sliced["site_id"].tolist()) == {"A-01"}


def test_state_save_and_load_reuses_alarm_store(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["100"], "down": ["200"], "door": ["300"]},
    )
    backend = state_mod.save_dataframe(_seed_df())
    loaded = state_mod.load_dataframe()

    assert backend == "duckdb"
    assert loaded is not None
    assert {"_duration_secs", "alarm_category", "site_down_flag"}.issubset(loaded.columns)
    assert len(loaded) == 4


def test_read_queries_gracefully_degrade_when_duckdb_is_locked(monkeypatch, tmp_path):
    alarm_store.set_alarm_db_file(tmp_path / "alarms.duckdb")
    alarm_store.ALARM_DB_FILE.write_text("", encoding="utf-8")
    monkeypatch.setattr(alarm_store, "_LOCK_WARNING_EMITTED", False)

    def _raise_lock(*, read_only=False):
        raise RuntimeError("Could not set lock on file")

    monkeypatch.setattr(alarm_store, "_connect", _raise_lock)

    query = alarm_store.AlarmQuery(limit=10, offset=0)
    assert alarm_store.query_alarms(query).empty
    assert alarm_store.count_alarms(query) == 0
    assert alarm_store.distinct_values("site_id") == []
    assert alarm_store.stats(query)["total"] == 0
    assert alarm_store.load_all_alarms().empty
    assert alarm_store.occurred_on_bounds() == (None, None)


def test_lock_warning_is_logged_once_until_connection_recovers(monkeypatch, caplog, tmp_path):
    alarm_store.set_alarm_db_file(tmp_path / "alarms.duckdb")
    alarm_store.ALARM_DB_FILE.write_text("", encoding="utf-8")
    monkeypatch.setattr(alarm_store, "_LOCK_WARNING_EMITTED", False)

    def _raise_lock(*, read_only=False):
        raise RuntimeError("Could not set lock on file")

    monkeypatch.setattr(alarm_store, "_connect", _raise_lock)

    with caplog.at_level("WARNING"):
        assert alarm_store._safe_connect(read_only=True) is None
        assert alarm_store._safe_connect(read_only=True) is None

    warnings = [rec for rec in caplog.records if "Alarm store connection failed" in rec.getMessage()]
    assert len(warnings) == 1
    assert "Could not set lock on file" in warnings[0].getMessage()
    assert warnings[0].exc_info is None

    class _DummyConn:
        def close(self):
            return None

    monkeypatch.setattr(alarm_store, "_connect", lambda *, read_only=False: _DummyConn())
    con = alarm_store._safe_connect(read_only=True)
    assert con is not None
    assert alarm_store._LOCK_WARNING_EMITTED is False


def test_alarm_store_serializes_reads_behind_active_write(monkeypatch):
    import threading
    import time

    events = []
    original_ensure = alarm_store._ensure_derived_fields

    def slow_ensure(df):
        events.append("write-start")
        time.sleep(0.1)
        events.append("write-end")
        return original_ensure(df)

    monkeypatch.setattr(alarm_store, "_ensure_derived_fields", slow_ensure)

    writer = threading.Thread(target=lambda: alarm_store.replace_alarm_table(_seed_df()))
    writer.start()
    while "write-start" not in events:
        time.sleep(0.005)

    alarm_store.load_all_alarms()
    writer.join()

    assert events == ["write-start", "write-end"]


def test_occurred_on_bounds_uses_alarm_store_read_lock(monkeypatch):
    calls = []

    class _LockCtx:
        def __enter__(self):
            calls.append("enter")

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")

    monkeypatch.setattr(alarm_store, "_alarm_store_read_lock", lambda: _LockCtx())

    result = alarm_store.occurred_on_bounds()

    assert result == (None, None)
    assert calls == ["enter", "exit"]
