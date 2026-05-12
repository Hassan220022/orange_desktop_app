"""Temp alarm correlation against Power alarm windows."""

from pathlib import Path
from dataclasses import replace
from datetime import date

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

try:
    from alarm_app.constants import TEMP_HEADERS
    from alarm_app.core.backup_time import fmt_td
    from alarm_app.core.duration import duration_to_secs
    from alarm_app.data.alarm_store import AlarmQuery, query_alarms
except ImportError:
    from constants import TEMP_HEADERS
    from core.backup_time import fmt_td
    from core.duration import duration_to_secs
    from data.alarm_store import AlarmQuery, query_alarms


TEMP_SUMMARY_BASE_COLUMNS = [
    "##",
    "Site Name",
    "Site Code",
    "Area",
    "Contractor",
    "No. Of HT Alarms",
    "HT Duration",
    "Batteries Types",
    "Batteries Status",
    "Week No.",
]


def compute_temp_alarm_matches(df: pd.DataFrame, margin_minutes: int = 60):
    """Find Temp alarms inside a same-site Power window plus Y margin."""
    if df.empty or "alarm_category" not in df.columns:
        return pd.DataFrame(), "No data loaded."

    margin_minutes = max(0, min(int(margin_minutes or 0), 60))
    need = [
        "site_id", "alarm_source", "alarm_name", "occurred_on", "cleared_on",
        "duration", "alarm_category", "network_type", "vendor", "clearance_status",
    ]
    sub = df[[c for c in need if c in df.columns]].copy()
    sub = sub.dropna(subset=["site_id", "occurred_on"])
    sub["site_id"] = sub["site_id"].astype(str).str.strip()
    sub["occurred_on"] = pd.to_datetime(sub["occurred_on"], errors="coerce", format="mixed")
    if "cleared_on" not in sub.columns:
        sub["cleared_on"] = pd.NaT
    sub["cleared_on"] = pd.to_datetime(sub["cleared_on"], errors="coerce", format="mixed")
    sub = sub.dropna(subset=["occurred_on"])

    pwr = sub[sub["alarm_category"] == "Power"].copy()
    tmp = sub[sub["alarm_category"] == "Temp"].copy()
    if pwr.empty:
        return pd.DataFrame(), "No Power alarms found in loaded data."
    if tmp.empty:
        return pd.DataFrame(), "No Temp alarms found in loaded data."

    tmp_by_site: dict[str, tuple[pd.DataFrame, pd.Series]] = {}
    for site_id, group in tmp.groupby("site_id", sort=False):
        sorted_group = group.sort_values("occurred_on").reset_index(drop=True)
        tmp_by_site[str(site_id)] = (sorted_group, sorted_group["occurred_on"])

    rows: list[dict[str, object]] = []
    y_delta = pd.Timedelta(minutes=margin_minutes)
    for _, power in pwr.sort_values("occurred_on").iterrows():
        site_id = str(power.get("site_id") or "").strip()
        power_time = power.get("occurred_on")
        power_cleared = power.get("cleared_on")
        if not site_id or pd.isna(power_time) or pd.isna(power_cleared) or power_cleared < power_time:
            continue

        site_temp_entry = tmp_by_site.get(site_id)
        if site_temp_entry is None:
            continue
        site_temp, temp_times = site_temp_entry
        window_end = power_cleared + y_delta
        start_idx = int(temp_times.searchsorted(power_time, side="left"))
        end_idx = int(temp_times.searchsorted(window_end, side="right"))
        if start_idx >= end_idx:
            continue
        matches = site_temp.iloc[start_idx:end_idx]
        for _, temp in matches.iterrows():
            temp_time = temp.get("occurred_on")
            temp_cleared = temp.get("cleared_on")
            after_clearance = temp_time - power_cleared if temp_time > power_cleared else None
            rows.append({
                "site_id": site_id,
                "network_type": power.get("network_type") or temp.get("network_type"),
                "vendor": power.get("vendor") or temp.get("vendor"),
                "power_time": _fmt_dt(power_time),
                "power_cleared": _fmt_dt(power_cleared),
                "x_duration": fmt_td(power_cleared - power_time),
                "y_margin": f"{margin_minutes} min",
                "temp_time": _fmt_dt(temp_time),
                "temp_cleared": _fmt_dt(temp_cleared),
                "temp_delay_after_power": fmt_td(temp_time - power_time),
                "temp_delay_after_power_clearance": fmt_td(after_clearance) if after_clearance is not None else "",
                "temp_clear_duration": _temp_duration(temp, temp_time, temp_cleared),
                "temp_alarm_name": temp.get("alarm_name") or "",
                "temp_alarm_source": temp.get("alarm_source") or "",
                "temp_clearance_status": temp.get("clearance_status") or "",
                "match_window": "Y margin" if after_clearance is not None else "Power window",
            })

    if not rows:
        return pd.DataFrame(), "No matching Temp alarms found in Power windows."
    return pd.DataFrame(rows).sort_values(["site_id", "temp_time"]).reset_index(drop=True), ""


