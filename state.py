"""
State persistence — save/restore UI state and DataFrame cache across sessions.

Uses ~/.alarm_viewer/ with:
  state.json        — UI settings, filter values, window geometry
  data_cache.parquet — full DataFrame for fast restore (~1s vs 10-30s)
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

STATE_DIR  = Path.home() / ".alarm_viewer"
STATE_FILE = STATE_DIR / "state.json"
CACHE_FILE = STATE_DIR / "data_cache.parquet"


def save_state(state_dict: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_dict["saved_at"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state_dict, indent=2, default=str),
                          encoding="utf-8")


def load_state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_dataframe(df: pd.DataFrame):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Coerce object columns (e.g. duration with mixed str/datetime.time)
    # to strings so Parquet serialisation doesn't choke on mixed types.
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].fillna("").astype(str)
    out.to_parquet(CACHE_FILE, index=False, engine="pyarrow")


def load_dataframe() -> pd.DataFrame | None:
    try:
        if CACHE_FILE.exists():
            return pd.read_parquet(CACHE_FILE, engine="pyarrow")
    except Exception:
        pass
    return None


def clear_cache():
    for f in (STATE_FILE, CACHE_FILE):
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass


# ── Alarm ID configuration ────────────────────────────────
ALARM_IDS_FILE = STATE_DIR / "alarm_ids.json"

def load_alarm_ids() -> dict:
    """Return {"power": [...], "down": [...], "door": [...]} from config."""
    try:
        if ALARM_IDS_FILE.exists():
            data = json.loads(ALARM_IDS_FILE.read_text(encoding="utf-8"))
            return {
                "power": [str(x).strip() for x in data.get("power", [])],
                "down":  [str(x).strip() for x in data.get("down", [])],
                "door":  [str(x).strip() for x in data.get("door", [])],
            }
    except Exception:
        pass
    return {"power": [], "down": [], "door": []}


def save_alarm_ids(ids: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ALARM_IDS_FILE.write_text(
        json.dumps(ids, indent=2), encoding="utf-8")


# ── File hash change detection ───────────────────────────
def compute_file_hashes(file_paths: list[str]) -> dict[str, str]:
    """Return {path: md5_hex} for each file that exists."""
    hashes = {}
    for fp in file_paths:
        try:
            if os.path.isfile(fp):
                h = hashlib.md5()
                with open(fp, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                hashes[fp] = h.hexdigest()
        except Exception:
            pass
    return hashes


def files_changed(saved_hashes: dict[str, str],
                  file_paths: list[str]) -> bool:
    """Return True if any source file was added, removed, or modified."""
    if not saved_hashes:
        return True
    if set(saved_hashes.keys()) != set(file_paths):
        return True
    current = compute_file_hashes(file_paths)
    return current != saved_hashes
