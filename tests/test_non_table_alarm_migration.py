from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

import alarm_app.data.alarm_store as alarm_store
import alarm_app.data.state as state_mod
from alarm_app.bdt.validator import _find_door_alarms
from alarm_app.core.backup_time import compute_backup_times_for_query
from alarm_app.ui.panels.bdt_detail_panel import BdtDetailPanel
from alarm_app.ui.panels.bdt_validation_panel import BdtValidationPanel
from alarm_app.ui.threads import BDTValidationThread, BackupTimeThread


@pytest.fixture(autouse=True)
def _isolate_alarm_store_paths(tmp_path, monkeypatch):
    alarm_db = tmp_path / "alarms.duckdb"
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state_mod, "ALARM_DB_FILE", alarm_db)
    monkeypatch.setattr(state_mod, "ALARM_IDS_FILE", tmp_path / "alarm_ids.json")
    monkeypatch.setattr(state_mod, "DEVICE_ID_FILE", tmp_path / "device_id.txt")
    monkeypatch.setattr(state_mod, "_engine", None)
    monkeypatch.setattr(state_mod, "_SessionFactory", None)
    alarm_store.set_alarm_db_file(alarm_db)


def _seed_alarm_store(monkeypatch):
    monkeypatch.setattr(
        alarm_store,
        "_load_alarm_ids",
        lambda: {"power": ["100"], "down": ["200"], "door": ["300"]},
    )
    alarm_store.replace_alarm_table(
        pd.DataFrame(
            [
                {
                    "site_id": "A-01",
                    "alarm_id": "100",
                    "alarm_name": "AC Power Fail",
                    "network_type": "RAN",
                    "vendor": "Huawei",
                    "occurred_on": datetime(2026, 1, 5, 10, 0, 0),
                    "cleared_on": datetime(2026, 1, 5, 12, 0, 0),
                    "duration": "",
                    "alarm_source": "A-01 / power",
                    "file_source": "power.csv",
                },
                {
                    "site_id": "A-01",
                    "alarm_id": "200",
                    "alarm_name": "Site Down",
                    "network_type": "RAN",
                    "vendor": "Huawei",
                    "occurred_on": datetime(2026, 1, 5, 11, 30, 0),
                    "cleared_on": datetime(2026, 1, 5, 11, 45, 0),
                    "duration": "00:15:00",
                    "alarm_source": "A-01 / down",
                    "file_source": "down.csv",
                },
                {
                    "site_id": "A-01",
                    "alarm_id": "300",
                    "alarm_name": "Door Open",
                    "network_type": "RAN",
                    "vendor": "Huawei",
                    "occurred_on": datetime(2026, 1, 5, 9, 0, 0),
                    "cleared_on": datetime(2026, 1, 5, 9, 5, 0),
                    "duration": "00:05:00",
                    "alarm_source": "A-01 / door",
                    "file_source": "door.csv",
                },
                {
                    "site_id": "B-02",
                    "alarm_id": "100",
                    "alarm_name": "AC Power Fail",
                    "network_type": "RAN",
                    "vendor": "Nokia",
                    "occurred_on": datetime(2026, 1, 5, 10, 0, 0),
                    "cleared_on": datetime(2026, 1, 5, 13, 0, 0),
                    "duration": "03:00:00",
                    "alarm_source": "B-02 / power",
                    "file_source": "power_b.csv",
                },
                {
                    "site_id": "C-03",
                    "alarm_id": "300",
                    "alarm_name": "Door Open",
                    "network_type": "RAN",
                    "vendor": "Huawei",
                    "occurred_on": datetime(2026, 2, 10, 9, 0, 0),
                    "cleared_on": datetime(2026, 2, 10, 9, 5, 0),
                    "duration": "00:05:00",
                    "alarm_source": "C-03 / door",
                    "file_source": "door_c.csv",
                },
            ]
        )
    )


