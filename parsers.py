"""
Parsers — file discovery, CSV/XLSX parsing, and threaded background loader.

Optimisations:
 • Encoding detection tries utf-8-sig first (covers BOM and plain UTF-8)
   before falling back to latin-1.  cp1252 is skipped because latin-1 is
   a strict superset for all byte values.
 • Column renaming uses a single dict-comprehension instead of two passes.
 • datetime conversion uses format= hint when possible.
 • Concatenation uses copy=False to avoid redundant memory copies.
"""

import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np

from PyQt5.QtCore import QThread, pyqtSignal

from .constants import SCHEMA_1_MAP, SCHEMA_2_MAP, ALL_INTERNAL_COLS

_EXTS = frozenset((".csv", ".xlsx", ".xls"))
_ENCODINGS = ("utf-8-sig", "latin-1")          # utf-8-sig covers plain utf-8 too


# ─────────────────────────────────────────────────────────────────
# File discovery
# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# Header validation (shared by discovery + parsing)
# ─────────────────────────────────────────────────────────────────
_SCHEMA_KEYS_1 = frozenset(SCHEMA_1_MAP.keys())
_SCHEMA_KEYS_2 = frozenset(SCHEMA_2_MAP.keys())
_MIN_MATCH = 3  # minimum columns that must match to qualify as alarm data


def _is_alarm_header(columns: list[str]) -> bool:
    """Quick check whether column headers look like alarm data."""
    col_set = {str(c).strip() for c in columns}
    return (len(col_set & _SCHEMA_KEYS_1) >= _MIN_MATCH
            or len(col_set & _SCHEMA_KEYS_2) >= _MIN_MATCH)


def _quick_header_check(path: str, ext: str) -> bool:
    """Read only the header row and verify it matches an alarm schema.

    Uses calamine (fast Rust reader) for xlsx/xls, falling back to
    openpyxl if calamine is unavailable or fails.  Returns False for
    files that aren't alarm data (BDT files, random spreadsheets, etc.).
    """
    try:
        if ext == ".csv":
            for enc in _ENCODINGS:
                try:
                    df = pd.read_csv(path, encoding=enc, nrows=0)
                    return _is_alarm_header(df.columns.tolist())
                except Exception:
                    continue
            return False
        # xlsx / xls — try calamine first (Rust-based, ~3x faster)
        try:
            df = pd.read_excel(path, engine="calamine", nrows=0)
            return _is_alarm_header(df.columns.tolist())
        except Exception:
            pass
        # Fallback to openpyxl read_only for header-only access
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True)
        try:
            ws = wb.active
            if ws is None:
                return False
            headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
            return _is_alarm_header(headers)
        finally:
            wb.close()
    except Exception:
        return False


# Filename patterns that strongly indicate alarm data — skip header check
_ALARM_NAME_HINTS = ("alarm", "power_alarm", "down_alarm")


def discover_alarm_files(directory: str) -> list[dict]:
    """
    Recursively walk *directory* and return metadata dicts for every
    alarm-format .csv / .xlsx / .xls file found.

    Performs a fast header check on each file so only genuine alarm
    data appears in the list — BDT files, random spreadsheets, etc.
    are silently skipped.
    """
    results: list[dict] = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname.startswith("._") or fname.startswith("~$"):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _EXTS:
                continue
            # Fast skip: BDT files by name
            fl = fname.lower()
            if "bdt" in fl:
                continue
            full = os.path.join(root, fname)
            # Trust filenames that clearly indicate alarm data
            name_ok = any(hint in fl for hint in _ALARM_NAME_HINTS)
            if not name_ok:
                # Unknown file — verify header before listing
                if not _quick_header_check(full, ext):
                    continue
            rel  = os.path.relpath(full, directory)
            kb   = os.path.getsize(full) / 1024
            results.append({
                "path": full, "rel_path": rel,
                "filename": fname, "ext": ext,
                "size_kb": kb,
            })
    return results


