"""Tests for uncovered Temp alarms outside Power coverage windows."""

import pandas as pd
from openpyxl import load_workbook

from alarm_app.core.temp_alarm import (
    build_temp_alarm_summary,
    compute_temp_alarm_matches,
    compute_temp_alarm_matches_for_query,
    export_temp_alarm_workbook,
    filter_temp_matches_to_query,
    filter_temp_matches_to_selected_temps,
)
from alarm_app.data.alarm_store import AlarmQuery
from alarm_app.ui.viewer import AlarmViewer


def _make_df(rows):
    defaults = {
        "site_id": "SITE_A",
        "alarm_source": "U_G_SITE_A_TEST",
        "alarm_name": "MAIN POWER CUT OFF",
        "occurred_on": None,
        "cleared_on": None,
        "duration": "",
        "alarm_category": "Power",
        "network_type": "4G",
        "vendor": "Huawei",
        "clearance_status": "Cleared",
    }
    records = []
    for row in rows:
        rec = {**defaults, **row}
        for col in ("occurred_on", "cleared_on"):
            if isinstance(rec[col], str):
                rec[col] = pd.Timestamp(rec[col])
        records.append(rec)
    return pd.DataFrame(records)


def test_excludes_temp_inside_power_window():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 11:00:00",
            "cleared_on": "2026-02-01 11:30:00",
            "duration": "00:30:00",
        },
    ])

    result, err = compute_temp_alarm_matches(df, margin_minutes=60)

    assert result.empty
    assert "No uncovered Temp alarms" in err


def test_excludes_temp_after_power_clearance_within_y_margin():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 12:45:00",
            "cleared_on": "2026-02-01 13:00:00",
            "duration": "00:15:00",
        },
    ])

    result, err = compute_temp_alarm_matches(df, margin_minutes=60)

    assert result.empty
    assert "No uncovered Temp alarms" in err


def test_excludes_multiple_temp_rows_inside_same_power_window():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 11:30:00",
            "cleared_on": "2026-02-01 11:40:00",
            "duration": "00:10:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 10:30:00",
            "cleared_on": "2026-02-01 10:40:00",
            "duration": "00:10:00",
        },
    ])

    result, err = compute_temp_alarm_matches(df, margin_minutes=60)

    assert result.empty
    assert "No uncovered Temp alarms" in err


def test_includes_temp_after_y_margin():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 13:01:00",
            "cleared_on": "2026-02-01 13:30:00",
            "duration": "00:29:00",
        },
    ])

    result, err = compute_temp_alarm_matches(df, margin_minutes=60)

    assert err == ""
    assert len(result) == 1
    row = result.iloc[0]
    assert row["match_window"] == "No Power coverage"
    assert row["temp_delay_after_power"] == ""
    assert row["temp_delay_after_power_clearance"] == ""


def test_summary_groups_counts_and_duration_by_week():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_source": "SRAN_LWG_TEST_SITE_A",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 13:15:00",
            "cleared_on": "2026-02-01 13:45:00",
            "duration": "00:30:00",
        },
        {
            "site_id": "SITE_B",
            "alarm_category": "Temp",
            "alarm_source": "SRAN_LWG_TEST_SITE_B",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 14:15:00",
            "cleared_on": "2026-02-01 15:00:00",
            "duration": "00:45:00",
        },
        {
            "site_id": "SITE_C",
            "alarm_category": "Temp",
            "alarm_source": "SRAN_LWG_TEST_SITE_C",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-08 14:15:00",
            "cleared_on": "2026-02-08 15:15:00",
            "duration": "01:00:00",
        },
    ])
    matches, err = compute_temp_alarm_matches(df, margin_minutes=60)
    assert err == ""

    summary = build_temp_alarm_summary(matches, week_label="W05-26")

    assert list(summary.columns) == [
        "##", "Site Name", "Site Code", "Area", "Contractor",
        "No. Of HT Alarms", "HT Duration", "Batteries Types",
        "Batteries Status", "Week No.", "W05-26", "W04-26", "W03-26",
        "W02-26", "W01-26", "W52-25", "W51-25", "W50-25",
    ]
    assert len(summary) == 2
    week_05 = summary[summary["Week No."] == "W05-26"].iloc[0]
    week_06 = summary[summary["Week No."] == "W06-26"].iloc[0]
    assert week_05["Site Name"] == ""
    assert week_05["Site Code"] == ""
    assert week_05["No. Of HT Alarms"] == 2
    assert week_05["HT Duration"] == "01:15"
    assert week_05["W05-26"] == "W05-26"
    assert week_06["No. Of HT Alarms"] == 1
    assert week_06["HT Duration"] == "01:00"


