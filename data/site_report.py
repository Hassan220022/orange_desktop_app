"""Site-sheet report helpers for alarm export workflows."""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Any

import pandas as pd


_SITE_ID_HEADER_ALIASES: dict[str, int] = {
    "siteid": 110,
    "sitecode": 100,
    "shortcode": 95,
    "site": 55,
    "code": 50,
    "id": 25,
    "sitename": 20,
}
_REQUIRED_WORKBOOK_SHEET_KEY = "alldown"
_SITE_REPORT_COLUMNS = [
    "Power Alarm At",
    "Down Alarm At",
    "Backup Time",
    "Power Cleared At",
    "Alarm Match Status",
]
_DATE_HEADER_ALIASES: dict[str, int] = {
    "actualdonedate": 120,
    "testdate": 110,
    "date": 90,
    "pmdate": 85,
    "donedate": 80,
    "actualdate": 80,
    "eventdate": 70,
}
_STATUS_HEADER_ALIASES: dict[str, int] = {
    "pmstatus": 120,
    "status": 100,
    "result": 80,
    "acceptance": 70,
}
_PM_ACCEPT_REPORT_COLUMNS = [
    "Matched BDT File Name",
    "Matched BDT Test Date",
    "Matched BDT Validation Verdict",
    "Theoretical Backup Time From BDT Inputs (mins)",
    "Measured Backup Time From BDT Test Duration (mins)",
    "Power Alarm Start Time",
    "Down Alarm Start Time",
    "Backup Time Calculated From Alarm Pair (HH:MM:SS)",
    "Power Alarm Clear Time",
    "Alarm Correlation Status",
]


def normalize_site_key(value: Any) -> str:
    """Normalize a site identifier to uppercase alphanumeric text."""
    if value is None:
        return ""
    text = str(value).strip().upper()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def _header_key(value: Any) -> str:
    return normalize_site_key(value).lower()


def _sheet_key(value: Any) -> str:
    return normalize_site_key(value).lower()