def parse_alarm_file(info: dict) -> pd.DataFrame | None:
    """Parse one alarm file described by a discovery dict.  Returns None on failure."""
    fp, ext, fname = info["path"], info["ext"], info["filename"]
    df = None

    for enc in _ENCODINGS:
        try:
            if ext == ".csv":
                df = pd.read_csv(fp, encoding=enc,
                                 on_bad_lines="skip", low_memory=False)
            else:
                # calamine (Rust-based) is ~3x faster than openpyxl for read-only
                try:
                    df = pd.read_excel(fp, engine="calamine")
                except Exception:
                    df = pd.read_excel(fp, engine="openpyxl")
            if df is not None and not df.empty:
                break
        except Exception:
            continue

    if df is None or df.empty:
        return None

    # Normalise headers
    df.columns = [str(c).strip() for c in df.columns]

    # Early reject: skip files that don't match any alarm schema
    if not _is_alarm_header(df.columns.tolist()):
        return None

    cols = set(df.columns)

    # Choose schema
    if "FM Office" in cols or ("Site ID" in cols and "Site Name" not in cols):
        rmap = {k: v for k, v in SCHEMA_2_MAP.items() if k in cols}
    else:
        rmap = {k: v for k, v in SCHEMA_1_MAP.items() if k in cols}

    df = df.rename(columns=rmap)
    fname_lower = fname.lower()
    if "power" in fname_lower:
        df["alarm_category"] = "Power"
    elif "down" in fname_lower:
        df["alarm_category"] = "Down"
    else:
        df["alarm_category"] = ""
    df["file_source"]    = fname

    # Ensure every expected column exists
    for col in ALL_INTERNAL_COLS:
        if col not in df.columns:
            df[col] = np.nan

    return df[ALL_INTERNAL_COLS]


def classify_by_alarm_id(df: pd.DataFrame, alarm_ids: dict) -> pd.DataFrame:
    """Classify alarm_category based on alarm_id matching configured ID lists.

    Args:
        df: DataFrame with 'alarm_id' and 'alarm_category' columns.
        alarm_ids: {"power": ["id1", ...], "down": ["id1", ...]}
    Returns:
        DataFrame with updated 'alarm_category' column.
    """
    if df.empty or "alarm_id" not in df.columns:
        return df
    power_set = set(alarm_ids.get("power", []))
    down_set  = set(alarm_ids.get("down", []))
    # Normalize: floats like 300.0 → "300", strings stay as-is
    aid = (df["alarm_id"].fillna("").astype(str).str.strip()
           .str.replace(r'\.0$', '', regex=True))
    df = df.copy()
    df.loc[aid.isin(power_set), "alarm_category"] = "Power"
    df.loc[aid.isin(down_set),  "alarm_category"] = "Down"
    return df


