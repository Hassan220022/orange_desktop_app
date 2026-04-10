"""Tests for the date filter helpers in core/filters.py plus state round-trip.

These exercise the pure filtering logic without needing a QApplication:
    - ``parse_manual_days`` (standalone function)
    - ``compute_date_mask`` (standalone function)
    - ``save_state`` / ``load_state`` round-trip for the new date keys.
"""

import pandas as pd
import pytest

import alarm_app.data.state as state_mod
from alarm_app.core.filters import compute_date_mask, parse_manual_days


# ─────────────────────────────────────────────────────────────────────
# Shared fixture: isolate state dir for every test in this module
# ─────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _isolate_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state_mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(state_mod, "CACHE_FILE", tmp_path / "data_cache.parquet")
    monkeypatch.setattr(state_mod, "ALARM_IDS_FILE", tmp_path / "alarm_ids.json")
    monkeypatch.setattr(state_mod, "REVIEW_LOG_FILE", tmp_path / "review_log.jsonl")
    monkeypatch.setattr(state_mod, "OUTBOX_FILE", tmp_path / "sync_outbox.jsonl")
    monkeypatch.setattr(
        state_mod, "SYNC_CHECKPOINT_FILE", tmp_path / "sync_checkpoint.json")
    monkeypatch.setattr(state_mod, "DEVICE_ID_FILE", tmp_path / "device_id.txt")


@pytest.fixture
def sample_occurred() -> pd.Series:
    """A small, chronologically ordered occurrence series with a NaT row."""
    return pd.to_datetime([
        "2026-01-01 10:15:00",  # 0
        "2026-01-05 23:30:00",  # 1
        "2026-01-10 00:00:00",  # 2
        "2026-01-15 12:00:00",  # 3
        "2026-02-01 06:30:00",  # 4
        None,                    # 5 — NaT
    ])


# ─────────────────────────────────────────────────────────────────────
# _parse_manual_days
# ─────────────────────────────────────────────────────────────────────
class TestParseManualDays:
    def test_empty_string_returns_empty(self):
        days, invalid = parse_manual_days("")
        assert days == set()
        assert invalid == []

    def test_whitespace_only(self):
        days, invalid = parse_manual_days("   ")
        assert days == set()
        assert invalid == []

    def test_single_valid_day(self):
        days, invalid = parse_manual_days("2026-01-15")
        assert days == {pd.Timestamp("2026-01-15")}
        assert invalid == []

    def test_multiple_valid_days_comma_separated(self):
        days, invalid = parse_manual_days(
            "2026-01-01, 2026-02-02, 2026-03-03")
        assert days == {
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-02-02"),
            pd.Timestamp("2026-03-03"),
        }
        assert invalid == []

    def test_supports_space_and_semicolon_separators(self):
        days, invalid = parse_manual_days(
            "2026-01-01 2026-02-02;2026-03-03")
        assert days == {
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-02-02"),
            pd.Timestamp("2026-03-03"),
        }
        assert invalid == []

    def test_dedupes_repeated_days(self):
        days, invalid = parse_manual_days(
            "2026-01-01, 2026-01-01 , 2026-01-01")
        assert days == {pd.Timestamp("2026-01-01")}
        assert invalid == []

    def test_normalizes_parsed_timestamps_to_midnight(self):
        """Parsed dates should always compare equal to their midnight form."""
        days, _invalid = parse_manual_days("2026-01-15")
        (only,) = days
        assert only == only.normalize()
        assert only.hour == 0 and only.minute == 0 and only.second == 0

    def test_invalid_tokens_are_collected(self):
        days, invalid = parse_manual_days(
            "2026-01-01, not-a-date, 2026-02-02, garbage")
        assert days == {
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-02-02"),
        }
        assert invalid == ["not-a-date", "garbage"]

    def test_all_invalid_returns_empty_days(self):
        days, invalid = parse_manual_days("nope; nada, zilch")
        assert days == set()
        assert invalid == ["nope", "nada", "zilch"]


