"""Site-sheet report helpers for alarm export workflows."""

from __future__ import annotations

import os
import re
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