def compute_temp_alarm_matches_for_query(
    alarm_query: AlarmQuery | None = None,
    margin_minutes: int = 60,
    result_filter_query: AlarmQuery | None = None,
):
    """Load a targeted alarm subset from DuckDB, then run temp analysis."""
    query = alarm_query or AlarmQuery()
    if result_filter_query is not None:
        temp_query = replace(
            result_filter_query,
            category="Temp",
            limit=None,
            offset=0,
            sort_by=None,
            sort_desc=False,
        )
        temp_df = query_alarms(temp_query)
        if temp_df.empty:
            return pd.DataFrame(), "No Temp alarms found in selected data.", temp_df
        site_ids = sorted({str(v).strip() for v in temp_df.get("site_id", pd.Series(dtype=object)).dropna() if str(v).strip()})
        power_query = replace(
            query,
            site_text="",
            category="Power",
            vendor="All",
            network_type="All",
            min_duration_secs=None,
            date_from=None,
            date_to=_source_query_date_to(result_filter_query),
            manual_days=None,
            site_scope_keys=site_ids or None,
            allowed_values={},
            column_filters={},
            col_filters={},
            limit=None,
            offset=0,
            sort_by=None,
            sort_desc=False,
        )
        power_df = query_alarms(power_query)
        df = pd.concat([power_df, temp_df], ignore_index=True)
    else:
        df = query_alarms(query)
    result, err = compute_temp_alarm_matches(df, margin_minutes=margin_minutes)
    if result_filter_query is not None and 'temp_df' in locals():
        result = filter_temp_matches_to_selected_temps(result, temp_df)
    return result, err, df


def _source_query_date_to(query: AlarmQuery) -> object:
    if query.date_to is not None:
        return query.date_to
    if query.manual_days is None:
        return None
    days = [pd.Timestamp(day).date() for day in query.manual_days if not pd.isna(pd.Timestamp(day))]
    return max(days) if days else None


def filter_temp_matches_to_query(matches: pd.DataFrame, alarm_query: AlarmQuery | None) -> pd.DataFrame:
    """Limit widened-query matches back to the user's original Temp alarm date scope."""
    if matches.empty or alarm_query is None or "temp_time" not in matches.columns:
        return matches
    times = pd.to_datetime(matches["temp_time"], errors="coerce", format="mixed")
    mask = pd.Series(True, index=matches.index)
    if alarm_query.date_from is not None:
        start = pd.Timestamp(alarm_query.date_from).normalize()
        mask &= times >= start
    if alarm_query.date_to is not None:
        end = pd.Timestamp(alarm_query.date_to).normalize() + pd.Timedelta(days=1)
        mask &= times < end
    if alarm_query.manual_days is not None:
        days = {
            pd.Timestamp(day).date()
            for day in alarm_query.manual_days
            if not pd.isna(pd.Timestamp(day))
        }
        if days:
            mask &= times.dt.date.isin(days)
    return matches[mask].reset_index(drop=True)


def filter_temp_matches_to_selected_temps(matches: pd.DataFrame, selected_temp: pd.DataFrame) -> pd.DataFrame:
    """Keep only matches whose Temp row exists in the already-filtered Temp set."""
    if matches.empty or selected_temp.empty or "site_id" not in matches.columns or "temp_time" not in matches.columns:
        return matches
    if "site_id" not in selected_temp.columns or "occurred_on" not in selected_temp.columns:
        return matches
    selected_key_cols = ["site_id", "occurred_on", "cleared_on", "alarm_name", "alarm_source"]
    match_key_cols = ["site_id", "temp_time", "temp_cleared", "temp_alarm_name", "temp_alarm_source"]
    if not all(col in selected_temp.columns for col in selected_key_cols) or not all(col in matches.columns for col in match_key_cols):
        selected_key_cols = ["site_id", "occurred_on"]
        match_key_cols = ["site_id", "temp_time"]
    selected_keys = {
        _temp_match_key(row, selected_key_cols)
        for row in selected_temp[selected_key_cols].dropna(subset=["site_id", "occurred_on"]).itertuples(index=False, name=None)
    }
    if not selected_keys:
        return matches.iloc[0:0].copy()
    keys = [_temp_match_key(row, match_key_cols) for row in matches[match_key_cols].itertuples(index=False, name=None)]
    mask = pd.Series([key in selected_keys for key in keys], index=matches.index)
    return matches[mask].reset_index(drop=True)