# ─────────────────────────────────────────────────────────────────────
# compute_date_mask
# ─────────────────────────────────────────────────────────────────────
class TestComputeDateMask:
    def test_neither_active_returns_none(self, sample_occurred):
        mask = compute_date_mask(
            sample_occurred,
            use_range=False,
            from_date="2026-01-01",
            to_date="2026-01-31",
            use_days=False,
            manual_days=[],
        )
        assert mask is None

    def test_range_only(self, sample_occurred):
        mask = compute_date_mask(
            sample_occurred,
            use_range=True,
            from_date="2026-01-01",
            to_date="2026-01-10",
            use_days=False,
            manual_days=[],
        )
        # Row 2 at 2026-01-10 00:00:00 is within the inclusive range.
        assert mask.tolist() == [True, True, True, False, False, False]

    def test_to_date_is_inclusive_through_end_of_day(self):
        """A row at 23:59:58 on the 'to' day must still match."""
        occurred = pd.to_datetime([
            "2026-01-10 00:00:00",
            "2026-01-10 23:59:58",
            "2026-01-11 00:00:00",
        ])
        mask = compute_date_mask(
            occurred,
            use_range=True,
            from_date="2026-01-10",
            to_date="2026-01-10",
            use_days=False,
            manual_days=[],
        )
        assert mask.tolist() == [True, True, False]

    def test_days_only(self, sample_occurred):
        mask = compute_date_mask(
            sample_occurred,
            use_range=False,
            from_date="2026-01-01",
            to_date="2026-01-31",
            use_days=True,
            manual_days={pd.Timestamp("2026-01-05"), pd.Timestamp("2026-02-01")},
        )
        # Row 1 (2026-01-05) and row 4 (2026-02-01) should match.
        assert mask.tolist() == [False, True, False, False, True, False]

    def test_days_only_with_empty_set_matches_nothing(self, sample_occurred):
        mask = compute_date_mask(
            sample_occurred,
            use_range=False,
            from_date="2026-01-01",
            to_date="2026-01-31",
            use_days=True,
            manual_days=set(),
        )
        assert mask.tolist() == [False] * len(sample_occurred)

    def test_union_of_range_and_days(self, sample_occurred):
        """Union must include rows matched by EITHER filter."""
        mask = compute_date_mask(
            sample_occurred,
            use_range=True,
            from_date="2026-01-01",
            to_date="2026-01-10",
            use_days=True,
            manual_days={pd.Timestamp("2026-02-01")},
        )
        # Rows 0, 1, 2 from range; row 4 from days; row 3 excluded; row 5 NaT.
        assert mask.tolist() == [True, True, True, False, True, False]

    def test_nat_rows_always_excluded(self):
        occurred = pd.to_datetime(["2026-01-01", None, "2026-01-02"])
        mask = compute_date_mask(
            occurred,
            use_range=True,
            from_date="2026-01-01",
            to_date="2026-01-31",
            use_days=False,
            manual_days=[],
        )
        assert mask.tolist() == [True, False, True]

    def test_accepts_non_datetime_series_and_coerces(self):
        occurred = pd.Series([
            "2026-01-05",
            "2026-01-20",
            "not-a-date",
        ])
        mask = compute_date_mask(
            occurred,
            use_range=True,
            from_date="2026-01-01",
            to_date="2026-01-10",
            use_days=False,
            manual_days=[],
        )
        assert mask.tolist() == [True, False, False]

    def test_days_normalized_from_arbitrary_times(self, sample_occurred):
        """manual_days values with a time component should still match."""
        mask = compute_date_mask(
            sample_occurred,
            use_range=False,
            from_date="2026-01-01",
            to_date="2026-01-31",
            use_days=True,
            manual_days=[pd.Timestamp("2026-01-05 18:00:00")],
        )
        assert mask.tolist() == [False, True, False, False, False, False]


# ─────────────────────────────────────────────────────────────────────
# Filter integration — apply mask to a DataFrame
# ─────────────────────────────────────────────────────────────────────
class TestDateMaskAppliedToDataFrame:
    @pytest.fixture
    def df(self):
        return pd.DataFrame({
            "site_id": ["A", "B", "C", "D", "E", "F"],
            "occurred_on": pd.to_datetime([
                "2026-01-01 10:00",
                "2026-01-05 20:00",
                "2026-01-10 00:00",
                "2026-01-20 08:00",
                "2026-02-15 15:00",
                None,
            ]),
        })

    def test_range_only_subset(self, df):
        mask = compute_date_mask(
            df["occurred_on"],
            use_range=True,
            from_date="2026-01-01",
            to_date="2026-01-10",
            use_days=False,
            manual_days=[],
        )
        result = df[mask]
        assert list(result["site_id"]) == ["A", "B", "C"]

    def test_days_only_subset(self, df):
        mask = compute_date_mask(
            df["occurred_on"],
            use_range=False,
            from_date="2026-01-01",
            to_date="2026-01-31",
            use_days=True,
            manual_days={pd.Timestamp("2026-01-20"), pd.Timestamp("2026-02-15")},
        )
        result = df[mask]
        assert list(result["site_id"]) == ["D", "E"]

    def test_union_subset(self, df):
        mask = compute_date_mask(
            df["occurred_on"],
            use_range=True,
            from_date="2026-01-01",
            to_date="2026-01-05",
            use_days=True,
            manual_days={pd.Timestamp("2026-02-15")},
        )
        result = df[mask]
        assert list(result["site_id"]) == ["A", "B", "E"]


# ─────────────────────────────────────────────────────────────────────
# state.json round-trip for the new date keys
# ─────────────────────────────────────────────────────────────────────
class TestDateStatePersistence:
    def test_round_trip_range_mode(self):
        payload = {
            "date_enabled": True,
            "date_use_range": True,
            "date_use_days": False,
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
            "date_days": "",
        }
        state_mod.save_state(payload)
        loaded = state_mod.load_state()
        assert loaded["date_enabled"] is True
        assert loaded["date_use_range"] is True
        assert loaded["date_use_days"] is False
        assert loaded["date_from"] == "2026-01-01"
        assert loaded["date_to"] == "2026-01-31"
        assert loaded["date_days"] == ""

    def test_round_trip_specific_days_mode(self):
        payload = {
            "date_enabled": True,
            "date_use_range": False,
            "date_use_days": True,
            "date_days": "2026-01-05, 2026-02-10",
        }
        state_mod.save_state(payload)
        loaded = state_mod.load_state()
        assert loaded["date_use_range"] is False
        assert loaded["date_use_days"] is True
        assert loaded["date_days"] == "2026-01-05, 2026-02-10"

    def test_round_trip_combined_mode(self):
        payload = {
            "date_enabled": True,
            "date_use_range": True,
            "date_use_days": True,
            "date_from": "2026-03-01",
            "date_to": "2026-03-15",
            "date_days": "2026-03-20",
        }
        state_mod.save_state(payload)
        loaded = state_mod.load_state()
        assert loaded["date_use_range"] is True
        assert loaded["date_use_days"] is True
        assert loaded["date_from"] == "2026-03-01"
        assert loaded["date_to"] == "2026-03-15"
        assert loaded["date_days"] == "2026-03-20"

    def test_round_trip_disabled(self):
        payload = {
            "date_enabled": False,
            "date_use_range": False,
            "date_use_days": False,
        }
        state_mod.save_state(payload)
        loaded = state_mod.load_state()
        assert loaded["date_enabled"] is False
        assert loaded["date_use_range"] is False
        assert loaded["date_use_days"] is False
