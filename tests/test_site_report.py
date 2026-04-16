import pandas as pd
import pytest
from types import SimpleNamespace

from alarm_app.data.site_report import (
    build_pm_accept_report,
    build_site_alarm_report,
    filter_site_sheet_to_matching_sites,
    infer_date_column,
    infer_site_id_column,
    normalize_site_key,
    read_pm_accept_sheet,
    read_site_sheet,
)


def test_normalize_site_key_strips_non_alnum():
    assert normalize_site_key(" kona-3420 ") == "KONA3420"


def test_infer_site_id_column_prefers_header_and_overlap():
    site_df = pd.DataFrame(
        {
            "VIP": ["Yes", "No"],
            "Short Code": ["KONA-3420", "BANI-0813"],
            "Area": ["North", "South"],
        }
    )
    alarm_df = pd.DataFrame({"site_id": ["KONA3420", "BANI0813"]})
    assert infer_site_id_column(site_df, alarm_df) == "Short Code"


def test_build_site_alarm_report_prefers_matched_power_down_incident():
    site_df = pd.DataFrame(
        {
            "Site Code": ["KONA-3420", "BANI-0813"],
            "VIP": ["Yes", "No"],
        }
    )
    alarm_df = pd.DataFrame(
        [
            {
                "site_id": "KONA3420",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 10:00:00",
                "cleared_on": "2026-04-01 14:00:00",
            },
            {
                "site_id": "KONA3420",
                "alarm_category": "Down",
                "occurred_on": "2026-04-01 11:30:00",
                "cleared_on": "2026-04-01 13:00:00",
            },
            {
                "site_id": "BANI0813",
                "alarm_category": "Power",
                "occurred_on": "2026-04-02 08:00:00",
                "cleared_on": "2026-04-02 09:15:00",
            },
        ]
    )

    report = build_site_alarm_report(site_df, "Site Code", alarm_df)

    kona = report.loc[report["Site Code"] == "KONA-3420"].iloc[0]
    assert kona["Power Alarm At"] == "2026-04-01 10:00:00"
    assert kona["Down Alarm At"] == "2026-04-01 11:30:00"
    assert kona["Backup Time"] == "01:30:00"
    assert kona["Power Cleared At"] == "2026-04-01 14:00:00"
    assert kona["Alarm Match Status"] == "Power and Down found"

    bani = report.loc[report["Site Code"] == "BANI-0813"].iloc[0]
    assert bani["Power Alarm At"] == "2026-04-02 08:00:00"
    assert bani["Down Alarm At"] == ""
    assert bani["Backup Time"] == "01:15:00"
    assert bani["Power Cleared At"] == "2026-04-02 09:15:00"
    assert bani["Alarm Match Status"] == "Power found only"
    assert "Power Cleared At" in report.columns
    assert "Backup Time Basis" not in report.columns


def test_build_site_alarm_report_marks_missing_site_id():
    site_df = pd.DataFrame({"Site Code": ["", None]})
    alarm_df = pd.DataFrame(
        [
            {
                "site_id": "KONA3420",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 10:00:00",
                "cleared_on": "2026-04-01 12:00:00",
            }
        ]
    )
    report = build_site_alarm_report(site_df, "Site Code", alarm_df)
    assert report["Alarm Match Status"].tolist() == ["Missing site ID", "Missing site ID"]


def test_filter_site_sheet_to_matching_sites_keeps_only_matching_rows():
    site_df = pd.DataFrame(
        {
            "Site Code": ["KONA-3420", "BANI-0813", "MISS-0001"],
            "VIP": ["Yes", "No", "No"],
        }
    )
    alarm_df = pd.DataFrame(
        [
            {
                "site_id": "KONA3420",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 10:00:00",
                "cleared_on": "2026-04-01 12:00:00",
            },
            {
                "site_id": "BANI0813",
                "alarm_category": "Down",
                "occurred_on": "2026-04-01 11:00:00",
                "cleared_on": "2026-04-01 12:30:00",
            },
        ]
    )

    filtered = filter_site_sheet_to_matching_sites(site_df, "Site Code", alarm_df)

    assert filtered["Site Code"].tolist() == ["KONA-3420", "BANI-0813"]


def test_build_site_alarm_report_allows_empty_filtered_alarm_set():
    site_df = pd.DataFrame({"Site Code": ["KONA-3420", "BANI-0813"]})
    alarm_df = pd.DataFrame(columns=["site_id", "alarm_category", "occurred_on", "cleared_on"])

    report = build_site_alarm_report(site_df, "Site Code", alarm_df)

    assert report["Alarm Match Status"].tolist() == ["No alarms found", "No alarms found"]
    assert report["Power Alarm At"].tolist() == ["", ""]