def _temp_match_key(row: tuple, columns: list[str]) -> tuple[str, ...]:
    values = []
    for col, value in zip(columns, row):
        if col in {"occurred_on", "cleared_on", "temp_time", "temp_cleared"}:
            timestamp = pd.to_datetime(value, errors="coerce")
            if pd.isna(timestamp):
                values.append("")
            else:
                values.append(pd.Timestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"))
        else:
            values.append(str(value or "").strip())
    return tuple(values)


def build_temp_alarm_summary(matches: pd.DataFrame, week_label: str | None = None) -> pd.DataFrame:
    """Build a W27-style site summary for matched Temp alarms."""
    week = week_label or _week_label_from_matches(matches)
    week_columns = _week_history_columns(week) if week else []
    columns = TEMP_SUMMARY_BASE_COLUMNS + week_columns
    if matches.empty:
        return pd.DataFrame(columns=columns)

    records = []
    for site_id, group in matches.groupby("site_id", sort=False):
        duration_secs = sum(duration_to_secs(value) for value in group["temp_clear_duration"])
        records.append({
            "Site Name": _first_text(group, "temp_alarm_source"),
            "Site Code": site_id,
            "Area": "",
            "Contractor": "",
            "No. Of HT Alarms": len(group),
            "HT Duration": _fmt_hours_minutes(duration_secs),
            "Batteries Types": "",
            "Batteries Status": "",
            "Week No.": week,
            **{col: (week if col == week else "") for col in week_columns},
        })
    summary = pd.DataFrame(records).sort_values(
        ["No. Of HT Alarms", "HT Duration"], ascending=[False, False]
    ).reset_index(drop=True)
    summary.insert(0, "##", range(1, len(summary) + 1))
    return summary[columns]


def export_temp_alarm_workbook(matches: pd.DataFrame, path: str | Path, week_label: str | None = None) -> None:
    """Export W27-style summary and matched detail rows to an Excel workbook."""
    summary = build_temp_alarm_summary(matches, week_label=week_label)
    detail_cols = [col for col in TEMP_HEADERS if col in matches.columns]
    details = matches[detail_cols].rename(columns=TEMP_HEADERS) if detail_cols else matches
    path = Path(path)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name=week_label or _week_label_from_matches(matches) or "Summary", index=False)
        details.to_excel(writer, sheet_name="Matched Temp Details", index=False)
    _format_temp_alarm_workbook(path, len(summary), len(matches))


def _fmt_dt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _temp_duration(temp: pd.Series, temp_time, temp_cleared) -> str:
    seconds = duration_to_secs(temp.get("duration"))
    if seconds > 0:
        return fmt_td(pd.Timedelta(seconds=seconds))
    if pd.notna(temp_time) and pd.notna(temp_cleared) and temp_cleared >= temp_time:
        return fmt_td(temp_cleared - temp_time)
    return ""


def _fmt_hours_minutes(seconds: float) -> str:
    total_minutes = int(seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def _week_history_columns(week_label: str, count: int = 8) -> list[str]:
    parsed = _parse_week_label(week_label)
    if parsed is None:
        return [week_label]
    year, week = parsed
    monday = date.fromisocalendar(year, week, 1)
    labels = []
    for offset in range(count):
        current = monday - pd.Timedelta(weeks=offset)
        iso = current.isocalendar()
        labels.append(f"W{int(iso.week):02d}-{str(int(iso.year))[-2:]}")
    return labels


def _parse_week_label(week_label: str) -> tuple[int, int] | None:
    text = str(week_label or "").strip().upper()
    if not text.startswith("W") or "-" not in text:
        return None
    week_text, year_text = text[1:].split("-", 1)
    try:
        week = int(week_text)
        year = int(year_text)
    except ValueError:
        return None
    year += 2000 if year < 100 else 0
    if week < 1 or week > 53:
        return None
    return year, week


def _week_label_from_matches(matches: pd.DataFrame) -> str:
    if matches.empty or "temp_time" not in matches.columns:
        return ""
    first = pd.to_datetime(matches["temp_time"], errors="coerce").dropna()
    if first.empty:
        return ""
    ts = first.min()
    iso = ts.isocalendar()
    return f"W{int(iso.week):02d}-{str(int(iso.year))[-2:]}"


def _first_text(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""
    values = df[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return values.iloc[0] if not values.empty else ""


def _format_temp_alarm_workbook(path: Path, summary_rows: int, detail_rows: int) -> None:
    wb = load_workbook(path)
    header_fill = PatternFill("solid", fgColor="4F81BD")
    border = Border(
        left=Side(style="thin", color="FF000000"),
        right=Side(style="thin", color="FF000000"),
        top=Side(style="thin", color="FF000000"),
        bottom=Side(style="thin", color="FF000000"),
    )
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = Font(bold=True)
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in ws.iter_rows(min_row=2, max_row=max(ws.max_row, 2)):
            for cell in row:
                cell.border = border
                cell.alignment = Alignment(vertical="center")
    if wb.worksheets:
        ws = wb.worksheets[0]
        widths = [6, 34, 12, 12, 14, 16, 12, 20, 20, 12]
        for index, width in enumerate(widths, start=1):
            ws.column_dimensions[chr(64 + index)].width = width
        for col in range(11, ws.max_column + 1):
            ws.column_dimensions[chr(64 + col)].width = 12
        for row in range(2, summary_rows + 2):
            ws.cell(row=row, column=7).number_format = "[hh]:mm"
    if len(wb.worksheets) > 1:
        ws = wb.worksheets[1]
        for col in range(1, ws.max_column + 1):
            ws.column_dimensions[chr(64 + col)].width = 20
        for row in range(2, detail_rows + 2):
            for col in (4, 5, 8, 9):
                ws.cell(row=row, column=col).number_format = "yyyy-mm-dd hh:mm:ss"
    wb.save(path)
