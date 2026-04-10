"""Duration conversion helpers (string <-> numeric seconds)."""

import datetime as _dt

import pandas as pd


def duration_to_secs(val) -> float:
    """Convert a duration value (str, time, Timestamp) to seconds."""
    if pd.isna(val) or val is None:
        return 0.0
    # datetime.time object
    if isinstance(val, _dt.time):
        return val.hour * 3600 + val.minute * 60 + val.second
    # Timestamp (Excel serial date like 1900-01-01 00:02:20)
    if isinstance(val, pd.Timestamp):
        return val.hour * 3600 + val.minute * 60 + val.second
    # String "HH:MM:SS"
    s = str(val).strip()
    parts = s.split(":")
    if len(parts) >= 3:
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except (ValueError, TypeError):
            pass
    return 0.0


def secs_to_hhmmss(s) -> str:
    """Convert seconds to HH:MM:SS string."""
    if s <= 0:
        return ""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"
