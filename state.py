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
from uuid import uuid4

import pandas as pd

STATE_DIR  = Path.home() / ".alarm_viewer"
STATE_FILE = STATE_DIR / "state.json"
CACHE_FILE = STATE_DIR / "data_cache.parquet"
REVIEW_LOG_FILE = STATE_DIR / "review_log.jsonl"
OUTBOX_FILE = STATE_DIR / "sync_outbox.jsonl"
SYNC_CHECKPOINT_FILE = STATE_DIR / "sync_checkpoint.json"
DEVICE_ID_FILE = STATE_DIR / "device_id.txt"


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


# ── Review log / daily report ──────────────────────────────
def append_review_event(
    *,
    username: str,
    filename: str,
    site_code: str,
    test_date: str,
    verdict: str,
    reviewed_at: str | None = None,
) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "reviewed_at": reviewed_at or datetime.now().isoformat(),
        "username": str(username or "").strip(),
        "filename": str(filename or ""),
        "site_code": str(site_code or ""),
        "test_date": str(test_date or ""),
        "verdict": str(verdict or ""),
    }
    with REVIEW_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")


def load_review_events() -> list[dict]:
    events: list[dict] = []
    try:
        if not REVIEW_LOG_FILE.exists():
            return events
        for line in REVIEW_LOG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if isinstance(event, dict):
                events.append(event)
    except Exception:
        return []
    return events


def summarize_review_events_by_day(events: list[dict] | None = None) -> list[dict]:
    rows = events if events is not None else load_review_events()
    buckets: dict[str, dict] = {}
    for event in rows:
        raw_ts = str(event.get("reviewed_at", "") or "")
        day = raw_ts[:10] if len(raw_ts) >= 10 else ""
        if not day:
            continue
        bucket = buckets.setdefault(
            day,
            {
                "date": day,
                "tests_reviewed": 0,
                "Accepted": 0,
                "Rejected": 0,
                "Revise": 0,
                "N/A": 0,
                "users": set(),
            },
        )
        bucket["tests_reviewed"] += 1
        verdict = str(event.get("verdict", "") or "")
        if verdict in ("Accepted", "Rejected", "Revise", "N/A"):
            bucket[verdict] += 1
        user = str(event.get("username", "") or "").strip()
        if user:
            bucket["users"].add(user)
    out = []
    for day in sorted(buckets.keys(), reverse=True):
        bucket = buckets[day]
        bucket["users"] = ", ".join(sorted(bucket["users"], key=str.lower))
        out.append(bucket)
    return out


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
    """Return {path: sha256_hex} for each file that exists."""
    hashes = {}
    for fp in file_paths:
        try:
            if os.path.isfile(fp):
                h = hashlib.sha256()
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


def get_or_create_device_id() -> str:
    """Return stable local device ID used for sync event provenance."""
    try:
        if DEVICE_ID_FILE.exists():
            existing = DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
    except Exception:
        pass

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    device_id = str(uuid4())
    try:
        DEVICE_ID_FILE.write_text(device_id, encoding="utf-8")
    except Exception:
        pass
    return device_id


def append_outbox_event(
    *,
    entity_type: str,
    entity_local_id: str,
    op: str,
    entity_hash: str,
    payload: dict,
    origin_device_id: str | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Append one sync event to durable local outbox journal."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": event_id or str(uuid4()),
        "origin_device_id": origin_device_id or get_or_create_device_id(),
        "entity_type": str(entity_type or ""),
        "entity_local_id": str(entity_local_id or ""),
        "op": str(op or "upsert"),
        "entity_hash": str(entity_hash or ""),
        "payload": payload or {},
        "created_at": created_at or datetime.now().isoformat(),
    }
    with OUTBOX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")
    return event


def load_pending_outbox(limit: int | None = None) -> list[dict]:
    """Return pending outbox events that are not yet marked synced."""
    rows: list[dict] = []
    try:
        if not OUTBOX_FILE.exists():
            return rows
        for line in OUTBOX_FILE.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except Exception:
                continue
            if isinstance(item, dict) and not item.get("synced_at"):
                rows.append(item)
                if limit is not None and limit > 0 and len(rows) >= limit:
                    break
    except Exception:
        return []
    return rows


def save_sync_checkpoint(cursor: str, last_ack_at: str | None = None) -> None:
    """Persist durable sync checkpoint cursor."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "cursor": str(cursor or ""),
        "last_ack_at": last_ack_at or datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    SYNC_CHECKPOINT_FILE.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )


def load_sync_checkpoint() -> dict | None:
    """Load durable sync checkpoint cursor metadata."""
    try:
        if not SYNC_CHECKPOINT_FILE.exists():
            return None
        data = json.loads(SYNC_CHECKPOINT_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def mark_outbox_synced(event_ids: list[str], checkpoint_cursor: str | None = None) -> int:
    """Mark matching outbox events as synced and optionally advance checkpoint."""
    if not event_ids or not OUTBOX_FILE.exists():
        return 0

    targets = set(event_ids)
    updated_rows: list[dict] = []
    synced_count = 0

    for line in OUTBOX_FILE.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue

        if item.get("event_id") in targets and not item.get("synced_at"):
            item["synced_at"] = datetime.now().isoformat()
            item["sync_status"] = "synced"
            synced_count += 1
        updated_rows.append(item)

    with OUTBOX_FILE.open("w", encoding="utf-8") as fh:
        for item in updated_rows:
            fh.write(json.dumps(item, default=str) + "\n")

    if checkpoint_cursor:
        save_sync_checkpoint(checkpoint_cursor)

    return synced_count
