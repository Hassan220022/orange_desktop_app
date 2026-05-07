"""Canonical normalization and hash computation for dedup."""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd


def compute_file_sha256(path: str | Path) -> str:
    """SHA-256 of file bytes. Reads in 64KB chunks for large files."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_value(value) -> str:
    """Normalize a value for canonical hashing."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    # pd.NaT passes isinstance checks for datetime/Timestamp, so catch it first
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    return s


ALARM_HASH_COLS = (
    "site_id", "alarm_name", "alarm_id", "network_type", "vendor",
    "occurred_on", "cleared_on", "duration", "clearance_status",
    "alarm_source", "alarm_category",
)


def compute_row_hash(row: dict | pd.Series,
                     key_columns: tuple = ALARM_HASH_COLS) -> str:
    """SHA-256 of pipe-delimited canonical values from key columns."""
    if isinstance(row, pd.Series):
        row = row.to_dict()
    composite = "|".join(_canonical_value(row.get(c)) for c in key_columns)
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_image_sha256(image_bytes: bytes) -> str:
    """SHA-256 of raw image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_perceptual_hash(image_path: str | Path) -> str:
    """dHash of an image for near-duplicate detection."""
    import imagehash
    from PIL import Image
    img = Image.open(image_path)
    return str(imagehash.dhash(img, hash_size=16))


def compute_bdt_content_hash(bdt_dict: dict) -> str:
    """Deterministic hash of BDT test content for dedup."""
    fields = [
        str(bdt_dict.get("site_code", "")).strip().upper(),
        str(bdt_dict.get("test_date", "")),
        str(bdt_dict.get("battery_brand", "")).strip().lower(),
        str(bdt_dict.get("battery_ah", "")),
        str(bdt_dict.get("num_batteries", "")),
        str(bdt_dict.get("num_strings", "")),
        str(bdt_dict.get("start_voltage", "")),
        str(bdt_dict.get("end_voltage", "")),
    ]
    composite = "|".join(fields)
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_canonical_json_sha256(payload: dict) -> str:
    """SHA-256 of JSON with sorted keys for deterministic hashing."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
