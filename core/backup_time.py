"""Backup-time computation -- pure pandas/datetime, no Qt."""

import pandas as pd

try:
    from alarm_app.data.alarm_store import AlarmQuery, query_alarms
except ImportError:
    from data.alarm_store import AlarmQuery, query_alarms


def compute_backup_times(df: pd.DataFrame):
    """
    For each site, find Power alarms and measure the incident duration as:

        backup_time = end_event_time - power_occurred_on

    where ``end_event_time`` is the matching Down alarm time when one exists
    inside the same power window, otherwise the Power alarm's cleared time.

    When multiple Down alarms fall inside the same power outage, only the
    **latest** Down alarm is kept (last tech to die). If no Down alarm exists,
    the Power→Cleared path is used as a fallback.

    Returns ``(result_df, error_msg)``.  *error_msg* is ``''`` on success.
    """
    if df.empty or "alarm_category" not in df.columns:
        return pd.DataFrame(), "No data loaded."

    need = ["site_id", "occurred_on", "cleared_on", "alarm_category",
            "network_type", "vendor"]
    sub = df[[c for c in need if c in df.columns]].copy()
    sub = sub.dropna(subset=["site_id", "occurred_on"])
    sub["site_id"] = sub["site_id"].astype(str).str.strip()

    pwr = sub[sub["alarm_category"] == "Power"].copy()
    dwn = sub[sub["alarm_category"] == "Down"].copy()

    if pwr.empty:
        return pd.DataFrame(), "No Power alarms found in loaded data."
    pwr = pwr.copy()
    if "cleared_on" not in pwr.columns:
        pwr["cleared_on"] = pd.NaT

    p_cols = ["site_id", "occurred_on", "cleared_on"]
    p_extra = [c for c in ("network_type", "vendor") if c in pwr.columns]
    p_cols += p_extra
    pwr = pwr[p_cols].copy()
    pwr["occurred_on"] = pd.to_datetime(pwr["occurred_on"], errors="coerce", format="mixed")
    pwr["cleared_on"] = pd.to_datetime(pwr["cleared_on"], errors="coerce", format="mixed")
    pwr = pwr.dropna(subset=["occurred_on"])

    dwn = dwn[["site_id", "occurred_on"]].copy()
    dwn["occurred_on"] = pd.to_datetime(dwn["occurred_on"], errors="coerce", format="mixed")
    dwn = dwn.dropna(subset=["occurred_on"])

    rows: list[dict[str, object]] = []
    down_by_site: dict[str, pd.DataFrame] = {
        str(site_id): group.sort_values("occurred_on").reset_index(drop=True)
        for site_id, group in dwn.groupby("site_id", sort=False)
    }

    for _, power in pwr.sort_values("occurred_on").iterrows():
        site_id = str(power.get("site_id") or "").strip()
        if not site_id:
            continue
        power_time = power.get("occurred_on")
        if pd.isna(power_time):
            continue
        power_cleared = power.get("cleared_on")
        site_down = down_by_site.get(site_id)

        chosen_end = None
        chosen_type = ""
        chosen_down = None
        if site_down is not None and not site_down.empty:
            if pd.notna(power_cleared):
                in_window = site_down[
                    (site_down["occurred_on"] >= power_time)
                    & (site_down["occurred_on"] <= power_cleared)
                ]
            else:
                in_window = site_down[
                    (site_down["occurred_on"] >= power_time)
                    & (site_down["occurred_on"].dt.normalize() == pd.Timestamp(power_time).normalize())
                ]
            if not in_window.empty:
                chosen_down = in_window.iloc[-1]["occurred_on"]
                chosen_end = chosen_down
                chosen_type = "Power→Down"

        if chosen_end is None and pd.notna(power_cleared) and power_cleared >= power_time:
            chosen_end = power_cleared
            chosen_type = "Power→Cleared"

        if chosen_end is None:
            continue

        backup_td = chosen_end - power_time
        rows.append({
            "site_id": site_id,
            "network_type": power.get("network_type"),
            "vendor": power.get("vendor"),
            "power_time": power_time.strftime("%Y-%m-%d %H:%M:%S"),
            "power_cleared": power_cleared.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(power_cleared) else "",
            "down_time": chosen_down.strftime("%Y-%m-%d %H:%M:%S") if chosen_down is not None else "",
            "end_event_type": chosen_type,
            "backup_time": fmt_td(backup_td),
            "_backup_td": backup_td,
        })

    if not rows:
        return pd.DataFrame(), "No matching Power alarms found."

    merged = pd.DataFrame(rows).sort_values("_backup_td", ascending=False).reset_index(drop=True)
    merged = merged.drop(columns=["_backup_td"])

    out = [c for c in [
        "site_id",
        "network_type",
        "vendor",
        "power_time",
        "power_cleared",
        "down_time",
        "end_event_type",
        "backup_time",
    ] if c in merged.columns]
    return merged[out], ""


def compute_backup_times_for_query(alarm_query: AlarmQuery | None = None):
    """Load a targeted alarm subset from DuckDB, then run backup analysis."""
    query = alarm_query or AlarmQuery()
    df = query_alarms(query)
    return compute_backup_times(df)


def fmt_td(td):
    """Format a timedelta as HH:MM:SS."""
    total = int(td.total_seconds())
    h, r  = divmod(total, 3600)
    m, s  = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