def compute_site_down_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Compute site_down_flag.

    - Down alarms → always 'Yes' (site went down by definition).
    - Power alarms → 'Yes' only if a Down alarm occurred on the same site
      within the Power alarm's [occurred_on, cleared_on] window
      (meaning the battery didn't hold and the site went down).
    - Everything else → 'No'.
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


# ─────────────────────────────────────────────────────────────────
# Duration helpers
# ─────────────────────────────────────────────────────────────────
def _duration_to_secs(val) -> float:
    """Convert a duration value (str, time, Timestamp) to seconds."""
    if pd.isna(val) or val is None:
        return 0.0
    # datetime.time object
    import datetime as _dt
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


def _secs_to_hhmmss(s) -> str:
    """Convert seconds to HH:MM:SS string."""
    if s <= 0:
        return ""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


# ─────────────────────────────────────────────────────────────────
# Background loader thread
# ─────────────────────────────────────────────────────────────────
class LoaderThread(QThread):
    """Load selected files in a background thread.

    Signals:
        progress(int, str)  — percentage + status message
        finished(DataFrame, str) — merged data + summary message
        error(str) — traceback on failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, str)
    error    = pyqtSignal(str)

    def __init__(self, file_infos: list[dict]):
        super().__init__()
        self.file_infos = file_infos

    def run(self):
        try:
            dfs: list[pd.DataFrame] = []
            total = len(self.file_infos)

            # Sort largest-first so big files start immediately
            ordered = sorted(
                enumerate(self.file_infos),
                key=lambda t: t[1].get("size_kb", 0),
                reverse=True,
            )

            workers = min(total, os.cpu_count() or 1, 6)
            done_count = 0

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(parse_alarm_file, info): idx
                    for idx, info in ordered
                }
                for future in as_completed(futures):
                    done_count += 1
                    idx = futures[future]
                    info = self.file_infos[idx]
                    self.progress.emit(
                        int(done_count / total * 90),
                        f"[{done_count}/{total}]  {info['filename']}",
                    )
                    try:
                        df = future.result()
                        if df is not None and not df.empty:
                            dfs.append(df)
                    except Exception:
                        pass  # individual file failures silently skipped

            if not dfs:
                self.error.emit(
                    "No readable alarm records found in selected files.")
                return

            self.progress.emit(95, "Merging records …")
            combined = pd.concat(dfs, ignore_index=True)

            # Fast vectorised datetime conversion
            for col in ("occurred_on", "cleared_on"):
                if col in combined.columns:
                    combined[col] = pd.to_datetime(
                        combined[col], errors="coerce", format="mixed")

            if "site_id" in combined.columns:
                combined["site_id"] = (
                    combined["site_id"].astype(str).str.strip())

            # Compute duration for records that don't have it (Nokia)
            if "duration" in combined.columns:
                missing_dur = combined["duration"].fillna("").astype(str).str.strip().eq("")
                if missing_dur.any():
                    has_times = (missing_dur
                                 & combined["occurred_on"].notna()
                                 & combined["cleared_on"].notna())
                    if has_times.any():
                        td = combined.loc[has_times, "cleared_on"] - combined.loc[has_times, "occurred_on"]
                        total_secs = td.dt.total_seconds().fillna(0)
                        h = (total_secs // 3600).astype(int)
                        m = ((total_secs % 3600) // 60).astype(int)
                        s = (total_secs % 60).astype(int)
                        combined.loc[has_times, "duration"] = (
                            h.astype(str).str.zfill(2) + ":"
                            + m.astype(str).str.zfill(2) + ":"
                            + s.astype(str).str.zfill(2))

            # Pre-computed duration seconds for fast filtering
            # Handles str "HH:MM:SS", datetime.time, and Timestamp objects
            if "duration" in combined.columns:
                combined["_duration_secs"] = combined["duration"].apply(_duration_to_secs)
                # Normalize duration display to HH:MM:SS strings
                combined["duration"] = combined["_duration_secs"].apply(_secs_to_hhmmss)

            self.progress.emit(100, "Done!")
            self.finished.emit(
                combined,
                f"Loaded {len(combined):,} records from {len(dfs)} file(s)",
            )
        except Exception:
            self.error.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────
# Background export thread
# ─────────────────────────────────────────────────────────────────
class ExportThread(QThread):
    """Write a DataFrame to Excel in a background thread.

    Signals:
        progress(int, str)  — percentage + status message
        finished(str)       — file path on success
        error(str)          — error message on failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, path: str):
        super().__init__()
        self._df = df
        self._path = path

    def run(self):
        try:
            self.progress.emit(30, "Writing Excel file …")
            self._df.to_excel(self._path, index=False, engine="openpyxl")
            self.progress.emit(100, "Export complete")
            self.finished.emit(self._path)
        except Exception:
            self.error.emit(traceback.format_exc())


class BDTValidationThread(QThread):
    """Parse and validate BDT files in a background thread.

    Signals:
        progress(int, str) — percentage + status message
        finished(list, dict) — (ValidationResult list, site→BDTData dict)
        error(str)         — error message on failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, object)
    error    = pyqtSignal(str)

    def __init__(self, bdt_files: list[str], alarm_df,
                 tolerance: float, health_pct: float):
        super().__init__()
        self._files = bdt_files
        self._alarm_df = alarm_df
        self._tolerance = tolerance
        self._health_pct = health_pct

    def run(self):
        from .bdt_parser import parse_bdt_file
        from .bdt_validator import validate_bdt
        from datetime import datetime

        try:
            total = len(self._files)
            results = []
            by_site: dict[str, list] = {}
            done = 0

            workers = min(total, os.cpu_count() or 1, 8)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(parse_bdt_file, fp, skip_photos=True): fp
                    for fp in self._files
                }
                for future in as_completed(futures):
                    done += 1
                    fp = futures[future]
                    fname = os.path.basename(fp)
                    pct = int(done / total * 90)
                    self.progress.emit(
                        pct, f"[{done}/{total}]  {fname}")

                    try:
                        bdt_data = future.result()
                    except Exception:
                        continue

                    result = validate_bdt(
                        bdt_data, self._alarm_df,
                        self._tolerance, self._health_pct)
                    results.append(result)

                    if bdt_data.site_code:
                        key = bdt_data.site_code.strip().upper()
                        by_site.setdefault(key, []).append(bdt_data)

            self.progress.emit(95, "Sorting results…")

            # Sort each site's tests by date (newest first)
            for key in by_site:
                by_site[key].sort(
                    key=lambda b: b.test_date or datetime.min,
                    reverse=True)

            self.progress.emit(100, "Done!")
            self.finished.emit(results, by_site)

        except Exception:
            self.error.emit(traceback.format_exc())
