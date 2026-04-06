"""
State persistence — save/restore UI state and DataFrame cache across sessions.

Uses ~/.alarm_viewer/ with:
  state.json        — UI settings, filter values, window geometry
  data_cache.parquet — full DataFrame for fast restore (~1s vs 10-30s)
"""

import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path

import pandas as pd

STATE_DIR  = Path.home() / ".alarm_viewer"
STATE_FILE = STATE_DIR / "state.json"
CACHE_FILE = STATE_DIR / "data_cache.parquet"
AUTH_FILE = STATE_DIR / "users.json"
REVIEW_LOG_FILE = STATE_DIR / "review_log.jsonl"

_PASSWORD_ITERATIONS = 120_000


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


# ── Local user authentication ──────────────────────────────
def _normalize_username(username: str) -> str:
    return str(username or "").strip()


def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        _PASSWORD_ITERATIONS,
    )
    return salt.hex(), digest.hex()


def _load_json_file(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json_file(path: Path, payload) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _coerce_user_store(raw) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}
    users = raw.get("users") if isinstance(raw.get("users"), dict) else raw
    out: dict[str, dict] = {}
    for username, record in users.items():
        name = _normalize_username(username)
        if not name or not isinstance(record, dict):
            continue
        salt = str(record.get("salt", "") or "").strip()
        digest = str(record.get("hash", "") or "").strip()
        if not salt or not digest:
            continue
        out[name] = {
            "salt": salt,
            "hash": digest,
            "iterations": int(record.get("iterations", _PASSWORD_ITERATIONS)),
            "created_at": str(record.get("created_at", "") or ""),
            "updated_at": str(record.get("updated_at", "") or ""),
        }
    return out


def load_users() -> dict[str, dict]:
    """Load the local username/password store."""
    raw = _load_json_file(AUTH_FILE, {})
    return _coerce_user_store(raw)


def save_users(users: dict[str, dict]) -> None:
    """Persist the local username/password store."""
    _save_json_file(
        AUTH_FILE,
        {
            "users": users,
            "saved_at": datetime.now().isoformat(),
        },
    )


def has_users() -> bool:
    return bool(load_users())


def verify_user(username: str, password: str) -> bool:
    users = load_users()
    name = _normalize_username(username)
    record = users.get(name)
    if not record:
        return False
    salt, digest = _hash_password(password, record.get("salt"))
    return digest == record.get("hash")


def upsert_user(username: str, password: str) -> None:
    name = _normalize_username(username)
    if not name:
        raise ValueError("Username cannot be empty")
    if not str(password or ""):
        raise ValueError("Password cannot be empty")

    users = load_users()
    existing = users.get(name, {})
    salt, digest = _hash_password(password)
    users[name] = {
        "salt": salt,
        "hash": digest,
        "iterations": _PASSWORD_ITERATIONS,
        "created_at": existing.get("created_at") or datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    save_users(users)


def delete_user(username: str) -> None:
    users = load_users()
    name = _normalize_username(username)
    if name in users:
        users.pop(name, None)
        save_users(users)


def list_usernames() -> list[str]:
    return sorted(load_users().keys(), key=str.lower)


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
        "username": _normalize_username(username),
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
        user = _normalize_username(event.get("username", ""))
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
