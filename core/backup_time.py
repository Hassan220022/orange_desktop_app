"""Backup-time computation -- pure pandas/datetime, no Qt."""

import pandas as pd

try:
    from ..data.alarm_store import AlarmQuery, query_alarms
except ImportError:
    try:
        from alarm_app.data.alarm_store import AlarmQuery, query_alarms
    except ImportError:
        from data.alarm_store import AlarmQuery, query_alarms


def compute_backup_times(df: pd.DataFrame):
    """
    For each site, find Down alarms that fall **inside** a Power alarm's
    time window (power_occurred_on -> power_cleared_on).  The backup time
    is how long the battery held: down_occurred_on - power_occurred_on.

    When multiple techs (2G/3G/4G/5G) go down within the same power
    outage, only the **longest** backup time is kept (last tech to die).

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
    if dwn.empty:
        return pd.DataFrame(), "No Down alarms found in loaded data."

    # Build power-event table with the outage window
    p_cols = ["site_id", "occurred_on"]
    if "cleared_on" in pwr.columns:
        p_cols.append("cleared_on")
    p_extra = [c for c in ("network_type", "vendor") if c in pwr.columns]
    p_cols += p_extra
    pwr = pwr[p_cols].rename(columns={
        "occurred_on": "power_time",
        "cleared_on":  "power_cleared",
    })
    # Drop power alarms with no cleared time (still active -- no window)
    pwr = pwr.dropna(subset=["power_cleared"])

    dwn = (dwn[["site_id", "occurred_on"]]
           .rename(columns={"occurred_on": "down_time"}))

    # Inner-join on site_id, then filter: down_time inside [power_time, power_cleared]
    merged = pwr.merge(dwn, on="site_id", how="inner")
    merged = merged[
        (merged["down_time"] >= merged["power_time"])
        & (merged["down_time"] <= merged["power_cleared"])
    ].copy()

    if merged.empty:
        return pd.DataFrame(), (
            "No Down alarms found inside any Power alarm window.")

    merged["backup_td"] = merged["down_time"] - merged["power_time"]

    # Per incident (site + power_time), keep only the LONGEST backup
    # (= the last technology to go down).
    idx = merged.groupby(["site_id", "power_time"])["backup_td"].idxmax()
    merged = merged.loc[idx].copy()

    merged["backup_time"]    = merged["backup_td"].apply(fmt_td)
    merged["power_time"]     = merged["power_time"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    merged["power_cleared"]  = merged["power_cleared"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    merged["down_time"]      = merged["down_time"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    merged = merged.sort_values("backup_td", ascending=False).reset_index(drop=True)

    out = [c for c in ["site_id", "network_type", "vendor",
                        "power_time", "power_cleared",
                        "down_time", "backup_time"]
           if c in merged.columns]
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
