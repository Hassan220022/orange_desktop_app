"""Tests for content hashing utilities (canonical normalization, SHA-256, dHash)."""

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from services.persistence import hashing
from services.persistence.exceptions import HashingError


def test_canonical_value_normalizes_whitespace():
    """_canonical_value strips leading/trailing whitespace but preserves internal newlines."""
    assert hashing._canonical_value("  hello world  ") == "hello world"


def test_canonical_value_lowercases_via_strip_only():
    """_canonical_value strips but does NOT lowercase (preserves case)."""
    assert hashing._canonical_value("FOO Bar") == "FOO Bar"


def test_canonical_value_handles_none():
    assert hashing._canonical_value(None) == ""


def test_canonical_value_handles_nan():
    assert hashing._canonical_value(float("nan")) == ""


def test_canonical_value_handles_timestamp():
    ts = pd.Timestamp("2025-01-15 14:30:00")
    assert hashing._canonical_value(ts) == "2025-01-15 14:30:00"


def test_compute_file_sha256_returns_64_chars(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello")
    h = hashing.compute_file_sha256(f)
    assert len(h) == 64
    assert h == hashlib.sha256(b"hello").hexdigest()


def test_compute_file_sha256_raises_hashing_error_on_missing_file():
    with pytest.raises(HashingError):
        hashing.compute_file_sha256("/nonexistent/path/that/does/not/exist")


def test_compute_image_sha256_matches_hashlib():
    h = hashing.compute_image_sha256(b"image-bytes")
    assert h == hashlib.sha256(b"image-bytes").hexdigest()


def test_compute_row_hash_is_deterministic():
    row = {
        "site_id": "SITE001",
        "alarm_name": "Power Down",
        "alarm_id": "ALM001",
        "occurred_on": pd.Timestamp("2025-01-15 10:00:00"),
    }
    h1 = hashing.compute_row_hash(row)
    h2 = hashing.compute_row_hash(row)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_row_hash_different_rows_differ():
    a = {"site_id": "SITE001", "alarm_id": "ALM001"}
    b = {"site_id": "SITE001", "alarm_id": "ALM002"}
    assert hashing.compute_row_hash(a) != hashing.compute_row_hash(b)


def test_compute_bdt_content_hash_is_deterministic():
    bdt = {
        "site_code": "SITE001",
        "test_date": "2025-01-15",
        "battery_brand": "Acme",
        "battery_ah": "100",
        "num_batteries": "4",
        "num_strings": "2",
        "start_voltage": "54.0",
        "end_voltage": "49.5",
    }
    h1 = hashing.compute_bdt_content_hash(bdt)
    h2 = hashing.compute_bdt_content_hash(bdt)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_canonical_json_sha256_key_order_independent():
    a = {"b": 1, "a": 2}
    b = {"a": 2, "b": 1}
    assert hashing.compute_canonical_json_sha256(a) == hashing.compute_canonical_json_sha256(b)


def test_compute_perceptual_hash_raises_on_missing_file():
    with pytest.raises(HashingError):
        hashing.compute_perceptual_hash("/nonexistent/image.png")