def test_export_workbook_contains_w27_summary_and_details(tmp_path):
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_source": "SRAN_LWG_TEST_SITE_A",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 13:15:00",
            "cleared_on": "2026-02-01 13:45:00",
            "duration": "00:30:00",
        },
    ])
    matches, err = compute_temp_alarm_matches(df, margin_minutes=60)
    assert err == ""
    out = tmp_path / "temp_alarm_export.xlsx"

    export_temp_alarm_workbook(matches, out, week_label="W05-26")

    wb = load_workbook(out, data_only=False)
    assert wb.sheetnames == ["W05-26", "Uncovered Temp Details"]
    summary = wb["W05-26"]
    assert [summary.cell(row=1, column=col).value for col in range(1, 19)] == [
        "##", "Site Name", "Site Code", "Area", "Contractor",
        "No. Of HT Alarms", "HT Duration", "Batteries Types",
        "Batteries Status", "Week No.", "W05-26", "W04-26", "W03-26",
        "W02-26", "W01-26", "W52-25", "W51-25", "W50-25",
    ]
    assert summary["G2"].value == "00:30"
    assert summary["A1"].fill.fgColor.rgb == "004F81BD"
    assert summary["A1"].border.left.color.rgb == "FF000000"
    assert wb["Uncovered Temp Details"].max_row == 2
    details = wb["Uncovered Temp Details"]
    assert [details.cell(row=1, column=col).value for col in range(1, 17)] == [
        "Site ID", "Network", "Vendor", "Power Alarm", "Power Cleared",
        "X Duration", "Y Margin", "Temp Alarm", "Temp Cleared",
        "Temp After Power", "Temp After Clearance", "Temp Clear Duration",
        "Temp Alarm Name", "Temp Alarm Source", "Status", "Coverage Status",
    ]


def test_filter_matches_to_original_date_scope_uses_temp_time():
    matches = pd.DataFrame([
        {"site_id": "A", "temp_time": "2026-02-01 23:30:00"},
        {"site_id": "B", "temp_time": "2026-02-02 00:30:00"},
    ])
    query = AlarmQuery(date_from=pd.Timestamp("2026-02-02"), date_to=pd.Timestamp("2026-02-02"))

    filtered = filter_temp_matches_to_query(matches, query)

    assert filtered["site_id"].tolist() == ["B"]


def test_filter_matches_to_selected_temp_rows_uses_site_and_temp_time():
    matches = pd.DataFrame([
        {"site_id": "A", "temp_time": "2026-02-01 11:00:00", "temp_cleared": "2026-02-01 11:10:00", "temp_alarm_name": "Shelter High Temperature", "temp_alarm_source": "SRC-1"},
        {"site_id": "A", "temp_time": "2026-02-01 11:00:00", "temp_cleared": "2026-02-01 11:20:00", "temp_alarm_name": "Shelter High Temperature", "temp_alarm_source": "SRC-2"},
    ])
    selected_temp = pd.DataFrame([
        {"site_id": "A", "occurred_on": pd.Timestamp("2026-02-01 11:00:00"), "cleared_on": pd.Timestamp("2026-02-01 11:20:00"), "alarm_name": "Shelter High Temperature", "alarm_source": "SRC-2"},
    ])

    filtered = filter_temp_matches_to_selected_temps(matches, selected_temp)

    assert filtered["temp_alarm_source"].tolist() == ["SRC-2"]


