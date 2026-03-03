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
def discover_alarm_files(directory: str) -> list[dict]:
    """
    Recursively walk *directory* and return metadata dicts for every
    .csv / .xlsx / .xls file found.
    """
    results: list[dict] = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname.startswith("._") or fname.startswith("~$"):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _EXTS:
                continue
            full = os.path.join(root, fname)
            rel  = os.path.relpath(full, directory)
            kb   = os.path.getsize(full) / 1024
            results.append({
                "path": full, "rel_path": rel,
                "filename": fname, "ext": ext,
                "size_kb": kb,
            })
    return results


# ─────────────────────────────────────────────────────────────────
# Single-file parser
# ─────────────────────────────────────────────────────────────────
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
                df = pd.read_excel(fp, engine="openpyxl")
            if df is not None and not df.empty:
                break
        except Exception:
            continue

    if df is None or df.empty:
        return None

    # Normalise headers
    df.columns = [str(c).strip() for c in df.columns]
    cols = set(df.columns)

    # Choose schema
    if "Site ID" in cols and "Site Name" not in cols:
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
            combined = pd.concat(dfs, ignore_index=True, copy=False)

            # Fast vectorised datetime conversion
            for col in ("occurred_on", "cleared_on"):
                if col in combined.columns:
                    combined[col] = pd.to_datetime(
                        combined[col], errors="coerce", format="mixed")

            if "site_id" in combined.columns:
                combined["site_id"] = (
                    combined["site_id"].astype(str).str.strip())

            # Step 4: Pre-computed duration seconds for fast filtering
            if "duration" in combined.columns:
                parts = (combined["duration"]
                         .fillna("")
                         .astype(str)
                         .str.split(":", expand=True))
                if parts.shape[1] >= 3:
                    h = pd.to_numeric(parts[0], errors="coerce").fillna(0.0)
                    m = pd.to_numeric(parts[1], errors="coerce").fillna(0.0)
                    s = pd.to_numeric(parts[2], errors="coerce").fillna(0.0)
                    combined["_duration_secs"] = h * 3600 + m * 60 + s
                else:
                    combined["_duration_secs"] = 0.0

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
