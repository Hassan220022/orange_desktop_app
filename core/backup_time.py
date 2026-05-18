"""Backup-time computation -- pure pandas/datetime, no Qt."""

from dataclasses import replace

import numpy as np
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

    down_by_site: dict[str, pd.Series] = {
        str(site_id): group["occurred_on"].sort_values().reset_index(drop=True)
        for site_id, group in dwn.groupby("site_id", sort=False)
    }
    parts: list[pd.DataFrame] = []
    for site_id, group in pwr.sort_values(["site_id", "occurred_on"]).groupby("site_id", sort=False):
        group = group.reset_index(drop=True)
        site_down = down_by_site.get(str(site_id))
        chosen_down = pd.Series(pd.NaT, index=group.index, dtype="datetime64[ns]")
        if site_down is not None and not site_down.empty:
            power_time = group["occurred_on"]
            power_cleared = group["cleared_on"]
            no_clear = power_cleared.isna()
            window_end = power_cleared.copy()
            window_end.loc[no_clear] = power_time.loc[no_clear].dt.normalize() + pd.Timedelta(days=1)
            start_idx = site_down.searchsorted(power_time, side="left")
            end_right = site_down.searchsorted(window_end, side="right")
            end_left = site_down.searchsorted(window_end, side="left")
            end_idx = np.where(no_clear.to_numpy(), end_left, end_right)
            has_down = start_idx < end_idx
            if has_down.any():
                chosen_down.loc[has_down] = site_down.iloc[end_idx[has_down] - 1].to_numpy()
        group["_chosen_down"] = chosen_down
        parts.append(group)

    if not parts:
        return pd.DataFrame(), "No matching Power alarms found."

    matched = pd.concat(parts, ignore_index=True)
    has_down = matched["_chosen_down"].notna()
    use_cleared = ~has_down & matched["cleared_on"].notna() & (matched["cleared_on"] >= matched["occurred_on"])
    keep = has_down | use_cleared
    if not keep.any():
        return pd.DataFrame(), "No matching Power alarms found."

    kept = matched.loc[keep].copy()
    chosen_end = kept["_chosen_down"].where(kept["_chosen_down"].notna(), kept["cleared_on"])
    kept["_backup_td"] = chosen_end - kept["occurred_on"]
    merged = pd.DataFrame({
        "site_id": kept["site_id"],
        "network_type": kept["network_type"] if "network_type" in kept.columns else None,
        "vendor": kept["vendor"] if "vendor" in kept.columns else None,
        "power_time": kept["occurred_on"].dt.strftime("%Y-%m-%d %H:%M:%S"),
        "power_cleared": kept["cleared_on"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna(""),
        "down_time": kept["_chosen_down"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna(""),
        "end_event_type": np.where(kept["_chosen_down"].notna(), "Power→Down", "Power→Cleared"),
        "backup_time": [_fmt_seconds_to_hhmmss(value.total_seconds()) for value in kept["_backup_td"]],
        "_backup_td": kept["_backup_td"],
    }).sort_values("_backup_td", ascending=False).reset_index(drop=True)
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
    if query.category == "All":
        base = {"limit": None, "offset": 0, "sort_by": None, "sort_desc": False}
        power_df = query_alarms(replace(query, category="Power", **base))
        down_df = query_alarms(replace(query, category="Down", **base))
        df = pd.concat([power_df, down_df], ignore_index=True)
    else:
        df = query_alarms(query)
    return compute_backup_times(df)


def fmt_td(td):
    """Format a timedelta as HH:MM:SS."""
    return _fmt_seconds_to_hhmmss(td.total_seconds())


def _fmt_seconds_to_hhmmss(seconds: float) -> str:
    total = int(seconds)
    h, r  = divmod(total, 3600)
    m, s  = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
