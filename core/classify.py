"""Alarm classification helpers (pure DataFrame transforms, no I/O or Qt)."""

import pandas as pd


def classify_by_alarm_id(df: pd.DataFrame, alarm_ids: dict) -> pd.DataFrame:
    """Classify alarm_category based on alarm_id matching configured ID lists.

    Args:
        df: DataFrame with 'alarm_id' and 'alarm_category' columns.
        alarm_ids: {"power": [...], "down": [...], "door": [...]}
    Returns:
        DataFrame with updated 'alarm_category' column.
    """
    if df.empty or "alarm_id" not in df.columns:
        return df
    power_set = set(alarm_ids.get("power", []))
    down_set  = set(alarm_ids.get("down", []))
    door_set  = set(alarm_ids.get("door", []))
    # Normalize: floats like 300.0 -> "300", strings stay as-is
    aid = (df["alarm_id"].fillna("").astype(str).str.strip()
           .str.replace(r'\.0$', '', regex=True))
    df = df.copy()
    df.loc[aid.isin(power_set), "alarm_category"] = "Power"
    df.loc[aid.isin(down_set),  "alarm_category"] = "Down"
    df.loc[aid.isin(door_set),  "alarm_category"] = "Door"

    # Heuristic fallback so door alarms are visible even without configured IDs.
    door_mask = pd.Series(False, index=df.index)
    door_rx = r"(?:^|[^a-z])door(?:[^a-z]|$)"
    for col in ("alarm_name", "file_source", "alarm_source"):
        if col in df.columns:
            door_mask |= df[col].astype(str).str.contains(
                door_rx, case=False, na=False, regex=True)
    df.loc[door_mask, "alarm_category"] = "Door"
    return df


def compute_site_down_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Compute site_down_flag.

    - Down alarms: always 'Yes' (site went down by definition).
    - Power alarms: 'Yes' only if a Down alarm occurred on the same site
      within the Power alarm's [occurred_on, cleared_on] window
      (meaning the battery didn't hold and the site went down).
    - Everything else: 'No'.
    """
    if df.empty or "alarm_category" not in df.columns:
        return df

    df = df.copy()
    df["site_down_flag"] = "No"

    # All Down alarms = site is down
    df.loc[df["alarm_category"] == "Down", "site_down_flag"] = "Yes"

    need = ["site_id", "occurred_on", "cleared_on"]
    if not all(c in df.columns for c in need):
        return df

    pwr = df[df["alarm_category"] == "Power"].dropna(subset=["site_id", "occurred_on"])
    dwn = df[df["alarm_category"] == "Down"].dropna(subset=["site_id", "occurred_on"])

    if pwr.empty or dwn.empty:
        return df

    # For Power alarms: flag 'Yes' if a Down alarm fell inside its window
    pwr_data = pwr[["site_id", "occurred_on", "cleared_on"]].copy()
    pwr_data["_pwr_idx"] = pwr.index
    dwn_data = dwn[["site_id", "occurred_on"]].rename(
        columns={"occurred_on": "down_time"})

    merged = pwr_data.merge(dwn_data, on="site_id")
    mask = merged["down_time"] >= merged["occurred_on"]
    mask = mask & (merged["down_time"] <= merged["cleared_on"].fillna(pd.Timestamp.max))

    matched_power_idx = merged.loc[mask, "_pwr_idx"].unique()
    df.loc[matched_power_idx, "site_down_flag"] = "Yes"

    return df