def test_bdt_validation_thread_queries_targeted_alarm_subset(monkeypatch):
    _seed_alarm_store(monkeypatch)

    parsed_bdt = SimpleNamespace(
        filename="BDT_A01.xlsx",
        file_path="/tmp/BDT_A01.xlsx",
        site_code="A-01",
        test_date=pd.Timestamp("2026-01-05"),
        errors=[],
        discharge_readings=[("60 min", 48.0, 10.0)],
        start_voltage=54.0,
        start_ampere=8.0,
        photos_deferred=False,
        summary_data={},
    )
    captured = {}

    def fake_validate(bdt_data, alarm_df, tolerance, health_pct):
        captured["alarm_df"] = alarm_df.copy()
        return SimpleNamespace(
            filename=bdt_data.filename,
            site_code=bdt_data.site_code,
            test_date="2026-01-05",
            overall="Accepted",
            rules=[],
            parse_errors=[],
            bdt_data=bdt_data,
        )

    monkeypatch.setattr("alarm_app.data.state.append_outbox_events", lambda *_args, **_kwargs: None)

    with patch("alarm_app.data.loaders._load_external_summary_lookup", return_value={}), \
         patch("alarm_app.bdt.parser.parse_bdt_file", return_value=parsed_bdt), \
         patch("alarm_app.bdt.validator.validate_bdt", side_effect=fake_validate), \
         patch("alarm_app.bdt.history.save_validation_batch", return_value=([], [], [])):
        thread = BDTValidationThread(["/tmp/BDT_A01.xlsx"], None, 0.15, 0.80)
        thread.run()

    alarm_df = captured["alarm_df"]
    assert not alarm_df.empty
    assert set(alarm_df["site_id"]) == {"A-01"}
    assert set(alarm_df["alarm_category"]) == {"Power", "Down", "Door"}


def test_pm_accept_alarm_subset_query_loads_only_matching_sites_and_dates(monkeypatch):
    _seed_alarm_store(monkeypatch)

    pm_df = pd.DataFrame(
        {
            "Site Code": ["A-01", "C-03"],
            "Actual Done Date": ["2026-01-05", "2026-02-10"],
        }
    )

    subset = BdtValidationPanel._load_pm_accept_alarm_subset(pm_df, "Site Code", "Actual Done Date")

    assert set(subset["site_id"]) == {"A-01", "C-03"}
    assert subset["occurred_on"].min() >= pd.Timestamp("2026-01-04")
    assert subset["occurred_on"].max() < pd.Timestamp("2026-02-12")


def test_bdt_detail_panel_door_subset_uses_alarm_store(monkeypatch):
    _seed_alarm_store(monkeypatch)

    subset = BdtDetailPanel._load_door_alarm_subset("A-01", pd.Timestamp("2026-01-05"))
    doors = _find_door_alarms(subset, "A-01", pd.Timestamp("2026-01-05"))

    assert len(doors) == 1
    assert set(doors["site_id"]) == {"A-01"}
    assert set(doors["alarm_category"]) == {"Door"}


def test_compute_backup_times_for_query_uses_alarm_store_subset(monkeypatch):
    _seed_alarm_store(monkeypatch)

    result, err = compute_backup_times_for_query(
        alarm_store.AlarmQuery(site_scope_keys=["A-01"], sort_by="occurred_on")
    )

    assert err == ""
    assert len(result) == 1
    assert result.iloc[0]["site_id"] == "A-01"
    assert result.iloc[0]["backup_time"] == "01:30:00"


def test_backup_time_thread_supports_query_backed_execution(monkeypatch):
    _seed_alarm_store(monkeypatch)

    captured = {}
    thread = BackupTimeThread(
        df=None,
        alarm_query=alarm_store.AlarmQuery(site_scope_keys=["A-01"], sort_by="occurred_on"),
    )
    thread.finished.connect(lambda result, err: captured.update(result=result, err=err))
    thread.run()

    assert captured["err"] == ""
    assert len(captured["result"]) == 1
    assert captured["result"].iloc[0]["site_id"] == "A-01"