def test_filter_matches_to_selected_temp_rows_handles_blank_cleared_time():
    matches = pd.DataFrame([
        {
            "site_id": "A",
            "temp_time": "2026-02-01 11:00:00",
            "temp_cleared": "",
            "temp_alarm_name": "Shelter High Temperature",
            "temp_alarm_source": "SRC-1",
        }
    ])
    selected_temp = pd.DataFrame([
        {
            "site_id": "A",
            "occurred_on": pd.Timestamp("2026-02-01 11:00:00"),
            "cleared_on": pd.NaT,
            "alarm_name": "Shelter High Temperature",
            "alarm_source": "SRC-1",
        }
    ])

    filtered = filter_temp_matches_to_selected_temps(matches, selected_temp)

    assert len(filtered) == 1


def test_query_path_without_result_filter_query_still_loads_query(monkeypatch):
    source_rows = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-01 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-01 13:15:00",
            "cleared_on": "2026-02-01 13:45:00",
            "duration": "00:30:00",
        },
    ])
    monkeypatch.setattr("alarm_app.core.temp_alarm.query_alarms", lambda query: source_rows)

    result, err, source_df = compute_temp_alarm_matches_for_query(AlarmQuery(), margin_minutes=60)

    assert err == ""
    assert len(result) == 1
    assert len(source_df) == 2


def test_date_scoped_temp_excludes_power_more_than_one_day_earlier():
    df = _make_df([
        {
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-04 12:00:00",
        },
        {
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-04 10:00:00",
            "cleared_on": "2026-02-04 11:00:00",
            "duration": "01:00:00",
        },
    ])
    query = AlarmQuery(date_from=pd.Timestamp("2026-02-04"), date_to=pd.Timestamp("2026-02-04"))

    matches, err = compute_temp_alarm_matches(df, margin_minutes=60)
    filtered = filter_temp_matches_to_query(matches, query)

    assert filtered.empty
    assert "No uncovered Temp alarms" in err


def test_temp_source_query_removes_date_scope_before_coverage_check():
    query = AlarmQuery(date_from=pd.Timestamp("2026-02-04"), date_to=pd.Timestamp("2026-02-04"))

    source_query = AlarmViewer._build_temp_alarm_source_query(query)

    assert source_query.date_from is None
    assert source_query.date_to is None
    assert source_query.manual_days is None


def test_query_path_scopes_broad_source_to_selected_temp_sites(monkeypatch):
    selected_temp = _make_df([
        {
            "site_id": "SITE_A",
            "alarm_category": "Temp",
            "alarm_name": "Shelter High Temperature",
            "occurred_on": "2026-02-04 13:30:00",
            "cleared_on": "2026-02-04 14:30:00",
            "duration": "01:00:00",
        }
    ])
    power_rows = _make_df([
        {
            "site_id": "SITE_A",
            "alarm_category": "Power",
            "occurred_on": "2026-02-01 10:00:00",
            "cleared_on": "2026-02-04 12:00:00",
        },
    ])
    calls = []

    def fake_query_alarms(query):
        calls.append(query)
        if len(calls) == 1:
            return selected_temp
        return power_rows

    monkeypatch.setattr("alarm_app.core.temp_alarm.query_alarms", fake_query_alarms)
    selected_query = AlarmQuery(date_from=pd.Timestamp("2026-02-04"), date_to=pd.Timestamp("2026-02-04"))

    result, err, source_df = compute_temp_alarm_matches_for_query(
        selected_query,
        margin_minutes=60,
        result_filter_query=selected_query,
    )

    assert err == ""
    assert len(result) == 1
    assert len(source_df) == 2
    assert calls[0].category == "Temp"
    assert calls[0].date_from == pd.Timestamp("2026-02-04")
    assert calls[1].category == "Power"
    assert calls[1].site_text == ""
    assert calls[1].vendor == "All"
    assert calls[1].network_type == "All"
    assert calls[1].min_duration_secs is None
    assert calls[1].col_filters == {}
    assert calls[1].date_from is None
    assert calls[1].date_to == pd.Timestamp("2026-02-04")
    assert calls[1].manual_days is None
    assert set(calls[1].site_scope_keys) == {"SITE_A"}
