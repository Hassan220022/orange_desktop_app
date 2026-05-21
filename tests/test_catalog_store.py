"""Tests for data/catalog_store.py."""

import json

import pandas as pd
import pytest

from alarm_app.data.catalog_store import (
    merge_bdt_summary,
    query_bdt_summary,
    query_site_metadata,
    read_bdt_summary,
    replace_site_metadata,
    set_catalog_db_file,
)


@pytest.fixture(autouse=True)
def temp_catalog_db(tmp_path, monkeypatch):
    """Route catalog DuckDB to a temp file so tests are isolated."""
    db_path = tmp_path / "catalog_test.duckdb"
    set_catalog_db_file(db_path)
    # also patch the global so any imports that use the module-level
    # constant are rerouted
    monkeypatch.setattr(
        "alarm_app.data.catalog_store.CATALOG_DB_FILE", db_path
    )
    yield db_path
    # cleanup
    if db_path.exists():
        db_path.unlink()


class TestSiteMetadataDuckDB:
    def test_replace_and_query(self):
        df = pd.DataFrame(
            [
                {
                    "site_id": "ABC123",
                    "original_headers_json": json.dumps({"Code": "code"}),
                    "raw_data_json": json.dumps({"Code": "ABC123", "Site Name": "Alpha"}),
                },
                {
                    "site_id": "XYZ456",
                    "original_headers_json": json.dumps({"Code": "code"}),
                    "raw_data_json": json.dumps({"Code": "XYZ456", "Area": "North"}),
                },
            ]
        )
        count = replace_site_metadata(df)
        assert count == 2

        result = query_site_metadata("ABC123")
        assert len(result) == 1
        raw = json.loads(result.iloc[0]["raw_data_json"])
        assert raw["Site Name"] == "Alpha"

    def test_query_missing_returns_empty(self):
        assert query_site_metadata("NOPE").empty

    def test_replace_clears_previous(self):
        df1 = pd.DataFrame(
            [{"site_id": "S1", "original_headers_json": "{}", "raw_data_json": '{"a":1}'}]
        )
        replace_site_metadata(df1)

        df2 = pd.DataFrame(
            [{"site_id": "S2", "original_headers_json": "{}", "raw_data_json": '{"b":2}'}]
        )
        replace_site_metadata(df2)

        assert query_site_metadata("S1").empty
        assert not query_site_metadata("S2").empty

    def test_replace_deduplicates_site_id_like_primary_key(self):
        df = pd.DataFrame(
            [
                {"site_id": "S1", "original_headers_json": "{}", "raw_data_json": '{"version":1}'},
                {"site_id": "S1", "original_headers_json": "{}", "raw_data_json": '{"version":2}'},
            ]
        )

        count = replace_site_metadata(df)

        result = query_site_metadata("S1")
        assert count == 1
        assert len(result) == 1
        assert json.loads(result.iloc[0]["raw_data_json"])["version"] == 2

    def test_empty_dataframe_creates_table(self):
        df = pd.DataFrame()
        count = replace_site_metadata(df)
        assert count == 0
        # should not raise when querying against empty table
        result = query_site_metadata("ANYTHING")
        assert result.empty

    def test_table_nonexistent_safe_behavior(self):
        # query before any table exists
        result = query_site_metadata("ABC")
        assert result.empty

    def test_search_literal_regex_chars_no_error(self):
        """search_site_metadata uses regex=False — special chars like '[' and '\\' match literally."""
        from alarm_app.data.catalog_store import search_site_metadata

        df = pd.DataFrame([
            {
                "site_id": "S1",
                "site_name": "Site [A] North",
                "area": "Region [X]",
                "subcontractor": "Co\\Sub",
                "original_headers_json": "{}",
                "raw_data_json": json.dumps({"site_id": "S1", "site_name": "Site [A] North"}),
            },
            {
                "site_id": "S2",
                "site_name": "Plain Site",
                "area": "South",
                "subcontractor": "OtherCo",
                "original_headers_json": "{}",
                "raw_data_json": json.dumps({"site_id": "S2", "site_name": "Plain Site"}),
            },
        ])
        replace_site_metadata(df)

        # Searching with '[' should match literal bracket, not raise regex error
        result = search_site_metadata(site_text="[A]")
        assert len(result) == 1
        assert result.iloc[0]["site_id"] == "S1"

        # Searching with '\\' should match literal backslash
        result = search_site_metadata(subcontractor="\\Sub")
        assert len(result) == 1
        assert result.iloc[0]["site_id"] == "S1"

        # Searching with '[' via area should also work
        result = search_site_metadata(area="[X]")
        assert len(result) == 1
        assert result.iloc[0]["site_id"] == "S1"