def test_build_site_alarm_report_reuses_existing_backup_time_column():
    site_df = pd.DataFrame(
        {
            "Site ID": ["KONA-3420"],
            "Backup time": ["old value"],
        }
    )
    alarm_df = pd.DataFrame(
        [
            {
                "site_id": "KONA3420",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 10:00:00",
                "cleared_on": "2026-04-01 14:00:00",
            },
            {
                "site_id": "KONA3420",
                "alarm_category": "Down",
                "occurred_on": "2026-04-01 11:30:00",
                "cleared_on": "2026-04-01 13:00:00",
            },
        ]
    )

    report = build_site_alarm_report(site_df, "Site ID", alarm_df)

    assert "Backup time" in report.columns
    assert "Backup Time" not in report.columns
    assert report.loc[0, "Backup time"] == "01:30:00"


def test_read_site_sheet_uses_only_all_down_sheet(tmp_path):
    path = tmp_path / "site_upload.xlsx"
    nodal_df = pd.DataFrame({"Site ID": ["NODE-9999"], "Backup time": ["legacy"]})
    all_down_df = pd.DataFrame(
        {
            "Alarm Name": ["Power alarm"],
            "Alarm Source": ["SRC"],
            "Site Code": ["KONA-3420"],
            "First Occurred On": ["2026-04-01 10:00:00"],
            "Site ID": ["KONA3420"],
            "VIP": ["Yes"],
            "Cleared On": ["2026-04-01 14:00:00"],
            "Area": ["North"],
            "Duration": ["04:00:00"],
        }
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        nodal_df.to_excel(writer, sheet_name="Nodal Sites", index=False)
        all_down_df.to_excel(writer, sheet_name="All down", index=False)

    df, sheet_name, site_col = read_site_sheet(str(path))

    assert sheet_name == "All down"
    assert site_col == "Site ID"
    assert df["Site ID"].tolist() == ["KONA3420"]


def test_read_site_sheet_requires_all_down_sheet(tmp_path):
    path = tmp_path / "site_upload.xlsx"
    vip_df = pd.DataFrame({"Site ID": ["KONA3420"]})
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        vip_df.to_excel(writer, sheet_name="VIP Sites", index=False)

    with pytest.raises(ValueError, match="All down"):
        read_site_sheet(str(path))


def test_infer_date_column_detects_actual_done_date():
    df = pd.DataFrame(
        {
            "Site Code": ["A001", "B002"],
            "Actual Done Date": ["01-Jan-25", "02-Jan-25"],
            "PM Status": ["Accepted", "Accepted"],
        }
    )
    assert infer_date_column(df) == "Actual Done Date"


def test_read_pm_accept_sheet_finds_site_and_date_columns(tmp_path):
    path = tmp_path / "accepted_pm.xlsx"
    df = pd.DataFrame(
        {
            "Virtual Code": ["0117CA45658"],
            "Site Code": ["0117CA"],
            "Actual Done Date": ["01-Jan-25"],
            "PM Status": ["Accepted"],
        }
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Accepted PM List", index=False)

    out_df, sheet_name, site_col, date_col, status_col = read_pm_accept_sheet(str(path))
    assert sheet_name == "Accepted PM List"
    assert site_col == "Site Code"
    assert date_col == "Actual Done Date"
    assert status_col == "PM Status"
    assert len(out_df) == 1


def test_build_pm_accept_report_maps_bdt_and_alarm_fields():
    pm_df = pd.DataFrame(
        {
            "Site Code": ["0117CA"],
            "Actual Done Date": ["2025-01-01"],
            "PM Status": ["Accepted"],
        }
    )
    bdt_data = SimpleNamespace(
        battery_ah=100.0,
        battery_voltage=48.0,
        num_strings=1,
        start_voltage=48.0,
        start_ampere=40.0,
        battery_brand="Lithium",
        discharge_minutes=130.0,
        test_date=pd.Timestamp("2025-01-01"),
    )
    bdt_results = [
        SimpleNamespace(
            filename="BDT_0117CA.xlsx",
            site_code="0117CA",
            test_date="2025-01-01",
            overall="Accepted",
            bdt_data=bdt_data,
        )
    ]
    alarm_df = pd.DataFrame(
        [
            {
                "site_id": "0117CA",
                "alarm_category": "Power",
                "occurred_on": "2025-01-01 10:00:00",
                "cleared_on": "2025-01-01 14:00:00",
            },
            {
                "site_id": "0117CA",
                "alarm_category": "Down",
                "occurred_on": "2025-01-01 11:30:00",
                "cleared_on": "2025-01-01 12:30:00",
            },
        ]
    )

    report = build_pm_accept_report(
        pm_df=pm_df,
        site_id_column="Site Code",
        date_column="Actual Done Date",
        bdt_results=bdt_results,
        alarm_df=alarm_df,
        health_pct=0.8,
        status_column="PM Status",
    )

    assert len(report) == 1
    row = report.iloc[0]
    assert row["Matched BDT File Name"] == "BDT_0117CA.xlsx"
    assert row["Matched BDT Validation Verdict"] == "Accepted"
    assert row["Measured Backup Time From BDT Test Duration (mins)"] == "130.0"
    assert row["Power Alarm Start Time"] == "2025-01-01 10:00:00"
    assert row["Down Alarm Start Time"] == "2025-01-01 11:30:00"
    assert row["Backup Time Calculated From Alarm Pair (HH:MM:SS)"] == "01:30:00"
