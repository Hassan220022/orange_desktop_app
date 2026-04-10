"""Tests for db/hashing.py."""
import pytest
import pandas as pd
from datetime import datetime, date
from alarm_app.db.hashing import (
    compute_file_sha256, compute_row_hash, compute_image_sha256,
    compute_bdt_content_hash, compute_canonical_json_sha256,
    _canonical_value,
)


class TestCanonicalValue:
    def test_none_returns_empty(self):
        assert _canonical_value(None) == ""

    def test_nan_returns_empty(self):
        assert _canonical_value(float("nan")) == ""

    def test_datetime_format(self):
        assert _canonical_value(datetime(2026, 1, 15, 10, 30)) == "2026-01-15 10:30:00"

    def test_date_format(self):
        assert _canonical_value(date(2026, 1, 15)) == "2026-01-15"

    def test_string_stripped(self):
        assert _canonical_value("  hello  ") == "hello"

    def test_number(self):
        assert _canonical_value(42) == "42"


class TestComputeRowHash:
    def test_deterministic(self):
        row = {"site_id": "S1", "alarm_name": "Power", "occurred_on": "2026-01-01"}
        assert compute_row_hash(row) == compute_row_hash(row)

    def test_different_rows_different_hash(self):
        r1 = {"site_id": "S1", "alarm_name": "Power"}
        r2 = {"site_id": "S2", "alarm_name": "Power"}
        assert compute_row_hash(r1) != compute_row_hash(r2)

    def test_works_with_series(self):
        s = pd.Series({"site_id": "S1", "alarm_name": "Power"})
        assert len(compute_row_hash(s)) == 64

    def test_missing_columns_stable(self):
        row = {"site_id": "S1"}
        assert compute_row_hash(row) == compute_row_hash(row)


class TestComputeFileSha256:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        assert compute_file_sha256(f) == compute_file_sha256(f)
        assert len(compute_file_sha256(f)) == 64

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert compute_file_sha256(f1) != compute_file_sha256(f2)


class TestComputeImageSha256:
    def test_deterministic(self):
        data = b"\x89PNG\r\n\x1a\nfakeimage"
        assert compute_image_sha256(data) == compute_image_sha256(data)


class TestComputeBdtContentHash:
    def test_deterministic(self):
        bdt = {"site_code": "ABC", "test_date": "2026-01-01", "battery_brand": "Narada", "battery_ah": 200}
        assert compute_bdt_content_hash(bdt) == compute_bdt_content_hash(bdt)

    def test_site_code_case_insensitive(self):
        b1 = {"site_code": "abc", "test_date": "2026-01-01"}
        b2 = {"site_code": "ABC", "test_date": "2026-01-01"}
        assert compute_bdt_content_hash(b1) == compute_bdt_content_hash(b2)


class TestComputeCanonicalJsonSha256:
    def test_key_order_independent(self):
        h1 = compute_canonical_json_sha256({"b": 2, "a": 1})
        h2 = compute_canonical_json_sha256({"a": 1, "b": 2})
        assert h1 == h2