def _format_dt(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _format_td(value: pd.Timedelta | None) -> str:
    if value is None or pd.isna(value):
        return ""
    total = int(value.total_seconds())
    if total < 0:
        return ""
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _resolve_report_column_names(columns: pd.Index) -> dict[str, str]:
    """Map canonical report columns to existing sheet columns when possible."""
    resolved: dict[str, str] = {}
    existing_by_key: dict[str, str] = {}
    for col in columns:
        key = _header_key(col)
        if key and key not in existing_by_key:
            existing_by_key[key] = str(col)

    for canonical in _SITE_REPORT_COLUMNS:
        key = _header_key(canonical)
        resolved[canonical] = existing_by_key.get(key, canonical)
    return resolved


def _resolve_columns(columns: pd.Index, canonical_names: list[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    existing_by_key: dict[str, str] = {}
    for col in columns:
        key = _header_key(col)
        if key and key not in existing_by_key:
            existing_by_key[key] = str(col)
    for canonical in canonical_names:
        key = _header_key(canonical)
        resolved[canonical] = existing_by_key.get(key, canonical)
    return resolved


def infer_site_id_column(df: pd.DataFrame, alarm_df: pd.DataFrame | None = None) -> str | None:
    """Infer the site-ID column from arbitrary site-sheet layouts."""
    if df is None or df.empty:
        return None

    alarm_keys: set[str] = set()
    if alarm_df is not None and not alarm_df.empty and "site_id" in alarm_df.columns:
        alarm_keys = {
            normalize_site_key(v)
            for v in alarm_df["site_id"].dropna().tolist()
            if normalize_site_key(v)
        }

    best_col = None
    best_score = float("-inf")

    for col in df.columns:
        series = df[col]
        values = [normalize_site_key(v) for v in series.dropna().tolist()]
        values = [v for v in values if v]
        nonempty = len(values)
        unique = len(set(values))
        header_score = _SITE_ID_HEADER_ALIASES.get(_header_key(col), 0)
        overlap_ratio = 0.0
        if alarm_keys and values:
            overlap_ratio = len(set(values) & alarm_keys) / len(set(values))
        density_score = min(nonempty, len(df)) / max(len(df), 1)
        uniqueness_score = unique / max(nonempty, 1)
        score = (
            header_score
            + overlap_ratio * 100.0
            + density_score * 10.0
            + uniqueness_score * 10.0
        )
        if score > best_score:
            best_score = score
            best_col = str(col)

    if best_score < 20:
        return None
    return best_col


def infer_date_column(df: pd.DataFrame) -> str | None:
    """Infer a date-like column from arbitrary sheet layouts."""
    if df is None or df.empty:
        return None

    best_col = None
    best_score = float("-inf")
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        if non_null.empty:
            continue
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        parse_ratio = float(parsed.notna().mean()) if len(non_null) else 0.0
        header_score = _DATE_HEADER_ALIASES.get(_header_key(col), 0)
        score = header_score + (parse_ratio * 100.0)
        if score > best_score:
            best_score = score
            best_col = str(col)

    if best_score < 35:
        return None
    return best_col


def infer_status_column(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    best_col = None
    best_score = float("-inf")
    for col in df.columns:
        key = _header_key(col)
        header_score = _STATUS_HEADER_ALIASES.get(key, 0)
        if header_score <= 0:
            continue
        series = df[col].astype(str).str.strip().str.lower()
        accepted_ratio = float(series.str.contains("accept", na=False).mean()) if len(series) else 0.0
        score = header_score + accepted_ratio * 20.0
        if score > best_score:
            best_score = score
            best_col = str(col)
    return best_col


def read_site_sheet(path: str, alarm_df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, str, str]:
    """Read a site sheet and infer which sheet/column contains site IDs."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path, dtype=object)
        site_col = infer_site_id_column(df, alarm_df)
        if not site_col:
            raise ValueError("Could not identify a site ID column in the uploaded file.")
        return df, "Sheet1", site_col

    workbook = None
    for engine in ("calamine", "openpyxl"):
        try:
            workbook = pd.ExcelFile(path, engine=engine)
            break
        except Exception:
            continue
    if workbook is None:
        raise ValueError("Could not open the uploaded workbook.")

    try:
        target_sheet = next(
            (sheet_name for sheet_name in workbook.sheet_names
             if _sheet_key(sheet_name) == _REQUIRED_WORKBOOK_SHEET_KEY),
            None,
        )
        if target_sheet is None:
            raise ValueError("Uploaded workbook must contain an 'All down' sheet.")

        df = pd.read_excel(workbook, sheet_name=target_sheet, dtype=object)
    finally:
        try:
            workbook.close()
        except Exception:
            pass

    if df is None or df.empty:
        raise ValueError("The 'All down' sheet is empty.")

    site_col = infer_site_id_column(df, alarm_df)
    if not site_col:
        raise ValueError("Could not identify a site ID column in the 'All down' sheet.")
    return df, target_sheet, site_col


def read_pm_accept_sheet(
    path: str,
    alarm_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, str, str, str, str | None]:
    """Read a PM accepted list and infer site/date/status columns flexibly."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path, dtype=object)
        site_col = infer_site_id_column(df, alarm_df)
        date_col = infer_date_column(df)
        status_col = infer_status_column(df)
        if not site_col:
            raise ValueError("Could not identify a site ID/Site Code column.")
        if not date_col:
            raise ValueError("Could not identify a test/date column.")
        return df, "Sheet1", site_col, date_col, status_col

    workbook = None
    for engine in ("calamine", "openpyxl"):
        try:
            workbook = pd.ExcelFile(path, engine=engine)
            break
        except Exception:
            continue
    if workbook is None:
        raise ValueError("Could not open the uploaded workbook.")

    best: tuple[float, pd.DataFrame, str, str, str, str | None] | None = None
    try:
        for sheet_name in workbook.sheet_names:
            df = pd.read_excel(workbook, sheet_name=sheet_name, dtype=object)
            if df is None or df.empty:
                continue
            site_col = infer_site_id_column(df, alarm_df)
            date_col = infer_date_column(df)
            status_col = infer_status_column(df)
            if not site_col or not date_col:
                continue

            status_bonus = 0.0
            if status_col:
                series = df[status_col].astype(str).str.strip().str.lower()
                status_bonus = float(series.str.contains("accept", na=False).mean()) * 20.0
            score = 100.0 + status_bonus + (_STATUS_HEADER_ALIASES.get(_header_key(status_col), 0) if status_col else 0)
            cand = (score, df, sheet_name, site_col, date_col, status_col)
            if best is None or cand[0] > best[0]:
                best = cand
    finally:
        try:
            workbook.close()
        except Exception:
            pass

    if best is None:
        raise ValueError("Could not find a sheet with both Site and Date columns.")
    _, df, sheet_name, site_col, date_col, status_col = best
    return df, sheet_name, site_col, date_col, status_col


def _pick_site_incident(site_df: pd.DataFrame) -> dict[str, str]:
    if site_df.empty:
        return {
            "Power Alarm At": "",
            "Down Alarm At": "",
            "Backup Time": "",
            "Power Cleared At": "",
            "Alarm Match Status": "No alarms found",
        }

    power_df = site_df[site_df["alarm_category"] == "Power"].copy()
    down_df = site_df[site_df["alarm_category"] == "Down"].copy()

    power_df = power_df.dropna(subset=["occurred_on"]).sort_values("occurred_on", ascending=False)
    down_df = down_df.dropna(subset=["occurred_on"]).sort_values("occurred_on", ascending=False)

    best_match: dict[str, str] | None = None
    best_power_only: dict[str, str] | None = None

    for _, power in power_df.iterrows():
        power_start = pd.to_datetime(power.get("occurred_on"), errors="coerce")
        power_clear = pd.to_datetime(power.get("cleared_on"), errors="coerce")
        if pd.isna(power_start):
            continue

        if pd.notna(power_clear):
            matches = down_df[
                (down_df["occurred_on"] >= power_start)
                & (down_df["occurred_on"] <= power_clear)
            ]
        else:
            matches = pd.DataFrame(columns=down_df.columns)

        if not matches.empty:
            down = matches.sort_values("occurred_on", ascending=False).iloc[0]
            down_time = pd.to_datetime(down.get("occurred_on"), errors="coerce")
            return {
                "Power Alarm At": _format_dt(power_start),
                "Down Alarm At": _format_dt(down_time),
                "Backup Time": _format_td(down_time - power_start),
                "Power Cleared At": _format_dt(power_clear),
                "Alarm Match Status": "Power and Down found",
            }

        if best_power_only is None:
            backup_td = None
            status = "Power found only"
            if pd.notna(power_clear):
                backup_td = power_clear - power_start
            else:
                status = "Power active only"
            best_power_only = {
                "Power Alarm At": _format_dt(power_start),
                "Down Alarm At": "",
                "Backup Time": _format_td(backup_td),
                "Power Cleared At": _format_dt(power_clear),
                "Alarm Match Status": status,
            }

    if best_match:
        return best_match
    if best_power_only:
        return best_power_only
    return {
        "Power Alarm At": "",
        "Down Alarm At": _format_dt(down_df.iloc[0]["occurred_on"]) if not down_df.empty else "",
        "Backup Time": "",
        "Power Cleared At": "",
        "Alarm Match Status": "Down found only" if not down_df.empty else "No alarms found",
    }


def _to_date_obj(value: Any) -> date | None:
    ts = pd.to_datetime(value, errors="coerce", format="mixed")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).date()


def _theoretical_backup_minutes_like_bdt(bdt, health_pct: float) -> float | None:
    if bdt is None:
        return None
    ah = getattr(bdt, "battery_ah", None)
    voltage = getattr(bdt, "battery_voltage", None)
    strings = getattr(bdt, "num_strings", None)
    load_v = getattr(bdt, "start_voltage", None)
    load_a = getattr(bdt, "start_ampere", None)
    if ah is None or voltage is None or strings is None:
        return None
    if load_v is None or load_a is None or load_v <= 0 or load_a <= 0:
        return None
    brand = str(getattr(bdt, "battery_brand", "") or "").lower()
    efficiency = 1.0 if "lith" in brand else health_pct
    load_w = float(load_v) * float(load_a)
    capacity_wh = float(ah) * float(voltage) * float(strings) * float(efficiency)
    return (capacity_wh / load_w) * 60.0


def _pick_site_incident_for_date(site_df: pd.DataFrame, target_date: date | None) -> dict[str, str]:
    if site_df.empty:
        return {
            "Power Alarm At": "",
            "Down Alarm At": "",
            "Backup Time": "",
            "Power Cleared At": "",
            "Alarm Match Status": "No alarms found",
        }
    if target_date is None:
        return _pick_site_incident(site_df)

    same_day = site_df[site_df["occurred_on"].dt.date == target_date]
    if not same_day.empty:
        return _pick_site_incident(same_day)

    plus_minus_1 = site_df[
        (site_df["occurred_on"].dt.date >= (target_date - timedelta(days=1)))
        & (site_df["occurred_on"].dt.date <= (target_date + timedelta(days=1)))
    ]
    if not plus_minus_1.empty:
        return _pick_site_incident(plus_minus_1)
    return _pick_site_incident(site_df)


def build_site_alarm_report(site_df: pd.DataFrame, site_id_column: str, alarm_df: pd.DataFrame) -> pd.DataFrame:
    """Append alarm report columns to every row of the uploaded site sheet."""
    if site_id_column not in site_df.columns:
        raise ValueError(f"Site ID column '{site_id_column}' was not found in the uploaded sheet.")
    if alarm_df is None:
        raise ValueError("Load alarm data before generating the site report.")
    if "site_id" not in alarm_df.columns:
        raise ValueError("The loaded alarm data does not contain a site_id column.")

    out = site_df.copy()
    out["_site_report_key"] = out[site_id_column].map(normalize_site_key)
    report_column_names = _resolve_report_column_names(out.columns)

    alarm_work = alarm_df.copy()
    alarm_work["_site_report_key"] = alarm_work["site_id"].map(normalize_site_key)
    for col in ("occurred_on", "cleared_on"):
        if col in alarm_work.columns:
            alarm_work[col] = pd.to_datetime(alarm_work[col], errors="coerce", format="mixed")

    site_results: dict[str, dict[str, str]] = {}
    if not alarm_work.empty:
        for site_key, rows in alarm_work.groupby("_site_report_key", dropna=False):
            if not site_key:
                continue
            site_results[site_key] = _pick_site_incident(rows)

    for canonical, actual in report_column_names.items():
        out[actual] = out["_site_report_key"].map(
            lambda key, source_col=canonical: site_results.get(key, {}).get(source_col, "")
        )

    missing_mask = out["_site_report_key"].eq("")
    status_col = report_column_names["Alarm Match Status"]
    if missing_mask.any():
        out.loc[missing_mask, status_col] = "Missing site ID"
    unmatched_mask = (~missing_mask) & out[status_col].eq("")
    if unmatched_mask.any():
        out.loc[unmatched_mask, status_col] = "No alarms found"

    return out.drop(columns=["_site_report_key"], errors="ignore")


def collect_site_sheet_keys(site_df: pd.DataFrame, site_id_column: str) -> set[str]:
    """Collect normalized site identifiers from the uploaded site sheet."""
    if site_id_column not in site_df.columns:
        raise ValueError(f"Site ID column '{site_id_column}' was not found in the uploaded sheet.")
    return {
        normalize_site_key(value)
        for value in site_df[site_id_column].tolist()
        if normalize_site_key(value)
    }


def filter_site_sheet_to_matching_sites(
    site_df: pd.DataFrame,
    site_id_column: str,
    alarm_df: pd.DataFrame,
) -> pd.DataFrame:
    """Keep only uploaded site-sheet rows that match the provided alarm dataset."""
    if site_id_column not in site_df.columns:
        raise ValueError(f"Site ID column '{site_id_column}' was not found in the uploaded sheet.")
    if alarm_df is None or alarm_df.empty:
        return site_df.iloc[0:0].copy()
    if "site_id" not in alarm_df.columns:
        raise ValueError("The loaded alarm data does not contain a site_id column.")

    matched_keys = {
        normalize_site_key(value)
        for value in alarm_df["site_id"].dropna().tolist()
        if normalize_site_key(value)
    }
    if not matched_keys:
        return site_df.iloc[0:0].copy()

    site_keys = site_df[site_id_column].map(normalize_site_key)
    return site_df[site_keys.isin(matched_keys)].copy()


def build_pm_accept_report(
    pm_df: pd.DataFrame,
    site_id_column: str,
    date_column: str,
    bdt_results: list[Any],
    alarm_df: pd.DataFrame,
    health_pct: float,
    status_column: str | None = None,
) -> pd.DataFrame:
    """Build accepted-PM report from uploaded sheet + BDT validations + alarms."""
    if site_id_column not in pm_df.columns:
        raise ValueError(f"Site ID column '{site_id_column}' was not found in the uploaded sheet.")
    if date_column not in pm_df.columns:
        raise ValueError(f"Date column '{date_column}' was not found in the uploaded sheet.")

    out = pm_df.copy()
    out["_site_key"] = out[site_id_column].map(normalize_site_key)
    out["_target_date"] = out[date_column].map(_to_date_obj)

    if status_column and status_column in out.columns:
        status_series = out[status_column].astype(str).str.strip().str.lower()
        out = out[status_series.str.contains("accept", na=False)].copy()

    bdt_by_site_date: dict[tuple[str, date], list[Any]] = {}
    bdt_by_site: dict[str, list[Any]] = {}
    for res in bdt_results or []:
        site_key = normalize_site_key(getattr(res, "site_code", ""))
        if not site_key:
            continue
        bdt = getattr(res, "bdt_data", None)
        test_date = _to_date_obj(getattr(bdt, "test_date", None) if bdt is not None else getattr(res, "test_date", None))
        bdt_by_site.setdefault(site_key, []).append(res)
        if test_date is not None:
            bdt_by_site_date.setdefault((site_key, test_date), []).append(res)

    alarm_work = alarm_df.copy() if alarm_df is not None else pd.DataFrame()
    if not alarm_work.empty and "site_id" in alarm_work.columns:
        alarm_work["_site_key"] = alarm_work["site_id"].map(normalize_site_key)
        for col in ("occurred_on", "cleared_on"):
            if col in alarm_work.columns:
                alarm_work[col] = pd.to_datetime(alarm_work[col], errors="coerce", format="mixed")
        alarm_work = alarm_work.dropna(subset=["occurred_on"])

    col_map = _resolve_columns(out.columns, _PM_ACCEPT_REPORT_COLUMNS)
    for canonical, actual in col_map.items():
        out[actual] = ""

    for idx, row in out.iterrows():
        site_key = row.get("_site_key", "")
        target_date = row.get("_target_date", None)
        if not site_key:
            out.at[idx, col_map["Alarm Match Status"]] = "Missing site ID"
            continue

        chosen = None
        exact = bdt_by_site_date.get((site_key, target_date), []) if target_date else []
        if exact:
            chosen = exact[0]
        else:
            site_list = bdt_by_site.get(site_key, [])
            if site_list and target_date:
                site_list_sorted = sorted(
                    site_list,
                    key=lambda r: abs(
                        ((_to_date_obj(getattr(getattr(r, "bdt_data", None), "test_date", None) if getattr(r, "bdt_data", None) is not None else getattr(r, "test_date", None)) or target_date) - target_date).days
                    ),
                )
                chosen = site_list_sorted[0]
            elif site_list:
                chosen = site_list[0]

        if chosen is not None:
            bdt = getattr(chosen, "bdt_data", None)
            out.at[idx, col_map["Matched BDT File Name"]] = str(getattr(chosen, "filename", "") or "")
            out.at[idx, col_map["Matched BDT Test Date"]] = str(getattr(chosen, "test_date", "") or "")
            out.at[idx, col_map["Matched BDT Validation Verdict"]] = str(getattr(chosen, "overall", "") or "")
            theoretical = _theoretical_backup_minutes_like_bdt(bdt, health_pct)
            if theoretical is not None:
                out.at[idx, col_map["Theoretical Backup Time From BDT Inputs (mins)"]] = f"{theoretical:.1f}"
            actual_mins = getattr(bdt, "discharge_minutes", None) if bdt is not None else None
            if actual_mins is not None:
                out.at[idx, col_map["Measured Backup Time From BDT Test Duration (mins)"]] = f"{float(actual_mins):.1f}"

        if not alarm_work.empty and "_site_key" in alarm_work.columns:
            site_alarms = alarm_work[alarm_work["_site_key"] == site_key]
            incident = _pick_site_incident_for_date(site_alarms, target_date)
            out.at[idx, col_map["Power Alarm Start Time"]] = incident.get("Power Alarm At", "")
            out.at[idx, col_map["Down Alarm Start Time"]] = incident.get("Down Alarm At", "")
            out.at[idx, col_map["Backup Time Calculated From Alarm Pair (HH:MM:SS)"]] = incident.get("Backup Time", "")
            out.at[idx, col_map["Power Alarm Clear Time"]] = incident.get("Power Cleared At", "")
            out.at[idx, col_map["Alarm Correlation Status"]] = incident.get("Alarm Match Status", "")

    return out.drop(columns=["_site_key", "_target_date"], errors="ignore")