class TestBDTSummaryDuckDB:
    def _make_bdt_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_merge_basic(self):
        df = self._make_bdt_df(
            [
                {
                    "site_id": "S1",
                    "reporting_period": "W27-24",
                    "week": "W27",
                    "test_date": "2024-07-01",
                    "test_year": 2024,
                    "content_hash": "h1",
                    "original_headers_json": "{}",
                    "raw_data_json": '{"x":1}',
                },
            ]
        )
        merge_bdt_summary(df, ["W27-24"])
        result = query_bdt_summary(site_id="S1")
        assert len(result) == 1
        assert result.iloc[0]["reporting_period"] == "W27-24"

    def test_merge_replaces_period(self):
        df1 = self._make_bdt_df(
            [
                {
                    "site_id": "S1",
                    "reporting_period": "P1",
                    "week": "W1",
                    "test_date": "2024-01-01",
                    "test_year": 2024,
                    "content_hash": "h1",
                    "original_headers_json": "{}",
                    "raw_data_json": '{"a":1}',
                },
                {
                    "site_id": "S2",
                    "reporting_period": "P2",
                    "week": "W2",
                    "test_date": "2024-02-01",
                    "test_year": 2024,
                    "content_hash": "h2",
                    "original_headers_json": "{}",
                    "raw_data_json": '{"a":2}',
                },
            ]
        )
        merge_bdt_summary(df1, ["P1", "P2"])

        # merge P1 with new rows
        df2 = self._make_bdt_df(
            [
                {
                    "site_id": "S3",
                    "reporting_period": "P1",
                    "week": "W1",
                    "test_date": "2024-01-03",
                    "test_year": 2024,
                    "content_hash": "h3",
                    "original_headers_json": "{}",
                    "raw_data_json": '{"a":3}',
                },
            ]
        )
        merge_bdt_summary(df2, ["P1"])

        # P2 should still have S2
        result_p2 = query_bdt_summary(reporting_period="P2")
        assert len(result_p2) == 1
        assert result_p2.iloc[0]["site_id"] == "S2"

        # P1 should only have S3
        result_p1 = query_bdt_summary(reporting_period="P1")
        assert len(result_p1) == 1
        assert result_p1.iloc[0]["site_id"] == "S3"

    def test_query_filters(self):
        df = self._make_bdt_df(
            [
                {
                    "site_id": "S1",
                    "reporting_period": "W27-24",
                    "week": "W27",
                    "test_date": "2024-07-01",
                    "test_year": 2024,
                    "content_hash": "h1",
                    "original_headers_json": "{}",
                    "raw_data_json": '{}',
                },
                {
                    "site_id": "S2",
                    "reporting_period": "W28-24",
                    "week": "W28",
                    "test_date": "2024-07-08",
                    "test_year": 2024,
                    "content_hash": "h2",
                    "original_headers_json": "{}",
                    "raw_data_json": '{}',
                },
            ]
        )
        merge_bdt_summary(df, ["W27-24", "W28-24"])

        result = query_bdt_summary(week="W27")
        assert len(result) == 1
        assert result.iloc[0]["site_id"] == "S1"

        result = query_bdt_summary(test_date_from="2024-07-05")
        assert len(result) == 1
        assert result.iloc[0]["site_id"] == "S2"

    def test_empty_import_safe(self):
        df = pd.DataFrame()
        merge_bdt_summary(df, [])
        result = query_bdt_summary()
        assert result.empty

    def test_merge_deduplicates_like_sqlite_catalog(self):
        row = {
            "site_id": "S1",
            "reporting_period": "W27-24",
            "week": "W27",
            "test_date": "2024-07-01",
            "test_year": 2024,
            "content_hash": "same",
            "original_headers_json": "{}",
            "raw_data_json": '{"x":1}',
        }
        df = self._make_bdt_df([row, {**row, "raw_data_json": '{"x":2}'}])

        merge_bdt_summary(df, ["W27-24"])

        result = query_bdt_summary(site_id="S1")
        assert len(result) == 1
        assert len(read_bdt_summary()) == 1

    def test_nonexistent_table_safe(self):
        result = query_bdt_summary(site_id="X")
        assert result.empty
