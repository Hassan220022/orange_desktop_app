"""E2E tests for the alarm processing pipeline: load -> classify -> compute backup times -> persist."""

from pathlib import Path

import pandas as pd
import pytest

try:
    from alarm_app.bdt.history import save_test_record
    from alarm_app.bdt.parser import parse_bdt_file
    from alarm_app.bdt.validator import BDTTolerances, validate_bdt
    from alarm_app.core.backup_time import compute_backup_times
    from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
    from alarm_app.data.loaders import parse_alarm_file
    from alarm_app.data.state import (
        append_review_event,
        load_review_events,
        load_state,
        save_state,
    )
    from alarm_app.db.engine import create_engine, get_session_factory, init_db
except ImportError:
    from bdt.history import save_test_record
    from bdt.parser import parse_bdt_file
    from bdt.validator import BDTTolerances, validate_bdt
    from core.backup_time import compute_backup_times
    from core.classify import classify_by_alarm_id, compute_site_down_flag
    from data.loaders import parse_alarm_file
    from data.state import (
        append_review_event,
        load_review_events,
        load_state,
        save_state,
    )
    from db.engine import create_engine, get_session_factory, init_db


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    import alarm_app.data.state as state_mod
    import alarm_app.db.engine as engine_mod

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(engine_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(engine_mod, "DB_PATH", db_path)
    engine_mod._app_engine = None
    engine_mod._app_session_factory = None
    state_mod._engine = None
    state_mod._SessionFactory = None

    engine = create_engine()
    init_db(engine)
    engine_mod._app_engine = engine
    engine_mod._app_session_factory = get_session_factory(engine)

    session = engine_mod._app_session_factory()
    yield session
    session.close()


class TestAlarmPipelineE2E:

    def test_load_and_classify_alarms(self, isolated_db, tmp_path):
        csv_path = tmp_path / "alarm_test.csv"
        csv_content = (
            "Site Name,Alarm ID,Alarm Name,Last Occurred On,Cleared On,"
            "Duration(hh:mm:ss),Clearance Status,Network Type,Vendor,Alarm Source\n"
            "SITE01,22001,Mains Failure,2026-01-15 08:00:00,2026-01-15 10:00:00,"
            "02:00:00,Cleared,2G,Huawei,Power_Alarm_File.csv\n"
            "SITE01,35001,Site Down,2026-01-15 09:30:00,,"
            "00:00:00,Not Cleared,2G,Huawei,Down_Alarm_File.csv\n"
        )
        csv_path.write_text(csv_content)

        info = {
            "path": str(csv_path),
            "ext": ".csv",
            "filename": "alarm_test.csv",
        }
        df = parse_alarm_file(info)
        assert df is not None, "parse_alarm_file should return a DataFrame"
        assert not df.empty, "DataFrame should not be empty"
        assert len(df) == 2, f"Expected 2 rows, got {len(df)}"

        alarm_ids = {"power": ["22001"], "down": ["35001"], "door": []}
        df = classify_by_alarm_id(df, alarm_ids)
        df = compute_site_down_flag(df)

        power_row = df[df["alarm_id"].astype(str).str.replace(r"\.0$", "", regex=True) == "22001"]
        down_row = df[df["alarm_id"].astype(str).str.replace(r"\.0$", "", regex=True) == "35001"]

        assert not power_row.empty, "Power alarm row should exist"
        assert not down_row.empty, "Down alarm row should exist"

        power_categories = power_row["alarm_category"].unique()
        assert "Power" in power_categories, f"Power alarm should have 'Power' category, got: {power_categories}"

        down_categories = down_row["alarm_category"].unique()
        assert "Down" in down_categories, f"Down alarm should have 'Down' category, got: {down_categories}"

        power_flags = power_row["site_down_flag"].unique()
        assert "Yes" in power_flags, (
            "Power alarm with matching Down inside its window should have site_down_flag='Yes', "
            f"got: {power_flags}"
        )

        down_flags = down_row["site_down_flag"].unique()
        assert "Yes" in down_flags, f"Down alarm should have site_down_flag='Yes', got: {down_flags}"

    def test_compute_backup_times(self, isolated_db, tmp_path):
        data = {
            "site_id": ["SITE01", "SITE01"],
            "occurred_on": ["2026-01-15 08:00:00", "2026-01-15 09:30:00"],
            "cleared_on": ["2026-01-15 10:00:00", pd.NaT],
            "alarm_category": ["Power", "Down"],
            "network_type": ["2G", "2G"],
            "vendor": ["Huawei", "Huawei"],
        }
        df = pd.DataFrame(data)
        df["occurred_on"] = pd.to_datetime(df["occurred_on"])
        df["cleared_on"] = pd.to_datetime(df["cleared_on"])

        result_df, error_msg = compute_backup_times(df)
        assert error_msg == "", f"Unexpected error: {error_msg}"
        assert not result_df.empty, "Backup times result should not be empty"
        assert "backup_time" in result_df.columns, "Result should contain backup_time column"

        matched = result_df[
            result_df["end_event_type"].str.contains("Down", na=False)
        ]
        assert len(matched) > 0, "Should have at least one Power->Down matched pair"

    def test_persist_and_load_from_db(self, isolated_db):
        filepath = FIXTURES_DIR / "bdt_layout_a_16photo.xlsx"
        assert filepath.is_file(), f"Fixture missing: {filepath}"

        bdt_data = parse_bdt_file(str(filepath), skip_photos=True)
        result = validate_bdt(
            bdt_data,
            alarm_df=None,
            tolerances=BDTTolerances.defaults(),
            health_pct=80,
        )
        save_test_record(bdt_data, result.overall)

        test_state = {"tab": "bdt_validation", "selected_site": "SITE01"}
        save_state(test_state)
        loaded_state = load_state()
        assert loaded_state is not None, "load_state should return a dict"
        assert loaded_state.get("tab") == "bdt_validation"
        assert loaded_state.get("selected_site") == "SITE01"

        append_review_event(
            username="tester",
            filename="bdt_layout_a_16photo.xlsx",
            site_code=bdt_data.site_code,
            test_date=(bdt_data.test_date.strftime("%Y-%m-%d")
                       if bdt_data.test_date else "2026-01-15"),
            verdict=result.overall,
        )
        events = load_review_events()
        assert len(events) > 0, "Should have at least one review event"
        event = events[0]
        assert event["username"] == "tester"
        assert event["verdict"] == result.overall
        assert event["site_code"] == bdt_data.site_code
